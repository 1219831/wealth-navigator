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
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("API設定エラー")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI分析エンジン ---
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
    p = f"今日は{d_str}。先週末の米株日本株振り返り、明日からの国内決算、重要指標、🚨重要イベントを日本語で簡潔にまとめて。投資助言は不要。"
    try:
        res = model.generate_content(p)
        return res.text if res.text else "情報の取得を制限中"
    except: return "整理中..."

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 収支計算（断線対策：事前に文字列化）
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    # 表示用のラベルと値を変数化
    m_val = f"¥{int(total):,}"
    d_label = f"{ld.month}月収支"
    d_val = f"¥{int(tm_diff):,}"
    d_delta = f"{int(tm_diff):+,}"

    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("現在の総資産", m_val)
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(d_label, d_val, delta=d_delta) # 短文化で断線防止
    cols[4].metric("目標達成率", f"{total/GOAL:.2%}")
    
    # 進捗バー
    prg_v = max(0.0, min(float(total / GOAL), 1.0))
    st.progress(prg_v)

    # AIマーケット情報
    st.divider()
    st.subheader("🗓️ 週末マーケット・ダイジェスト")
    today_key = datetime.now().strftime('%Y-%m-%d')
    st.markdown(get_market_briefing(today_key))

    # グラフセクション
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc: st.write("
