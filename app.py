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

# セッション状態の保持
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# AI解析エンジン
def perform_ai_analysis(up_file):
    prompt = """松井証券の数値抽出。{"cash": 100, "spot": 200, "margin": -50} の形式で。"""
    try:
        img = Image.open(up_file)
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
except Exception:
    st.warning("スプレッドシートの読み込みに失敗しました。")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    try:
        # データの整形
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
        
        latest = df.iloc[-1]
        l_date = latest['日付']
        total = latest['総資産']
        
        # 内訳
        s_v = latest['現物時価総額']
        m_v = latest['信用評価損益']
        c_v = latest['現物買付余力']
        
        # 指標
        daily = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_mo = df[df['日付'].dt.to_period('M') == l_date.to_period('M')]
        this_mo_diff = total - this_mo.iloc[0]['総資産']
        
        last_mo_day = l_date.replace(day=1) - timedelta(days=1)
        last_mo_df = df[df['日付'].dt.to_period('M') == last_mo_day.to_period('M')]
        last_mo_diff = last_mo_df.iloc[-1]['総資産'] - last_mo_df.iloc[0]['総資産'] if not last_mo_df.empty else 0

        # メトリックス
        st.subheader("📊 資産状況ダッシュボード")
        m_cols = st.columns([1.2, 1, 1, 1, 1])
