import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="保有資産管理シート", layout="wide")

# --- 2. 司令部接続（AI & データ同期） ---
@st.cache_resource
def init_system():
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            return None
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        # 最新の1.5 Flashモデルを使用
        return gai.GenerativeModel("gemini-1.5-flash")
    except:
        return None

def fetch_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
        if df is None or df.empty: return None

        # データ洗浄
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except:
        return None

model = init_system()
df = fetch_data()

# --- 3. 投資解析 ---
if df is not None and not df.empty:
    # 総資産が0より大きい最新データを取得
    valid_df = df[df["総資産"] > 0]
    if valid_df.empty: 
        valid_df = df # 全データが0の場合はそのまま利用（エラー回避）
        
    L = valid_df.iloc[-1]
    T_total = int(L["総資産"])
    P_margin = int(L["信用評価損益"])
    now = dt.now()

    # 収支計算
    d_gain = T_total - valid_df.iloc[-2]["総資産"] if len(valid_df) > 1 else 0
    m_start = valid_df[valid_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_gain = T_total - m_start.iloc[0]["総資産"] if not m_start.empty else 0
    lm_start = (now.replace(day=1) - relativedelta(months=1))
    lm_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end) & (df["総資産"] > 0)]
    p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # --- 4. メイン表示 ---
    st.title("🚀 Wealth Navigator PRO")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥ " + "{:,}".format(T_total))
        with st.expander("内訳を表示"):
            st.write("┣ 現物時価: ¥ " + "{:,}".format(int(L["現物時価総額"])))
            st.write("┣ 信用損益: ¥ " + "{:,}".format(P_margin))
            st.write("┗ 買付余力: ¥ " + "{:,}".format(int(L["現物買付余力"])))
    
    with c2: st.metric("📅 今日の収支", "¥ " + "{:,}".format(int(d_gain)))
    with c3: st.metric("🗓️ 今月の収支", "¥ " + "{:,}".format(int(m_gain)))
    with c4: st.metric("⏳ 先月の収支", "¥ " + "{:,}".format(int(p_gain)))

    st.progress(max(0.0, min(float(T_total/GOAL), 1.0)), text="目標達成率: " + "{:.4%}".format(T_total/GOAL))

    # --- 5. 参謀本部：市場イベント
