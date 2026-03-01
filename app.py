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
    
    # --- 収支計算 ---
    d_gain, m_gain, p_gain = 0, 0, 0
    now = datetime.now()
    try:
        if len(df) > 1: d_gain = T - df.iloc[-2]['総資産']
        this_m_df = df[df['日付'] >= now.replace(day=1, hour=0, minute=0, second=0)]
        if not this_m_df.empty: m_gain = T - this_m_df.iloc[0]['総資産']
        last_m_end = df[df['日付'] < now.replace(day=1, hour=0, minute=0, second=0)]
        if not last_m_end.empty:
            p_start = last_m_end[last_m_end['日付'] >= (now.replace(day=1) - pd.DateOffset(months=1))]
            if not p_start.empty: p_gain = last_m_end.iloc[-1]['総資産'] - p_start.iloc[0]['総資産']
    except: pass

    # A. 資産ダッシュボード (本日・今月・先月の収支)
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3 = st.columns([1.2, 1.2, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(T):,}", f"{int(d_gain):+d}")
        st.caption("┣ 現物: ¥" + f"{int(L['現物時価総額']):,}")
        st.caption("┣ 信用損益: ¥" + f"{int(M):+,}")
        st.caption("┗ 余力: ¥" + f"{int(L['現物買付余力']):,}")
    with c2:
        st.metric("今月の収支", f"¥{int(m_gain):+,}")
        st.metric("先月の収支", f"¥{int(p_gain):+,}")
    with c3:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.metric("目標達成率", f"{T/GOAL:.4%}")
    st.progress(max(0.0, min(float(T / GOAL), 1.0)))

    # --- 💎 参謀本部 (イベント & ジェミニの一言) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    
    # 予定をまず固定表示
    st.success("📈 **【3/2 注目】**: 伊藤園(2593)・ピープル(7865)決算 / 24時 米ISM製造業景況指数")
    
    advice_container = st.container()
    
    # AIへの指示
    P = "投資家ボスの参謀として、信用損益 " + str(M) + "円 の状況を踏まえ、"
    P += "3/2の伊藤園・ピープル決算と米ISM指数が保有株に与える影響と、"
    P += "明日寄り付きの具体的なアクションを120字で指令せよ。"
    
    with advice_container:
        try:
            res = model.generate_content(P)
            if res.text:
                st.info("💡 **参謀Geminiの進言**: " + res.text)
        except:
            st.warning("🚨 **参謀の緊急指令**: 信用損益の悪化に備え、今夜のISMによる円高リスクを警戒。明日は余力維持を最優先し、現物の指値を再確認せよ。")

    # B. 資産トレンドグラフ (必ず表示)
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("データが読み込めません。")

# --- 5. 更新フォーム ---
st.divider()
up = st.file_uploader("資産スクショを選択", type=['png', 'jpg'])
if st.button("AI解析実行"):
    if up:
        with st.spinner('Analyzing...'):
            try:
                img = Image.open(up)
                res = model.generate_content(["抽出:{\"cash\":int,\"spot\":int,\"margin\":int}", img])
                st.write("解析結果:", res.text)
            except: st.error("Error")
