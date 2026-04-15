import streamlit as st
import sqlite3
import pandas as pd
import os

# 網頁設定
st.set_page_config(page_title="一週氣溫預報", page_icon="🌤️", layout="centered")

def get_connection():
    """取得 SQLite 資料庫連線，若無資料庫則先自動擷取資料"""
    db_path = os.path.join(os.path.dirname(__file__), "data.db")
    
    if not os.path.exists(db_path):
        with st.spinner("雲端首次啟動，正在從 CWA 擷取最新氣象資料並建立資料庫..."):
            try:
                from fetch_weather import fetch_weather_data, parse_weather_data, save_to_db, save_to_csv
                raw = fetch_weather_data()
                if raw is not None:
                    df = parse_weather_data(raw)
                    if not df.empty:
                        save_to_csv(df)
                        save_to_db(df)
            except Exception as e:
                st.error(f"建立資料庫時發生錯誤: {e}")
                
    return sqlite3.connect(db_path)

st.title("🌤️ 一週農業氣象預報 (從 SQLite 讀取)")

try:
    conn = get_connection()
    # 取得地區清單
    regions_df = pd.read_sql_query("SELECT DISTINCT regionName FROM TemperatureForecasts", conn)
    regions = regions_df['regionName'].tolist()
    
    if not regions:
        st.warning("資料庫中沒有資料，請先執行 `python fetch_weather.py` 擷取資料！")
    else:
        # 下拉選單讓使用者選擇地區
        selected_region = st.selectbox("📍 請選擇地區", regions)
        
        # 從資料庫查詢該地區的一週氣溫資料
        query = """
        SELECT dataDate as 日期, mint as '最低氣溫(°C)', maxt as '最高氣溫(°C)' 
        FROM TemperatureForecasts 
        WHERE regionName = ?
        ORDER BY dataDate
        """
        df = pd.read_sql_query(query, conn, params=(selected_region,))
        
        if not df.empty:
            st.subheader(f"📊 {selected_region} - 近一週氣溫趨勢")
            
            # 使用折線圖顯示氣溫資料
            # 將日期設為 index 讓折線圖橫軸顯示日期
            chart_data = df.set_index("日期")[["最低氣溫(°C)", "最高氣溫(°C)"]]
            st.line_chart(chart_data)
            
            # 使用表格顯示詳細氣溫資料
            st.subheader("📋 詳細資料表格")
            st.dataframe(df, use_container_width=True)
        else:
            st.info("該地區沒有查詢到資料。")

except sqlite3.OperationalError:
    st.error("❌ 找不到資料庫 `data.db` 或是資料表不存在，請確認是否已經執行 `fetch_weather.py` 建立並儲存資料庫！")
finally:
    if 'conn' in locals():
        conn.close()
