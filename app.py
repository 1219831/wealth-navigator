import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
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

# --- 3. データ取得 ---
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
    L = df.iloc[-1]
    T = L['総資産']
    M = L['信用評価損益']
    
    # 収支計算 (安全策)
    d_gain, m_gain, p_gain = 0, 0, 0
    try:
        if len(df) > 1: d_gain = T - df.iloc[-2]['総資産']
        this_m = df[df['日付'] >= datetime.now().replace(day=1)]
        if not this_m.empty: m_gain = T - this_m.iloc[0]['総資産']
        last_m = df[df['日付'] < datetime.now().replace(day=1)]
        if not last_m.empty: p_gain = last_m.iloc[-1]['総資産'] - last_m.iloc[0]['総資産']
    except:
        pass

    # A. 資産ダッシュボード
    st.subheader("📊 資産状況 & 収支")
    c1, c2, c3 = st.columns([1.2, 1, 1])
    with c1:
        st.metric("総資産", f"¥{int(T):,}", f"{int(d_gain):+d}")
        st.caption("┣ 現物: ¥" + f"{int(L['現物時価総額']):,}")
        st.caption("┣ 信用: ¥" + f"{int(M):+,}")
        st.caption("┗ 余力: ¥" + f"{int(L['現物買付余力']):,}")
    with c2:
        st.metric("今月収支", f"¥{int(m_gain):+,}")
        st.metric("先月収支", f"¥{int(p_gain):+,}")
    with c3:
        st.metric("目標まで", f"¥{int(GOAL - T):,}")
        st.metric("達成率", f"{T/GOAL:.4%}")
    st.progress(max(0.0, min(float(T / GOAL), 1.0)))

    # --- 💎 参謀本部 (銘柄・イベント) ---
    st.divider()
