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
st.set_page_config(page_title="WealthNav PRO", layout="wide")

# --- 2. API連携 ---
try:
    gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
    model = gai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API設定エラー"); st.stop()

# --- 3. データ取得 & 洗浄 ---
conn = st.connection("gsheets", type=GSheetsConnection)
raw = conn.read(spreadsheet=URL, ttl=0)
if raw.empty: st.stop()

df = raw.copy()
df["日付"] = pd.to_datetime(df["日付"])

# ★数値列の洗浄：カンマや¥を消して数値化
cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
for c in cols:
    if c in df.columns:
        df[c] = df[c].astype(str).replace('[,¥]', '', regex=True)
        df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0).astype(int)

df = df.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)

# --- 4. 資産解析 ---
L = df.iloc[-1]
T = int(L["総資産"])
M = int(L["信用評価損益"])
S = int(L["現物時価総額"])
C = int(L["現物買付余力"])
now = dt.now()

# 収支計算
d_g, m_g, p_g = 0, 0, 0
try:
    if len(df) > 1: d_g = T - int(df.iloc[-2]["総資産"])
    m_s = df[df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    if not m_s.empty: m_g = T - int(m_s.iloc[0]["総資産"])
    le = now.replace(day=1, hour=0, minute=0, second=0)
    ls = (le - pd.DateOffset(months=1))
    ld = df[(df["日付"] >= ls) & (df["日付"] < le)]
    if not ld.empty: p_g = int(ld.iloc[-1]["総資産"]) - int(ld.iloc[0]["総資産"])
except: pass

# --- 5. メイン画面 (総資産 -> 今日 -> 今月 -> 先月) ---
st.title("🚀 Wealth Navigator PRO")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("💰 総資産", "¥ " + "{:,}".format(T))
    st.caption("┣ 現物: ¥ " + "{:,}".format(S))
    st.caption("┣ 信用: ¥ " + "{:,}".format(M))
    st.caption("┗ 余力: ¥ " + "{:,}".format(C))

with c2:
    st.metric("📅 今日の収支", "¥ " + "{:,}".format(d_g))
    st.write("目標まで: ¥ ", "{:,}".format(GOAL - T))

with c3:
    st.metric("🗓️ 今月の収支", "¥ " + "{:,}".format(m_g))
    st.progress(max(0.0, min(float(T/GOAL), 1.0)))

with c4:
    st.metric("⏳ 先月の収支", "¥ " + "{:,}".format(p_g))
    st.write("達成率: ", "{:.4%}".format(T/GOAL))

# --- 6. 参謀本部 ---
st.divider()
p = "投資参謀として、信用損益 " + str(M) + "円のボスに、最新の市場動向を踏まえた戦略を120字で指令せよ。"
try:
    res = model.generate_content(p)
    if res.text: st.info(res.text)
except: st.warning("指令：ボラ警戒。余力を維持せよ。")

# --- 7. グラフ ---
st.divider()
def draw(d, k):
    d["MA5"] = d["総資産"].rolling(5).mean()
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=d["日付"], y=d["総資産"], name="資産", fill="tozeroy", line=dict(color="#007BFF")))
    fig.add_trace(go.Scatter(x=d["日付"], y=d["MA5"], name="5日線", line=dict(dash="dot", color="#FFA500")))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(tickformat=",.0f"))
    st.plotly_chart(fig, use_container_width=True, key=k)

mode = st.radio("期間:", ["日次", "週次", "月次"], horizontal=True)
if mode == "日次": draw(df, "d")
elif mode == "週次": draw(df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
else: draw(df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

# --- 8. 更新 (3枚解析) ---
st.divider()
ups = st.
