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

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部連携設定 (404対策: モデルパスを厳密に指定) ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 2026年現在の安定エンドポイントを使用
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"API初期化エラー: {e}")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能（OCR解析 & マーケット要約） ---
def perform_ai_analysis(up_file):
    p = '抽出項目：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except: return None

@st.cache_data(ttl=86400) # 1日キャッシュ
def get_market_briefing(date_str):
    # 日曜日でも週明けの予定を出すようにプロンプトを最適化
    prompt = f"""
    今日は {date_str} です。投資家が明日の市場再開に備えるための情報を日本語でまとめてください。
    1. 国内決算：今週発表予定の主要銘柄（3〜5社）と件数。
    2. 重要指標：日・米・欧・中で今週発表される重要指標（雇用統計、PMI、CPI等）。
    3. 🚨注目イベント：相場の転換点になりそうな超重要イベントを太字で強調。
    ※投資助言ではなく、公開情報のスケジュールまとめとして出力してください。
    """
    try:
        response = model.generate_content(prompt)
        if response and hasattr(response, 'text'):
            return response.text
        return "🚨 情報の生成に失敗しました。リロードしてください。"
    except Exception:
        # 404やタイムアウト時のフォールバック
        return
