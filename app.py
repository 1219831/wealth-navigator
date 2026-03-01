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
    st.error("API Error: Secretsを確認してください")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ読み込み（最優先） ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付'])
        df = df.sort_values('日付').drop_duplicates('日付', keep='last')
        df = df.reset_index(drop=True)
except:
    st.warning("スプレッドシート接続中...")

# --- 4. メイン画面表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    # A. 資産ダッシュボード
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

    # B. 資産トレンドグラフ (AIを待たずに即時表示)
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
    except:
        st.info("グラフ描画中...")

    # C. AIマーケットダイジェスト (断線対策済み)
    st.divider()
    now_dt = datetime.now()
    is_we = now_dt.weekday() >= 5
    st.subheader("🗓️ 週末の振り返りと週明け展望" if is_we else "📈 本日のマーケット要約")
    
    ai_area = st.empty()
    ai_area.info("⌛ AIが明日の寄り付きに向けた戦略を練っています...")
    
    # プロンプトを短く分割して変数化（断線防止）
    day_str = now_dt.strftime('%Y-%m-%d')
    p_text = f"今日は {day_str} (日曜)。明日の日本株市場に向けた"
    p_text += "戦略・注目決算・指標を3行で。🚨マーク活用。"
    
    try:
        res = model.generate_content(p_text)
        if res and res.text:
            ai_area.markdown(res.text)
        else:
            ai_area.warning("💡 明朝の日本市場の寄り付きと主要決算に注目しましょう。")
    except:
        ai_area.warning("🚨 AI接続が混雑中。週明けのボラティリティに注意です。")

else:
    st.info("データが読み込めません。")

# --- 5. 更新フォーム ---
st.divider()
up_file = st.file_uploader("資産スクショを選択", type=['png', 'jpg', 'jpeg'])
if st.button("AI解析実行"):
    if up_file:
        with st.spinner('解析中...'):
            try:
                img = Image.open(up_file)
                ocr_p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([ocr_p, img])
                st.write("解析結果:", res.text)
            except:
                st.error("解析エラー。直接入力してください。")
