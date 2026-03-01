import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.express as px
import plotly.graph_objects as go

# --- 設定 ---
GOAL_AMOUNT = 100000000 
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator", page_icon="🚀", layout="wide")

# --- 準備1: Gemini API ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    st.stop()

st.title("🚀 Wealth Navigator")

# --- 準備2: Google Sheets接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の数値抽出。{"cash": 123, "spot": 456, "margin": -789}のJSONのみ。"""
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception: return None

# ==========================================================
# 処理1: データ読み込みとダッシュボード表示
# ==========================================================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df_raw.empty:
        # 時刻を除去して日付のみにする
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values(by='日付').reset_index(drop=True)
        
        latest = df.iloc[-1]
        total = latest['総資産']
        
        # 指標計算
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_month_df = df[(df['日付'].dt.year == latest['日付'].year) & (df['日付'].dt.month == latest['日付'].month)]
        this_month_diff = total - this_month_df.iloc[0]['総資産'] if not this_month_df.empty else 0
        
        last_month_date = latest['日付'].replace(day=1) - pd.Timedelta(days=1)
        last_month_df = df[(df['日付'].dt.year == last_month_date.year) & (df['日付'].dt.month == last_month_date.month)]
        last_month_diff = last_month_df.iloc[-1]['総資産'] - last_month_df.iloc[0]['総資産'] if not last_month_df.empty else 0

        # メトリックス
        st.subheader("📊 資産状況ダッシュボード")
        cols = st.columns(5)
        cols[0].metric("現在の総資産", f"¥{int(total):,}")
        cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        cols[2].metric("前日比(前回比)", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        cols[3].metric(f"{last_month_date.month}月の収支", f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        cols[4].metric(f"{latest
