"""
app.py
台灣一週農業氣象預報 — 互動式 Streamlit 儀表板
以 Folium 地圖呈現各地區溫度，搭配日期篩選器與資料表格。
"""

import streamlit as st
import pandas as pd
import folium
from streamlit_folium import st_folium
import os
import json

# ── 頁面設定 ─────────────────────────────────────────────────────────
st.set_page_config(
    page_title="🌾 台灣農業氣象預報",
    page_icon="🌾",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── 自訂 CSS 樣式 ────────────────────────────────────────────────────
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@300;400;500;700;900&display=swap');

    /* 全域字型 */
    html, body, [class*="css"] {
        font-family: 'Noto Sans TC', sans-serif;
    }

    /* 頂部標題列 */
    .main-header {
        background: linear-gradient(135deg, #0f2027 0%, #203a43 50%, #2c5364 100%);
        padding: 1.8rem 2rem;
        border-radius: 16px;
        margin-bottom: 1.5rem;
        box-shadow: 0 8px 32px rgba(0,0,0,0.25);
        text-align: center;
    }
    .main-header h1 {
        color: #ffffff;
        font-size: 2rem;
        font-weight: 900;
        margin: 0;
        letter-spacing: 2px;
        text-shadow: 0 2px 8px rgba(0,0,0,0.3);
    }
    .main-header p {
        color: #94d2bd;
        font-size: 0.95rem;
        margin: 0.3rem 0 0 0;
        font-weight: 300;
    }

    /* 指標卡片 */
    .metric-card {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border: 1px solid rgba(148, 210, 189, 0.15);
        border-radius: 14px;
        padding: 1.2rem 1rem;
        text-align: center;
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    .metric-card:hover {
        transform: translateY(-3px);
        box-shadow: 0 8px 30px rgba(148, 210, 189, 0.15);
    }
    .metric-label {
        color: #94a3b8;
        font-size: 0.78rem;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 1.5px;
        margin-bottom: 0.3rem;
    }
    .metric-value {
        color: #f1f5f9;
        font-size: 1.8rem;
        font-weight: 900;
    }

    /* 溫度色彩 */
    .temp-cold   { color: #60a5fa; }
    .temp-cool   { color: #34d399; }
    .temp-warm   { color: #fbbf24; }
    .temp-hot    { color: #f87171; }

    /* 圖例 */
    .legend-container {
        display: flex;
        gap: 1rem;
        justify-content: center;
        flex-wrap: wrap;
        margin: 1rem 0;
    }
    .legend-item {
        display: flex;
        align-items: center;
        gap: 0.4rem;
        font-size: 0.82rem;
        color: #cbd5e1;
    }
    .legend-dot {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        display: inline-block;
        box-shadow: 0 0 8px rgba(255,255,255,0.15);
    }

    /* 資料表格美化 */
    .dataframe-container {
        background: #0f172a;
        border-radius: 12px;
        padding: 0.5rem;
        border: 1px solid rgba(148, 210, 189, 0.1);
    }

    /* 日期選擇器區塊 */
    .date-selector {
        background: linear-gradient(145deg, #1e293b, #0f172a);
        border: 1px solid rgba(148, 210, 189, 0.15);
        border-radius: 14px;
        padding: 1.2rem;
        margin-bottom: 1rem;
    }

    /* 隱藏 Streamlit 預設選單 */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}

    /* Selectbox 美化 */
    div[data-baseweb="select"] {
        border-radius: 10px;
    }

    /* 區分區塊 */
    .section-title {
        color: #94d2bd;
        font-size: 1.1rem;
        font-weight: 700;
        margin-bottom: 0.8rem;
        padding-bottom: 0.4rem;
        border-bottom: 2px solid rgba(148, 210, 189, 0.2);
    }
</style>
""", unsafe_allow_html=True)

# ── 各地區近似座標 ──────────────────────────────────────────────────
REGION_COORDS = {
    "北部地區": (25.03, 121.52),
    "中部地區": (24.15, 120.67),
    "南部地區": (22.63, 120.30),
    "東北部地區": (24.76, 121.75),
    "東部地區": (23.97, 121.60),
    "東南部地區": (22.75, 121.14),
}

# 備用英文名稱對照
REGION_NAMES_EN = {
    "北部地區": "Northern",
    "中部地區": "Central",
    "南部地區": "Southern",
    "東北部地區": "Northeastern",
    "東部地區": "Eastern",
    "東南部地區": "Southeastern",
}


def get_temp_color(avg_temp):
    """根據平均溫度回傳對應的顏色代碼。"""
    if avg_temp is None:
        return "#6b7280"  # 灰色
    if avg_temp < 20:
        return "#3b82f6"  # 藍
    elif avg_temp <= 25:
        return "#22c55e"  # 綠
    elif avg_temp <= 30:
        return "#eab308"  # 黃
    else:
        return "#ef4444"  # 紅


def get_temp_class(avg_temp):
    """回傳 CSS 類別名稱。"""
    if avg_temp is None:
        return ""
    if avg_temp < 20:
        return "temp-cold"
    elif avg_temp <= 25:
        return "temp-cool"
    elif avg_temp <= 30:
        return "temp-warm"
    else:
        return "temp-hot"


def load_data():
    """載入 weather_data.csv，若不存在則即時擷取。"""
    csv_path = os.path.join(os.path.dirname(__file__), "weather_data.csv")

    if os.path.exists(csv_path):
        df = pd.read_csv(csv_path)
        return df
    else:
        st.warning("⚠️ 找不到 weather_data.csv，正在即時擷取資料...")
        # 動態匯入並執行 fetch_weather
        from fetch_weather import fetch_weather_data, parse_weather_data, save_to_csv
        raw = fetch_weather_data()
        if raw is None:
            st.error("❌ 無法取得 CWA 氣象資料，請檢查網路連線。")
            return pd.DataFrame()
        df = parse_weather_data(raw)
        if not df.empty:
            save_to_csv(df, csv_path)
        return df


def build_map(df_day):
    """建立 Folium 地圖，以彩色圓圈標記各地區溫度。"""
    # 台灣中心座標
    m = folium.Map(
        location=[23.7, 120.96],
        zoom_start=7,
        tiles="CartoDB dark_matter",
        control_scale=True,
    )

    for _, row in df_day.iterrows():
        region = row["地區"]
        coords = REGION_COORDS.get(region)
        if coords is None:
            continue

        avg_temp = row.get("平均溫(°C)")
        min_temp = row.get("最低溫(°C)")
        max_temp = row.get("最高溫(°C)")
        color = get_temp_color(avg_temp)
        en_name = REGION_NAMES_EN.get(region, region)

        # Popup HTML
        popup_html = f"""
        <div style="font-family:'Noto Sans TC',sans-serif; min-width:180px;
                    background:#1e293b; color:#f1f5f9; border-radius:12px;
                    padding:14px; box-shadow:0 4px 16px rgba(0,0,0,0.3);">
            <div style="font-size:15px; font-weight:700; color:#94d2bd;
                        margin-bottom:8px; border-bottom:1px solid rgba(148,210,189,0.3);
                        padding-bottom:6px;">
                📍 {region}
                <span style="font-size:11px; color:#64748b; margin-left:4px;">
                    {en_name}
                </span>
            </div>
            <div style="display:flex; justify-content:space-between; margin:6px 0;">
                <span style="color:#94a3b8; font-size:12px;">🌡️ 最低溫</span>
                <span style="color:#60a5fa; font-weight:700;">{min_temp}°C</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin:6px 0;">
                <span style="color:#94a3b8; font-size:12px;">🔥 最高溫</span>
                <span style="color:#f87171; font-weight:700;">{max_temp}°C</span>
            </div>
            <div style="display:flex; justify-content:space-between; margin:6px 0;
                        padding-top:6px; border-top:1px solid rgba(148,210,189,0.15);">
                <span style="color:#94a3b8; font-size:12px;">📊 平均溫</span>
                <span style="font-weight:900; font-size:16px; color:{color};">{avg_temp}°C</span>
            </div>
        </div>
        """

        # 圓圈標記
        folium.CircleMarker(
            location=coords,
            radius=22,
            color=color,
            fill=True,
            fill_color=color,
            fill_opacity=0.55,
            weight=3,
            popup=folium.Popup(popup_html, max_width=260),
            tooltip=f"{region}: {avg_temp}°C",
        ).add_to(m)

        # 在圓圈中央加上溫度文字標籤
        folium.Marker(
            location=coords,
            icon=folium.DivIcon(
                html=f'<div style="font-size:11px; font-weight:700; color:{color}; '
                     f'text-align:center; text-shadow:0 1px 3px rgba(0,0,0,0.8); '
                     f'margin-top:-5px;">{avg_temp}°</div>',
                icon_size=(50, 20),
                icon_anchor=(25, 10),
            ),
        ).add_to(m)

    return m


def main():
    # ── 標題 ─────────────────────────────────────────────────────
    st.markdown("""
    <div class="main-header">
        <h1>🌾 台灣一週農業氣象預報</h1>
        <p>資料來源：中央氣象署 CWA Open Data ｜ F-A0010-001</p>
    </div>
    """, unsafe_allow_html=True)

    # ── 載入資料 ─────────────────────────────────────────────────
    df = load_data()

    if df.empty:
        st.error("🚫 無可用資料。請先執行 `python fetch_weather.py` 以取得氣象資料。")
        st.code("python fetch_weather.py", language="bash")
        return

    # ── 確保欄位型別正確 ─────────────────────────────────────────
    for col in ["最低溫(°C)", "最高溫(°C)", "平均溫(°C)"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── 日期列表 ─────────────────────────────────────────────────
    dates = sorted(df["日期"].unique().tolist())

    # ── 快速指標 ─────────────────────────────────────────────────
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)

    with col_m1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">📅 預報天數</div>
            <div class="metric-value">{len(dates)}</div>
        </div>""", unsafe_allow_html=True)

    with col_m2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">📍 涵蓋地區</div>
            <div class="metric-value">{df['地區'].nunique()}</div>
        </div>""", unsafe_allow_html=True)

    with col_m3:
        overall_min = df["最低溫(°C)"].min()
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">❄️ 全期最低溫</div>
            <div class="metric-value temp-cold">{overall_min}°C</div>
        </div>""", unsafe_allow_html=True)

    with col_m4:
        overall_max = df["最高溫(°C)"].max()
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-label">🔥 全期最高溫</div>
            <div class="metric-value temp-hot">{overall_max}°C</div>
        </div>""", unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 左右版面 ─────────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown('<div class="section-title">🗺️ 台灣地區溫度分布圖</div>',
                    unsafe_allow_html=True)

        # 日期選擇器
        selected_date = st.selectbox(
            "📅 選擇預報日期",
            options=dates,
            index=0,
            key="date_selector",
            help="選擇日期以檢視該日各地區的溫度分布",
        )

        # 圖例
        st.markdown("""
        <div class="legend-container">
            <div class="legend-item">
                <span class="legend-dot" style="background:#3b82f6;"></span>
                <span>&lt; 20°C 偏涼</span>
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background:#22c55e;"></span>
                <span>20–25°C 舒適</span>
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background:#eab308;"></span>
                <span>25–30°C 偏暖</span>
            </div>
            <div class="legend-item">
                <span class="legend-dot" style="background:#ef4444;"></span>
                <span>&gt; 30°C 炎熱</span>
            </div>
        </div>
        """, unsafe_allow_html=True)

        # 篩選該日資料
        df_day = df[df["日期"] == selected_date].copy()

        # 建立地圖
        weather_map = build_map(df_day)
        st_folium(weather_map, width=None, height=520, returned_objects=[])

    with col_right:
        st.markdown(f'<div class="section-title">📋 {selected_date} 各地區溫度一覽</div>',
                    unsafe_allow_html=True)

        if not df_day.empty:
            # 顯示溫度卡片
            for _, row in df_day.iterrows():
                region = row["地區"]
                min_t = row["最低溫(°C)"]
                max_t = row["最高溫(°C)"]
                avg_t = row["平均溫(°C)"]
                color = get_temp_color(avg_t)
                css_class = get_temp_class(avg_t)
                en_name = REGION_NAMES_EN.get(region, "")

                st.markdown(f"""
                <div style="background:linear-gradient(145deg, #1e293b, #0f172a);
                            border-left: 4px solid {color};
                            border-radius: 10px; padding: 0.9rem 1.1rem;
                            margin-bottom: 0.7rem;
                            box-shadow: 0 2px 12px rgba(0,0,0,0.15);
                            transition: transform 0.2s ease;">
                    <div style="display:flex; justify-content:space-between; align-items:center;">
                        <div>
                            <span style="color:#f1f5f9; font-weight:700; font-size:1rem;">
                                📍 {region}
                            </span>
                            <span style="color:#64748b; font-size:0.75rem; margin-left:6px;">
                                {en_name}
                            </span>
                        </div>
                        <div style="font-size:1.3rem; font-weight:900;" class="{css_class}">
                            {avg_t}°C
                        </div>
                    </div>
                    <div style="display:flex; gap:1.5rem; margin-top:0.5rem;">
                        <span style="color:#60a5fa; font-size:0.82rem;">
                            ❄️ {min_t}°C
                        </span>
                        <span style="color:#f87171; font-size:0.82rem;">
                            🔥 {max_t}°C
                        </span>
                    </div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("<br>", unsafe_allow_html=True)

            # 資料表格
            st.markdown('<div class="section-title">📊 詳細資料表格</div>',
                        unsafe_allow_html=True)

            display_df = df_day[["地區", "最低溫(°C)", "最高溫(°C)", "平均溫(°C)"]].reset_index(drop=True)
            display_df.index = display_df.index + 1
            display_df.index.name = "#"

            st.dataframe(
                display_df,
                use_container_width=True,
                column_config={
                    "地區": st.column_config.TextColumn("地區", width="medium"),
                    "最低溫(°C)": st.column_config.NumberColumn("最低溫 (°C)", format="%.1f"),
                    "最高溫(°C)": st.column_config.NumberColumn("最高溫 (°C)", format="%.1f"),
                    "平均溫(°C)": st.column_config.NumberColumn("平均溫 (°C)", format="%.1f"),
                },
            )
        else:
            st.info("ℹ️ 該日期無資料。")

    # ── 全期趨勢總覽 ─────────────────────────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    st.markdown('<div class="section-title">📈 各地區全期溫度趨勢</div>',
                unsafe_allow_html=True)

    # 將資料轉為適合折線圖的格式
    if len(dates) > 1:
        chart_col1, chart_col2 = st.columns(2)

        with chart_col1:
            st.markdown("##### 🔥 最高溫趨勢")
            pivot_max = df.pivot_table(
                values="最高溫(°C)", index="日期", columns="地區", aggfunc="first"
            )
            st.line_chart(pivot_max, height=300)

        with chart_col2:
            st.markdown("##### ❄️ 最低溫趨勢")
            pivot_min = df.pivot_table(
                values="最低溫(°C)", index="日期", columns="地區", aggfunc="first"
            )
            st.line_chart(pivot_min, height=300)

    # ── 頁尾 ─────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown(
        '<div style="text-align:center; color:#64748b; font-size:0.8rem; padding:0.5rem;">'
        '🌾 資料來源：<a href="https://opendata.cwa.gov.tw/dataset/forecast/F-A0010-001" '
        'target="_blank" style="color:#94d2bd;">中央氣象署開放資料平台</a> ｜ '
        'F-A0010-001 一週農業氣象預報'
        '</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
