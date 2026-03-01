import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.graph_objects as go
import time

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

# --- 3. データ読み込み（安定化） ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
except:
    st.warning("Sheet Syncing...")

# --- 4. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    latest = df.iloc[-1]
    total = latest['総資産']
    
    # 資産ダッシュボード
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 余力: ¥{int(latest['現物買付余力']):,}")
    with c2:
        st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    with c3:
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 AIマーケットダイジェスト（粘りのリトライ実装） ---
    st.divider()
    is_we = datetime.now().weekday() >= 5
    st.subheader("🗓️ 週末の振り返りと週明け展望" if is_we else "📈 本日のマーケット要約")
    
    ai_area = st.empty()
    ai_area.info("⌛ AIが明日の戦術を練っています（混雑時はリトライします）...")
    
    # プロンプトの簡略化
    p = f"今日は{datetime.now().strftime('%m/%d')}。明日の日本株の寄り付き注目点、重要決算、指標を3行で。🚨マーク活用。"
    
    success = False
    for i in range(3): # 最大3回リトライ
        try:
            res = model.generate_content(p)
            if res and res.text:
                ai_area.markdown(res.text)
                success = True
                break
        except:
            time.sleep(2) # 2秒待って再試行
    
    if not success:
        # 最終バックアップ：AIが全滅しても出す実戦情報
        ai_area.warning("🚨 混雑のためAIは沈黙していますが、明日は『3月初日のアノマリー』と『国内主要決算』が寄り付きの焦点です。米株の安定を受け、底堅い展開を想定しましょう。")

    # グラフ描画
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No data.")

# 更新フォーム
st.divider()
up_file = st.file_uploader("スクショ更新", type=['png', 'jpg', 'jpeg'])
if st.button("AI解析"):
    if up_file:
        with st.spinner('Analyzing...'):
            try:
                img = Image.open(up_file)
                p_ocr = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([p_ocr, img])
                st.write(res.text)
            except:
                st.error("OCR Failed.")
