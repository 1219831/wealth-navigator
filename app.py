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
st.set_page_config(page_title="WealthNav PRO", layout="wide", page_icon="📈")

# --- 2. API連携 (エラー詳細完全開示) ---
@st.cache_resource
def init_ai():
    try:
        if "GEMINI_API_KEY" not in st.secrets: return None, "API Key Missing in Secrets"
        genai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return genai.GenerativeModel("gemini-1.5-flash"), None
    except Exception as e: return None, str(e)

model, err = init_ai()

# --- 3. データ処理 (計算ロジック徹底強化) ---
conn = st.connection("gsheets", type=GSheetsConnection)
raw = conn.read(spreadsheet=URL, ttl=0)
if raw.empty: st.error("Spreadsheet is empty."); st.stop()

df = raw.copy()
df["日付"] = pd.to_datetime(df["日付"])
df = df.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)

# --- 4. 資産解析 ---
L = df.iloc[-1]
T = L["総資産"]
now = datetime.now()

# 収支計算 (0回避・時系列集計)
try:
    d_gain = T - df.iloc[-2]["総資産"] if len(df) > 1 else 0
    m_start = df[df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_gain = T - m_start.iloc[0]["総資産"] if not m_start.empty else 0
    lm_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_start = (lm_end - pd.DateOffset(months=1))
    lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end)]
    p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0
except: d_gain = m_gain = p_gain = 0

# --- 5. メインダッシュボード (順序：総資産→今日→今月→先月) ---
st.title("📈 Wealth Navigator PRO")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("💰 総資産", f"¥{int(T):,}")
    st.caption(f"┣ 現物時価: ¥{int(L['現物時価総額']):,}")
    st.caption(f"┣ 信用損益: ¥{int(L['信用評価損益']):+,}")
    st.caption(f"┗ 買付余力: ¥{int(L['現物買付余力']):,}")

with c2:
    st.metric("📅 今日の収支", f"¥{int(d_gain):+,}")
    st.write(f"1億まで: ¥{
