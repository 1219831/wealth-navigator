import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# 1. 基本設定
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav", layout="wide")

# 2. API連携
try:
    gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
    model = gai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API Error"); st.stop()

# 3. データ処理
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = conn.read(spreadsheet=URL, ttl=0)
if df_raw.empty: st.stop()
df = df_raw.copy()
df["日付"] = pd.to_datetime(df["日付"])
df = df.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)

# 4. メイン画面
st.title("🚀 Wealth Navigator PRO")
L = df.iloc[-1]; T = L["総資産"]; M = L["信用評価損益"]; now = dt.now()

# 収支計算
d_g, m_g, p_g = 0, 0, 0
try:
    if len(df) > 1: d_g = T - df.iloc[-2]["総資産"]
    m_s = df[df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    if not m_s.empty: m_g = T - m_s.iloc[0]["総資産"]
    le = now.replace(day=1, hour=0, minute=0, second=0)
    ls = (le - pd.DateOffset(months=1))
    ld = df[(df["日付"] >= ls) & (df["日付"] < le)]
    if not ld.empty: p_g = ld.iloc[-1]["総資産"] - ld.iloc[0]["総資産"]
except: pass

# A. 資産ダッシュボード (順序: 今日→先月→今月)
st.subheader("📊 収支成績")
c1, c2, c3, c4 = st.columns(4)
c1.metric("今日の収支", f"
