import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL_AMOUNT = 100000000 
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部サービス連携 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# AI解析エンジン
def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の資産状況から数値（現物買付余力、現物時価総額、信用評価損益）を抽出し、{"cash": 100, "spot": 200, "margin": -50} の形式で出力。"""
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# --- 4. メインロジック ---
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values(by='日付').drop_duplicates(subset='日付', keep='last').reset_index(drop=True)
        
        latest = df.iloc[-1]
        total = latest['総資産']
        
        # 内訳データの取得（ボス指定の名称に紐付け）
        spot_val = latest['現物時価総額']
        margin_val = latest['信用評価損益']
        cash_val = latest['現物買付余力']
        
        # 指標の計算
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_month_start = df[df['日付'] >= latest['日付'].replace(day=1)]
        this_month_diff = total - this_month_start.iloc[0]['総資産'] if not this_month_start.empty else 0
        
        last_month_end = latest['日付'].replace(day=1) - timedelta(days=1)
        last_month_data = df[df['日付'].dt.to_period('M') == last_month_end.to_period('M')]
        last_month_diff = last_month_data.iloc[-1]['総資産'] - last_month_data.iloc[0]['総資産'] if not last_month_data.empty else 0

        # --- 5. ダッシュボード表示 ---
        st.title("🚀 Wealth Navigator PRO")
        
        # レイアウト：総資産＆内訳エリア と その他指標
        st.subheader("📊 資産状況ダッシュボード")
        
        # 指標表示用の5列
        m_cols = st.columns([1.2, 1, 1, 1, 1])
        
        with m_cols[0]:
            st.metric("現在の総資産", f"¥{int(total):,}")
            # 内訳を参考情報として表示
            st.caption(f"┣ 現物資産時価総額: ¥{int(spot_val):,}")
            st.caption(f"┣ 信用保有資産損益: ¥{int(margin_val):+,}")
            st.caption(f"┗ 現物取得余力: ¥{int(cash_val):,}")

        m_cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        m_cols[2].metric("前日(前回)比", f"¥{
