"""
fetch_weather.py
從中央氣象署開放資料平台取得一週農業氣象預報 (F-A0010-001)，
解析 JSON 回應，萃取各地區之最低溫與最高溫，儲存為 weather_data.csv。
"""

import requests
import pandas as pd
import json
import os
import sys
import urllib3
import sqlite3
from datetime import datetime, timedelta
from dotenv import load_dotenv

# -- 載入 .env 環境變數 ----------------------------------------------------
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))

# -- 修正 Windows 終端機編碼問題 ------------------------------------------
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# -- 停用 SSL 警告（某些環境可能遇到憑證問題）-------------------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# -- CWA API 設定 ----------------------------------------------------------
# F-A0010-001 為 rawData 類型，需使用 fileapi 而非 datastore REST API
API_URL = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/F-A0010-001"


def load_api_key():
    """從環境變數或 Streamlit Secrets 讀取 API 授權碼。"""
    # 若在 Streamlit 環境下，優先嘗試讀取 Streamlit Secrets
    try:
        import streamlit as st
        if "API_KEY" in st.secrets:
            return st.secrets["API_KEY"]
    except Exception:
        pass
        
    # 回退到本機的環境變數 (由 dotenv 載入)
    api_key = os.getenv("API_KEY", "")
    if not api_key:
        print("[WARN] 尚未設定 API_KEY 環境變數！")
        print("       請在 .env 檔案或 Streamlit Secrets 中設定: API_KEY=CWA-XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
    return api_key


def fetch_weather_data():
    """向 CWA API 取得農業氣象預報並回傳原始 JSON 資料。"""
    api_key = load_api_key()

    if not api_key:
        print("[WARN] 尚未設定 CWA API 授權碼！")
        print("       請在 .env 檔案中設定 API_KEY。")
        print("       授權碼申請: https://opendata.cwa.gov.tw/")
        return None

    params = {
        "Authorization": api_key,
        "downloadType": "WEB",
        "format": "JSON",
    }

    try:
        # verify=False 以處理某些環境下 SSL 驗證失敗的問題
        response = requests.get(API_URL, params=params, verify=False, timeout=30)
        response.raise_for_status()
        data = response.json()
        print("[OK] 成功取得 CWA 氣象資料！")
        return data
    except requests.exceptions.HTTPError as e:
        print(f"[ERROR] HTTP 錯誤: {e}")
        if response.status_code == 401:
            print("        授權碼無效，請檢查 .env 中的 API_KEY。")
        return None
    except requests.exceptions.RequestException as e:
        print(f"[ERROR] 取得資料時發生錯誤: {e}")
        return None


def parse_weather_data(data):
    """
    解析 CWA fileapi 的 JSON 回應，萃取各地區、各日期的最低溫與最高溫。
    JSON 結構: cwaopendata > resources > resource > data >
               agrWeatherForecasts > weatherForecasts > location[]
    每個 location 含 weatherElements > MaxT/MinT > daily[] > {dataDate, temperature}
    回傳 pandas DataFrame。
    """
    records = []

    try:
        # 導航至 weatherForecasts 層
        agr = data["cwaopendata"]["resources"]["resource"]["data"]["agrWeatherForecasts"]
        locations = agr["weatherForecasts"]["location"]

        for loc in locations:
            location_name = loc["locationName"]
            elements = loc["weatherElements"]

            # 取最高溫與最低溫的每日資料
            max_t_daily = elements.get("MaxT", {}).get("daily", [])
            min_t_daily = elements.get("MinT", {}).get("daily", [])

            # 建立以日期為 key 的 dict 方便配對
            max_t_map = {d["dataDate"]: float(d["temperature"]) for d in max_t_daily}
            min_t_map = {d["dataDate"]: float(d["temperature"]) for d in min_t_daily}

            # 取所有唯一日期（合併 MaxT 和 MinT 的日期）
            all_dates = sorted(set(list(max_t_map.keys()) + list(min_t_map.keys())))

            for date_str in all_dates:
                max_temp = max_t_map.get(date_str)
                min_temp = min_t_map.get(date_str)

                avg_temp = None
                if min_temp is not None and max_temp is not None:
                    avg_temp = round((min_temp + max_temp) / 2, 1)

                records.append({
                    "日期": date_str,
                    "地區": location_name,
                    "最低溫(°C)": min_temp,
                    "最高溫(°C)": max_temp,
                    "平均溫(°C)": avg_temp,
                    "起始時間": f"{date_str}T06:00:00+08:00",
                    "結束時間": f"{date_str}T18:00:00+08:00",
                })

    except (KeyError, TypeError) as e:
        print(f"[ERROR] 解析資料時發生錯誤: {e}")
        print("嘗試分析 JSON 結構...")
        # 儲存原始 JSON 以利偵錯
        debug_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "raw_response.json")
        with open(debug_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"已將原始回應儲存至 {debug_path}")

    df = pd.DataFrame(records)
    return df


def generate_sample_data():
    """
    產生範例資料，供沒有 API 金鑰時展示使用。
    模擬 7 天、6 個地區的溫度資料。
    """
    import random
    random.seed(42)

    regions = {
        "北部地區":   {"min_base": 18, "max_base": 26},
        "中部地區":   {"min_base": 19, "max_base": 28},
        "南部地區":   {"min_base": 22, "max_base": 31},
        "東北部地區": {"min_base": 17, "max_base": 24},
        "東部地區":   {"min_base": 19, "max_base": 27},
        "東南部地區": {"min_base": 21, "max_base": 29},
    }

    records = []
    today = datetime.now()

    for day_offset in range(7):
        date = today + timedelta(days=day_offset)
        date_str = date.strftime("%Y-%m-%d")

        for region, temps in regions.items():
            min_temp = temps["min_base"] + random.uniform(-2, 2)
            max_temp = temps["max_base"] + random.uniform(-2, 2)
            min_temp = round(min_temp, 1)
            max_temp = round(max_temp, 1)
            avg_temp = round((min_temp + max_temp) / 2, 1)

            records.append({
                "日期": date_str,
                "地區": region,
                "最低溫(°C)": min_temp,
                "最高溫(°C)": max_temp,
                "平均溫(°C)": avg_temp,
                "起始時間": f"{date_str}T06:00:00+08:00",
                "結束時間": f"{date_str}T18:00:00+08:00",
            })

    return pd.DataFrame(records)


def save_to_csv(df, filename="weather_data.csv"):
    """將 DataFrame 存為 CSV 檔案。"""
    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), filename)
    df.to_csv(filepath, index=False, encoding="utf-8-sig")
    print(f"[OK] 資料已儲存至 {filepath} (共 {len(df)} 筆)")


def save_to_db(df, db_name="data.db"):
    """將 DataFrame 存為 SQLite3 資料庫。"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), db_name)
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 創建 Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS TemperatureForecasts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            regionName TEXT,
            dataDate TEXT,
            mint REAL,
            maxt REAL
        )
    ''')
    
    # 清空舊資料，避免重複
    cursor.execute('DELETE FROM TemperatureForecasts')
    
    # 插入資料
    for _, row in df.iterrows():
        cursor.execute('''
            INSERT INTO TemperatureForecasts (regionName, dataDate, mint, maxt)
            VALUES (?, ?, ?, ?)
        ''', (row['地區'], row['日期'], row['最低溫(°C)'], row['最高溫(°C)']))
        
    conn.commit()
    conn.close()
    print(f"[OK] 資料已儲存至 SQLite 資料庫 {db_path} (共 {len(df)} 筆)")


def main():
    print("=" * 60)
    print("  CWA 一週農業氣象預報 -- 資料擷取工具")
    print("  資料集: F-A0010-001")
    print("=" * 60)

    # 1. 嘗試取得真實資料
    raw_data = fetch_weather_data()

    if raw_data is not None:
        # 2. 解析資料
        df = parse_weather_data(raw_data)

        if df.empty:
            print("[WARN] 未解析到任何資料，API 可能回傳了不同的結構。")
            print("       改用範例資料展示...")
            df = generate_sample_data()
        else:
            print(f"\n[DATA] 資料概覽:")
            print(f"  地區: {df['地區'].unique().tolist()}")
            print(f"  日期範圍: {df['日期'].min()} ~ {df['日期'].max()}")
            print(f"  總筆數: {len(df)}")
    else:
        print("\n[INFO] 無法取得真實資料，改用範例資料展示。")
        print("       若需真實資料，請至 https://opendata.cwa.gov.tw/ 申請授權碼，")
        print("       並填入 .env 的 API_KEY 欄位。\n")
        df = generate_sample_data()

    # 3. 顯示
    print()
    print(df.to_string(index=False))

    # 4. 儲存 CSV 與 SQLite
    save_to_csv(df)
    save_to_db(df)


if __name__ == "__main__":
    main()
