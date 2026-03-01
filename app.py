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
    m_profit = latest['信用評価損益']
    
    # 資産ダッシュボード
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

    # --- 💎 参謀本部：銘柄直撃アラート ---
    st.divider()
    st.subheader("⚔️ 参謀本部：ポートフォリオ防衛指令")
    
    event_area = st.empty()
    
    # AIへのプロンプト（断線防止のため細かく結合）
    p = f"あなたは参謀です。信用損益{m_profit}円のボスへ助言せよ。"
    p += "1.伊藤園・ピープル決算の銘柄波及リスク。"
    p += "2.深夜24時米ISM指数による円高と信用維持率への警告。"
    p += "3.明日寄り付きの具体的アクション。"

    try:
        res = model.generate_content(p, generation_config={"temperature": 0.5})
        if res and res.text:
            event_area.warning(res.text)
    except:
        # バックアップメッセージ（断線しないよう1行ずつ定義）
        msg = "🚨 **【緊急代行指令】**\n"
        msg += f"現在の信用損益({m_profit:+,}円)に鑑み、深夜の米ISMによる円高急伸は"
        msg += "追証リスクを直撃します。伊藤園決算を材料視した買いが先行しても深追いは厳禁。"
        msg += "明日は【余力維持】を最優先し、現物の利確ラインを5%上に再設定せよ。"
        event_area.error(msg)

    # グラフ表示
    st.divider()
    st.write("
