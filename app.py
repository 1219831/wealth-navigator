import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 & UI保持 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav PRO", layout="wide")

# --- 2. 司令部接続 ---
@st.cache_resource
def init():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except: return None

def fetch():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
        df.columns = [c.strip() for c in df.columns]
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        for c in ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]:
            df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except: return None

model, df = init(), fetch()

# --- 3. メイン表示 (ボスお気に入りUI) ---
st.title("🚀 保有資産管理シート")

if df is not None:
    v_df = df[df["総資産"] > 0]
    if v_df.empty: v_df = df
    L = v_df.iloc[-1]
    T, M, S, C = int(L["総資産"]), int(L["信用評価損益"]), int(L["現物時価総額"]), int(L["現物買付余力"])
    now = dt.now()

    # 収支計算
    d_g = T - v_df.iloc[-2]["総資産"] if len(v_df) > 1 else 0
    m_s = v_df[v_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_g = T - m_s.iloc[0]["総資産"] if not m_s.empty else 0
    lm_s = (now.replace(day=1) - relativedelta(months=1))
    lm_e = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_s) & (df["日付"] < lm_e) & (df["総資産"] > 0)]
    p_g = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", f"¥ {T:,}")
        with st.expander("内訳を表示"):
            st.write(f"┣ 現物: ¥{S:,}\n┣ 信用: ¥{M:+,}\n┗ 余力: ¥{C:,}")
    c2.metric("📅 今日の収支", f"¥ {int(d_g):+,}")
    c3.metric("🗓️ 今月の収支合計", f"¥ {int(m_g):+,}")
    c4.metric("⏳ 先月の収支合計", f"¥ {int(p_g):+,
