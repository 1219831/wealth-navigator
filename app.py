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

st.set_page_config(page_title="Wealth Nav Pro", page_icon="📈", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Error")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ読み込み ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
except:
    pass

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
        st.caption(f"┣ 信用: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 余力: ¥{int(latest['現物買付余力']):,}")
    with c2: st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    with c3:
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 【新機能】戦略ボード：具体的イベント ＆ 参謀の進言 ---
    st.divider()
    st.subheader("🗓️ 戦略ボード：翌営業日の焦点")
    
    ai_area = st.empty()
    advice_area = st.empty() # 参謀の進言用
    
    ai_area.info("🔍 伊藤園・ピープル決算、米ISM指標、月初アノマリーを分析中...")
    
    # AIへの指示：イベント抽出 ＋ 参謀としての助言
    p = f"""
    今日は {datetime.now().strftime('%Y-%m-%d')} です。投資参謀として以下を出力してください。
    
    【1. 明日の重要イベント】: 
    ・国内決算：伊藤園(2593)、ピープル(7865)の注目点
    ・海外指標：米国ISM製造業景況指数の時間と予想
    ・市場環境：3月初日のアノマリーの有無
    
    【2. 参謀の進言】: 
    上記を踏まえ、明日の寄り付きから深夜にかけて、投資家はどう立ち回るべきか、
    鋭い洞察を込めた「参謀の一言」を100文字程度で。
    """
    
    success = False
    for i in range(2):
        try:
            res = model.generate_content(p, generation_config={"temperature": 0.3})
            if res and res.text:
                # テキストを【1.】【2.】で分割
                parts = res.text.split("【2. 参謀の進言】:")
                event_txt = parts[0].replace("【1. 明日の重要イベント】:", "").strip()
                advice_txt = parts[1].strip() if len(parts) > 1 else "明日は勝負の月曜日です。慎重かつ大胆に。"
                
                ai_area.success(event_txt)
                advice_area.info(f"💡 **参謀Geminiの独り言**: {advice_txt}")
                success = True
                break
        except:
            time.sleep(1)
    
    if not success:
        ai_area.warning("🚨 伊藤園・ピープル決算 ＆ 今夜24時米ISM指数。3月初日の資金流入に警戒。")
        advice_area.info("💡 **参謀Geminiの独り言**: AI通信が不安定ですが、月初は買いが先行しやすい傾向です。利確のタイミングを逃さぬよう。")

    # グラフ
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No data.")

# 更新フォーム（省略せず維持）
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
            except: st.error("OCR Failed.")
