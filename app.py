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
    latest = df.iloc[-1]
    total = latest['総資産']
    margin_profit = latest['信用評価損益'] # 信用損益を取得
    
    # 資産ダッシュボード
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(margin_profit):+,}")
        st.caption(f"┗ 余力: ¥{int(latest['現物買付余力']):,}")
    with c2: st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    with c3:
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 参謀本部：銘柄別・緊急指令ボード ---
    st.divider()
    st.subheader("⚔️ 参謀本部：ポートフォリオ防衛指令")
    
    # 状況分析
    margin_status = "悪化" if margin_profit < 0 else "良好"
    
    # プロンプトの構築（銘柄相関と資産状況を紐付け）
    p = f"""
    あなたはボスの資産形成を支えるプロの投資参謀です。
    現在のボスの状況：信用損益が{margin_profit}円（{margin_status}）。
    
    【明日の焦点】
    1. 伊藤園(2593)・ピープル(7865)の決算発表
    2. 深夜24時の米国ISM製造業景況指数
    
    これらを踏まえ、以下の2点を出力してください。
    【A. 銘柄への波及・注意喚起】: 
    これらのイベントが、ボスの保有する「現物株」や「信用ポジション」にどう悪影響・好影響を与えるか。特に円高・円安への振れ幅と信用維持率への懸念を。
    【B. 参謀の断固たる指令】: 
    今すぐ、あるいは明日の寄り付きにボスが取るべき具体的アクション。
    """
    
    event_area = st.empty()
    
    try:
        res = model.generate_content(p, generation_config={"temperature": 0.5})
        if res and res.text:
            # AIの回答をそのままカード形式で表示
            event_area.warning(res.text)
    except:
        # 万が一のバックアップ（ボスへの直撃弾を想定）
        event_area.error(f"""
        🚨 **【緊急代行指令】**
        明日の寄り付きは月初資金で浮つきますが、深夜のISM指数が予想を下回れば急激な「円高」を
