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
    st.error("API接続エラー。Secrets設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ読み込み（ここが止まると全て消えるため最優先） ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
except Exception as e:
    st.error(f"データ読み込みエラー: {e}")

# --- 4. メイン画面表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    # A. 資産ダッシュボード（ここは絶対に消さない）
    latest = df.iloc[-1]
    total = latest['総資産']
    
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
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # B. 資産トレンドグラフ（AIを待たずに描画）
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    try:
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['日付'], y=df['総資産'], fill='tozeroy', 
            line=dict(color='#007BFF', width=3),
            hovertemplate='日付: %{x|%Y/%m/%d}<br>資産: ¥%{y:,.0f}<extra></extra>'
        ))
        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.info("グラフデータを整理中...")

    # C. AIマーケットダイジェスト（最後に配置し、失敗しても他を守る）
    st.divider()
    is_weekend = datetime.now().weekday() >= 5
    st.subheader("🗓️ 週末の振り返りと週明け展望" if is_weekend else "📈 本日のマーケット要約")
    
    ai_area = st.empty() # プレースホルダー作成
    ai_area.info("⌛ AIが週明けの戦略を練っています...")
    
    try:
        prompt = f"今日は
