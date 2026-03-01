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

# --- 2. 外部連携設定 (API 404対策) ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 2026年現在の最も安定したモデルパスを使用
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"API設定を確認してください: {e}")
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
def get_market_briefing(date_str):
    # AIが拒否しないよう「週明けの見通し」をマイルドに依頼
    prompt = f"今日は{date_str}（日曜日）です。明日からのマーケットで投資家が注目すべき「国内決算」「重要経済指標」「🚨注目イベント」を日本語で簡潔にまとめてください。"
    try:
        response = model.generate_content(prompt)
        return response.text if response.text else "情報の取得を制限中"
    except:
        return "💡 現在、マーケット情報を整理中です。明日朝の寄り付きにご注目ください。"

# --- 4. データ読み込み & 強制クリーニング ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except Exception:
    st.warning("スプレッドシートが見つかりません。")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    try:
        # データの型を徹底的に正規化
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df_raw = df_raw.dropna(subset=['日付'])
        df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
        
        latest = df.iloc[-1]
        ld, total = latest['日付'], latest['総資産']
        
        # 指標計算
        d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
        tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0

        # ダッシュボード表示
        st.subheader("📊 資産状況ダッシュボード")
        m_cols = st.columns([1.2, 1, 1, 1, 1])
        with m_cols[0]:
            st.metric("現在の総資産", f"¥{int(total):,}")
            st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
            st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
            st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
        
        m_cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
        m_cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
        m_cols[3].metric(f"{ld.month}月収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
        m_cols[4].metric("目標達成率", f"{total/GOAL:.2%}")
        
        st.progress(max(0.0, min(float(total / GOAL), 1.0)))

        # AIマーケットダイ
