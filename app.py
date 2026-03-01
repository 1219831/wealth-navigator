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

# --- 2. 外部連携設定 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# セッション状態管理
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能（OCR & 投資ダイジェスト） ---
def perform_ai_analysis(up_file):
    p = '松井証券の数値抽出。{"cash": 100, "spot": 200, "margin": -50} の形式。'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except Exception:
        return None

@st.cache_data(ttl=86400)
def get_investment_briefing(date_key):
    # AIが回答しやすいよう、客観的な情報の整理を依頼するプロンプト
    prompt = f"""
    今日は {date_key} です。プロの投資家向けに本日の市場予定を日本語でまとめてください。
    1. 国内決算：本日または週明けの主な注目企業（3〜5社）と発表数。
    2. 重要指標：日本、米国、欧州、中国の順で、直近の重要経済指標（PMI、金利、雇用関連など）。
    3. 🚨注目イベント：相場変動要因になりそうな最重要項目を太字で。
    ※投資助言ではなく、公開カレンダーの要約として出力してください。
    """
    try:
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text
        return "🚨 情報取得制限：最新のマーケットニュースを確認してください。"
    except Exception:
        return "💡 マーケット情報は準備中です。更新ボタンを試してください。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except Exception:
    st.warning("スプレッドシートの接続を確認中...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データ加工（破壊防止）
    df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld = latest['日付']
    total = latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    lm_target = ld.replace(day=1) - timedelta(days=1)
    lm_df = df[df['日付'].dt.to_period('M') == lm_target.to_period('M')]
    lm_diff = lm_df.iloc[-1]['総資産
