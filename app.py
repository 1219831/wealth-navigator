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

# --- 4. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    # A. 資産ダッシュボード (最優先で表示)
    latest = df.iloc[-1]
    total = latest['総資産']
    m_profit = latest['信用評価損益']
    
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(m_profit):+,}")
        st.caption(f"┗ 余力: ¥{int(latest['現物買付余力']):,}")
    with c2: st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    with c3:
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 参謀本部：銘柄・イベント直撃ボード ---
    st.divider()
    st.subheader("⚔️ 参謀本部：明日の決戦指令")
    
    # AIへの指令を構築
    p_lines = [
        "あなたは投資家ボスの有能な参謀です。",
        f"現在のボスの信用損益は {m_profit}円 です。",
        "明日の『伊藤園(2593)』『ピープル(7865)』の決算発表、",
        "および今夜24時の『米国ISM製造業景況指数』を踏まえ、",
        "1. 具体的な注目ポイント",
        "2. 保有株(現物・信用)への注意喚起と明日寄り付きの行動",
        "を150文字以内で鋭くアドバイスしてください。"
    ]
    p_final = " ".join(p_lines)

    # プレースホルダーの設置
    advice_box = st.empty()

    try:
        res = model.generate_content(p_final, generation_config={"temperature": 0.4})
        if res and res.text:
            advice_box.warning(res.text)
    except:
        # AIエラー時のフォールバック
        fallback = [
            "🚨 【緊急参謀警告】",
            f"信用損益 {m_profit:+,}円 の状況下では、今夜のISMによるドル円急変が",
            "最大の懸念材料です。伊藤園決算は内需の避難先となる可能性がありますが、",
            "明日は【余力維持】を最優先し、寄り付きの買い一巡後の動きを注視せよ。"
        ]
        advice
