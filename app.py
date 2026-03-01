import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav Pro", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Error")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ取得と収支計算 ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
except:
    pass

# --- 4. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    L = df.iloc[-1]  # 最新
    T = L['総資産']
    
    # --- 📊 収支状況の算出 (本日・今月・先月) ---
    # 本日収支 (前日比)
    day_diff = T - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    # 今月収支 (月初比)
    this_month_start = df[df['日付'] >= datetime.now().replace(day=1)].iloc[0]['総資産']
    month_diff = T - this_month_start
    # 先月収支
    last_month_end = df[df['日付'] < datetime.now().replace(day=1)]
    prev_month_diff = last_month_end.iloc[-1]['総資産'] - last_month_end.iloc[0]['総資産'] if not last_month_end.empty else 0

    # A. 資産ダッシュボード
    st.subheader("📊 資産状況 & 収支")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(T):,}", f"{int(day_diff):+,}")
        st.caption(f"┣ 現物: ¥{int(L['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(L['信用評価損益']):+,}")
        st.caption(f"┗ 余力: ¥{int(L['現物買付余力']):,}")
    with c2:
        st.metric("今月の収支", f"¥{int(month_diff):+,}")
        st.metric("先月の収支", f"¥{int(prev_month_diff):+,}")
    with c3:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.metric("目標達成率", f"{T/GOAL:.4%}")
    st.progress(max(0.0, min(float(T / GOAL), 1.0)))

    # --- 💎 参謀本部：銘柄・イベント直撃ボード ---
    st.divider()
    st.subheader("⚔️ 参謀本部：明日の決戦指令")
    
    # ボスの今の状況をAIに伝える
    status_msg = f"総資産{T}円、信用損益{
