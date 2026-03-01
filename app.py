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
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav", page_icon="📈", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API接続エラー。Secretsを確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. AIマーケット要約 (日曜夜の戦略モード) ---
@st.cache_data(ttl=3600)
def get_market_briefing(date_str):
    # AIが日曜日でも「明日の戦略」を語るための専用プロンプト
    prompt = f"""
    今日は {date_str} (日曜日の夜) です。明日の日本市場再開に向けた投資戦略をまとめて。
    1. 【先週末の振り返り】: 米国市場の最終動向。
    2. 【明日の日本株展望】: 寄り付きの注目点と、今週の主要決算予定。
    3. 【🚨最重要チェック】: 相場を左右する今週の経済指標。
    ※3行で、簡潔な日本語で出力してください。
    """
    try:
        res = model.generate_content(prompt)
        if res and res.text:
            return res.text
        return "💡 明朝の寄り付きに向け、先週末の米株終値と今週の決算スケジュールを再確認しましょう。"
    except:
        return "🚨 AI接続待機中。今週は国内主要企業の決算発表が相次ぐため、ボラティリティに注意です。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("データ接続中...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データ正規化
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    total = latest['総資産']
    
    # 1. 資産ダッシュボード (最上段
