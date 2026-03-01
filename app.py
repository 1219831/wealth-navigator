import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
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

    # --- 💎 【最重要】参謀本部：戦略ボード ＆ 緊急指令 ---
    st.divider()
    st.subheader("⚔️ 参謀本部：明日の決戦指令")
    
    event_area = st.empty()
    advice_area = st.empty()
    
    # AIへの指示：具体的イベント ＋ 投資家への「指令」
    p = f"""
    今日は {datetime.now().strftime('%Y-%m-%d')} です。投資家（ボス）の参謀として以下を厳守して出力してください。
    
    【1. 決戦予定】: 
    ・伊藤園(2593)、ピープル(7865)決算の具体的注目点
    ・今夜24時、米国ISM製造業景況指数の予想と影響
    ・3月初営業日のアノマリー
    
    【2. 参謀の緊急指令】: 
    上記を踏まえ、ボスが今すぐ、あるいは明日の寄り付きに「どう動くべきか」を。
    保有株への警戒、利確の検討、余力の確保など、アプリ画面で即座にアクションが取れるような、
    鋭く、重みのある一言を100文字以内で。
    """
    
    try:
        res = model.generate_content(p, generation_config={"temperature": 0.4})
        if res and res.text:
            parts = res.text.split("【2. 参謀の緊急指令】:")
            event_txt = parts[0].replace("【1. 決戦予定】:", "").strip()
            advice_txt = parts[1].strip() if len(parts) > 1 else "明日の寄り付きに集中してください。波乱の予感があります。"
            
            # 具体的なスケジュール表示
            event_area.success(event_txt)
            
            # 参謀の金言（緊急度を演出）
            advice_area.warning(f"💡 **参謀Geminiの緊急指令**: {advice_txt}")
    except:
        event_area.warning("🚨 伊藤園・ピープル決算 ＆ 今夜24時米ISM指数。3月初日の資金流入に警戒。")
        advice_area.error("💡 **参謀Geminiの緊急指令**: AI通信が混雑していますが、明日の寄り付きは『買い先行後の利確売り』を警戒。余力を残し、深夜のISM結果を待ってから動くのが上策です。")

    # グラフ表示
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
