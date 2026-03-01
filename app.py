import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav", page_icon="📈", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Error")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. AI機能 ---
@st.cache_data(ttl=3600)
def get_market_briefing(d_str):
    is_weekend = datetime.now().weekday() >= 5
    p = f"今日は{d_str}。市場振り返りと今後の注目点を日本語で3行で。"
    try:
        res = model.generate_content(p)
        return res.text
    except: return "データ整理中..."

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("Sheet Wait...")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データクレンジング
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    total = latest['総資産']
    
    # 資産表示 (DeltaGeneratorエラー対策: 確実に値を埋める)
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    
    with c1:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物時価: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 買付余力: ¥{int(latest['現物買付余力']):,}")
    
    with c2:
        st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    
    with c3:
        pct = (total / GOAL) * 100
        st.metric("目標達成率", f"{pct:.3%}")
    
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # AIマーケット情報
    st.divider()
    is_weekend = datetime.now().weekday() >= 5
    st.subheader("🗓️ 週末マーケット要約" if is_weekend else "📈 本日のマーケット要約")
    st.write(get_market_briefing(datetime.now().strftime('%Y-%m-%d')))

    # グラフ
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No Data.")

# --- 6. 更新フォーム ---
st.divider()
up_file = st.file_uploader("スクショ更新", type=['png', 'jpg', 'jpeg'])
if st.button("AI解析実行"):
    if up_file:
        with st.spinner('AI解析中...'):
            try:
                img = Image.open(up_file)
                p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([p, img])
                st.write("解析結果:", res.text)
            except: st.error("解析失敗")
