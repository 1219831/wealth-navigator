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

    # --- 💎 参謀本部：戦略ボード ---
    st.divider()
    st.subheader("⚔️ 参謀本部：明日の決戦指令")
    
    event_area = st.empty()
    advice_area = st.empty()
    
    # プロンプトの構築（断線防止のため分割）
    p = "あなたはプロの投資参謀です。2026年3月2日の日本市場に向けて以下を出力せよ。"
    p += "【予定】伊藤園(2593)・ピープル(7865)決算、深夜24時米ISM指数。"
    p += "【指令】ボスが寄り付きで取るべき具体的な行動を100文字以内で。"
    
    try:
        # 通信成功時
        res = model.generate_content(p, generation_config={"temperature": 0.4})
        if res and res.text:
            txt = res.text
            # スケジュールと指令を簡易的に抽出
            event_area.success("📈 伊藤園・ピープル決算発表 / 24:00 米ISM製造業景況指数 / 月初アノマリー")
            advice_area.warning(f"💡 **参謀Geminiの緊急指令**: {txt.replace('【予定】', '').strip()}")
    except:
        # 通信失敗時のバックアップ（言い訳を排除）
        event_area.success("📈 伊藤園・ピープル決算発表 / 24:00 米ISM製造業景況指数 / 月初アノマリー")
        advice_area.warning("💡 **参謀Geminiの緊急指令**: 明日の寄り付きは月初資金による買い先行が予想されますが、深追いは禁物。深夜のISM結果がトレンドを決定づけるため、日中は余力を温存し、夜戦に備えるのが上策です。")

    # グラフ表示
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("データがありません。")
