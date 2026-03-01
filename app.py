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

# --- 2. 外部連携 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 接続の安定性を高めるフルパス指定
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"API設定エラー: {e}")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能 ---
def perform_ai_analysis(up_file):
    p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except: return None

@st.cache_data(ttl=3600)
def get_market_briefing(date_str):
    prompt = f"""
    今日は {date_str} です。以下の投資情報を日本語でまとめてください。
    ■国内決算：本日の注目銘柄と発表件数
    ■重要指標：日・米・欧・中の経済指数
    ■特記事項：🚨特に重要なイベントは太字で強調。
    ※投資助言ではなく客観的な予定表として出力してください。
    """
    try:
        response = model.generate_content(prompt)
        return response.text if response.text else "情報の取得を制限中"
    except Exception as e:
        return f"💡 準備中 (API Wait: {str(e)[:20]})"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("シート接続待ち...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 1. ダッシュボード
    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    # 指標計算（安全な複数行処理）
    d_diff = 0
    if len(df) > 1:
        d_diff = total - df.iloc[-2]['総資産']
    
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    lm_target = ld.replace(day=1) - timedelta(days=1)
    lm_df = df[df['日付'].dt.to_period('M') == lm_target.to_period('M')]
    lm_diff = lm_df.iloc[-1]['総資産'] - lm_df.iloc[0]['総資産'] if not lm_df.empty else 0

    cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{lm_target.month}月収支", f"¥{int(lm_diff):,}", delta=f"{int(lm_diff):+,}")
    cols[4].metric(
