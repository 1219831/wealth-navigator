import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav", layout="wide")

# --- 2. API連携 ---
try:
    gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
    model = gai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API設定エラー"); st.stop()

# --- 3. データ処理 ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = conn.read(spreadsheet=URL, ttl=0)
if df_raw.empty: st.stop()
df = df_raw.copy()
df["日付"] = pd.to_datetime(df["日付"])
df = df.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)

# --- 4. メイン画面 ---
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

# --- A. 資産ダッシュボード (順序厳守: 今日 -> 先月 -> 今月) ---
st.subheader("📊 収支成績 & 資産状況")
c1, c2, c3, c4 = st.columns(4)

# 今日の収支
c1.metric("今日の収支", "¥" + str(int(d_g)))
c1.write("総資産: ¥" + str(int(T)))

# 先月の収支
c2.metric("先月の収支", "¥" + str(int(p_g)))
c2.write("信用損益: ¥" + str(int(M)))

# 今月の収支
c3.metric("今月の収支", "¥" + str(int(m_g)))
c3.write("買付余力: ¥" + str(int(L["現物買付余力"])))

# 目標達成
c4.metric("1億円まで", "¥" + str(int(GOAL - T)))
prog = max(0.0, min(float(T/GOAL), 1.0))
st.progress(prog)

# --- B. 参謀本部 ---
st.divider()
st.subheader("⚔️ 参謀本部")
st.success("📈 3/3注目: 伊藤園・ピープル決算反応 / 今夜米ISM指数")
prompt = "信用損益" + str(M) + "円のボスへ、明日寄り付きの行動を100字で指令せよ。"
try:
    res = model.generate_content(prompt)
    if res.text: st.info(res.text)
except: st.warning("指令：余力維持を最優先せよ。")

# --- C. 期間切替グラフ ---
