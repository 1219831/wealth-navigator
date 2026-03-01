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

# --- 2. 外部連携 (AI Studioでの成功を確認済み) ---
try:
    # SecretsからAPIキーを読み込み（前後の空白を除去）
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    # AI Studioと同じモデル名を指定
    model = genai.GenerativeModel('gemini-1.5-flash')
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

@st.cache_data(ttl=3600)
def get_market_briefing(d_str):
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    if is_weekend:
        p = f"今日は{d_str}(週末)。先週の市場振り返りと明日からの指標・注目予定を日本語で短くまとめて。"
    else:
        p = f"今日は{d_str}(平日)。昨晩の米株、本日の日本株見通しを日本語で短くまとめて。"
    try:
        res = model.generate_content(p)
        return res.text if res.text else "情報の取得制限中"
    except:
        return "💡 マーケット情報を整理中。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データの徹底的なクレンジング
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    # 1. ダッシュボード
    st.subheader("📊 資産状況")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
    cols
