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
    api = st.secrets["GEMINI_API_KEY"].strip()
    gai.configure(api_key=api)
    model = gai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API Error")
    st.stop()

# --- 3. データ処理 ---
conn = st.connection("gsheets", type=GSheetsConnection)
def load():
    try:
        raw = conn.read(spreadsheet=URL, ttl=0)
        if raw.empty: return None
        raw["日付"] = pd.to_datetime(raw["日付"])
        return raw.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)
    except: return None

df = load()

# --- 4. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if df is not None:
    L = df.iloc[-1]
    T = L["総資産"]
    M = L["信用評価損益"]
    now = dt.now()

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

    # A. 資産ダッシュボード (今日 -> 先月 -> 今月)
    st.subheader("📊 収支成績 & 状況")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("今日の収支", f"¥{int(d_g):+}")
    c1.write(f"総資産: ¥{int(T):,}")
    
    c2.metric("先月の収支", f"¥{int(p_g):+}")
    c2.write(f"信用損益: ¥{int(M):+}")
    
    c3.metric("今月の収支", f"¥{int(m_g):+}")
    c3.write(f"余力: ¥{int(L['現物買付余力']):,}")
    
    c4.metric("1億円まで", f"¥{int(GOAL - T):,}")
    pct = T/GOAL
    c4.write(f"達成率: {pct:.4%}")
    st.progress(max(0.0, min(float(pct), 1.0)))

    # B. 参謀本部
    st.divider()
    st.subheader("⚔️ 参謀本部")
    st.success("📈 3/3: 寄り付き注意 / 伊藤園・ピープル決算反応 / 今夜米指標")
    
    p = f"投資参謀として信用損益{M}円のボスへ。明日寄り付きの具体的行動を100字で指令せよ。"
    try:
        res = model.generate_content(p)
        if res.text: st.info(res.text)
    except: st.warning("指令：ボラ増大に備え、余力維持を最優先せよ。")

    # C. グラフ (不具合対策: IDを極小化)
    st.divider()
    st.write("### 🏔️ トレンド")
    t1, t2, t3 = st.tabs(["日", "週", "月"])
    
    def fig(d):
        f = go.Figure(go.Scatter(x=d["日付"], y=d["総資産"],
