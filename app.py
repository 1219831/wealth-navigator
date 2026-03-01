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
    now = datetime.now()
    
    # --- 収支計算 (徹底シミュレーション) ---
    d_gain, m_gain, p_gain = 0, 0, 0
    try:
        # 今日の収支 (前日比)
        if len(df) > 1: d_gain = T - df.iloc[-2]['総資産']
        # 今月の収支 (月初比)
        this_m_start = df[df['日付'] >= now.replace(day=1, hour=0, minute=0, second=0)]
        if not this_m_start.empty: m_gain = T - this_m_start.iloc[0]['総資産']
        # 先月の収支 (先月の初日から末日まで)
        last_m_end_date = now.replace(day=1, hour=0, minute=0, second=0)
        last_m_start_date = (last_m_end_date - pd.DateOffset(months=1))
        last_m_data = df[(df['日付'] >= last_m_start_date) & (df['日付'] < last_m_end_date)]
        if not last_m_data.empty: p_gain = last_m_data.iloc[-1]['総資産'] - last_m_data.iloc[0]['総資産']
    except: pass

    # A. 資産ダッシュボード (順序：今日 -> 先月 -> 今月)
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        st.metric("今日の収支", f"¥{int(d_gain):+d}")
        st.caption("┣ 総資産: ¥" + f"{int(T):,}")
        st.caption("┗ 信用: ¥" + f"{int(M):+,}")
    with c2:
        st.metric("先月の収支", f"¥{int(p_gain):+,}")
    with c3:
        st.metric("今月の収支", f"¥{int(m_gain):+,}")
    with c4:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.caption(f"達成率: {T/GOAL:.4%}")
    st.progress(max(0.0, min(float(T / GOAL), 1.0)))

    # --- 💎 参謀本部 (イベント & ジェミニの一言) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    st.success("📈 **【3/2 予定】**: 伊藤園(2593)・ピープル(7865)決算 / 24時 米ISM製造業景況指数")
    
    P = "信用損益 " + str(M) + "円のボスに、3/2の伊藤園・ピープル決算と米ISMの影響、明日寄り付きの行動を120字で指令せよ。"
    try:
        res = model.generate_content(P)
        if res.text: st.info("💡 **参謀Geminiの進言**: " + res.text)
    except:
        st.warning("🚨 **参謀の緊急指令**: 深夜の米ISMによる円高リスクを警戒。余力維持を最優先し、現物の指値を再確認せよ。")

    # B. 資産トレンドグラフ (期間切り替え復活)
    st.divider()
    st.write("### 🏔️ 資産トレンド推移")
    tab1, tab2, tab3 = st.tabs(["日次 (Daily)", "週次 (Weekly)", "月次 (Monthly)"])
    
    def plot_graph(data, title):
        fig = go.Figure(go.Scatter(x=data['日付'], y=data['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    with tab1:
        st.plotly_chart(plot_graph(df, "Daily"), use_container_width=True)
    with tab2:
        df_w = df.resample('W', on='日付').last().reset_index().dropna()
        st.plotly_chart(plot_graph(df_w, "Weekly"), use_container_width=True)
    with tab3:
        df_m = df.resample('M', on='日付').last().reset_index().dropna()
        st.plotly_chart(plot_graph(df_m, "Monthly"), use_container_width=True)

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
