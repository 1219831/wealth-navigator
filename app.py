import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go

# --- 1. システム設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav Pro", layout="wide", page_icon="📈")

# --- 2. API連携 (404/アクセスエラー対策) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    # 接続を安定させるため、複数のモデル名候補を試行するロジック
    model_name = "gemini-1.5-flash" 
    model = genai.GenerativeModel(model_name)
except Exception as e:
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
    
    # 収支計算 (本日・先月・今月)
    d_gain, m_gain, p_gain = 0, 0, 0
    try:
        if len(df) > 1: d_gain = T - df.iloc[-2]["総資産"]
        m_start = df[df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
        if not m_start.empty: m_gain = T - m_start.iloc[0]["総資産"]
        # 先月計算
        lm_end = now.replace(day=1, hour=0, minute=0, second=0)
        lm_start = (lm_end - pd.DateOffset(months=1))
        lm_data = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end)]
        if not lm_data.empty: p_gain = lm_data.iloc[-1]["総資産"] - lm_data.iloc[0]["総資産"]
    except: pass

    # A. 資産ダッシュボード (収支順序: 今日 -> 先月 -> 今月)
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    
    with c1:
        st.metric("今日の収支", f"¥{int(d_gain):+d}")
        st.write("総資産:", f"¥{int(T):,}")
    with c2:
        st.metric("先月の収支", f"¥{int(p_gain):+,}")
        st.write("信用損益:", f"¥{int(M):+,}")
    with c3:
        st.metric("今月の収支", f"¥{int(m_gain):+,}")
        st.write("買付余力:", f"¥{int(L['現物買付余力']):,}")
    with c4:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.write("達成率:", f"{T/GOAL:.4%}")
        st.progress(max(0.0, min(float(T/GOAL), 1.0)))

    # B. 参謀本部
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    st.success("📈 **【3/3 注目】**: 昨日の伊藤園・ピープル決算反映 / 今夜の注目指標")
    
    p_text = "投資参謀として、信用損益 " + str(M) + "円のボスに、明日の寄り付き行動を120字で指令せよ。"
    try:
        res = model.generate_content(p_text)
        if res.text: st.info("💡 **参謀
