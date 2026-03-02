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

st.set_page_config(page_title="Wealth Nav Pro", layout="wide", page_icon="📈")

# --- 2. API連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API設定エラー")
    st.stop()

# --- 3. データ取得 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        raw = conn.read(spreadsheet=URL, ttl=0)
        if raw.empty: return None
        raw["日付"] = pd.to_datetime(raw["日付"], errors="coerce")
        df = raw.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)
        return df
    except:
        return None

df = load_data()

# --- 4. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if df is not None and not df.empty:
    L = df.iloc[-1]
    T = L["総資産"]
    M = L["信用評価損益"]
    now = datetime.now()
    
    # 収支計算 (今日・先月・今月)
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

    # A. 資産ダッシュボード (順序厳守)
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    
    with c1:
        st.metric("今日の収支", "¥" + str(int(d_g)))
        st.write("総資産:", "¥" + str(int(T)))
    with c2:
        st.metric("先月の収支", "¥" + str(int(p_g)))
        st.write("信用損益:", "¥" + str(int(M)))
    with c3:
        st.metric("今月の収支", "¥" + str(int(m_g)))
        st.write("買付余力:", "¥" + str(int(L["現物買付余力"])))
    with c4:
        st.metric("1億円まで", "¥" + str(int(GOAL - T)))
        st.write("達成率:", str(round(T/GOAL*100, 4)) + "%")
        st.progress(max(0.0, min(float(T/GOAL), 1.0)))

    # B. 参謀本部 (断線してもエラーにならない構造)
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    st.success("📈 **【3/3 注目】**: 日本市場寄り付き / 米国指標の波及警戒")
    
    p_t = "投資参謀として、信用損益 " + str(M) + "円のボスに、明日の具体的行動を120字で指令せよ。"
    try:
        res = model.generate_content(p_t)
        # 変数に入れてから表示することで、クォート断線を回避
        msg_txt = res.text
        st.info(msg_txt)
    except:
        st.warning("参謀指令：市場のボラティリティに備え、余力を維持せよ。")

    # C. グラフ (ID重複を避ける短いキー)
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    tabs = st.tabs(["日次", "週次", "月次"])
    def pf(data):
        fig = go.Figure(go.Scatter(x=data["日付"], y=data["総資産"], fill="tozeroy
