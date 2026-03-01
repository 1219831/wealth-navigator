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

# --- 3. AIマーケット要約関数 (日曜日は週明けを展望) ---
@st.cache_data(ttl=3600)
def get_market_briefing(d_str):
    now = datetime.now()
    # プロンプトを「週明けの展望」にシフトしてAIの回答を安定化
    p = f"今日は{d_str}。直近の米株動向と、明日からの日本株決算・重要指標の注目点を、投資家向けに日本語3行でまとめて。🚨マークを活用して。"
    try:
        res = model.generate_content(p)
        if res and res.text:
            return res.text
        return "💡 市場データを分析中です。しばらくお待ちください。"
    except Exception as e:
        return f"💡 準備中 (明日朝の寄り付きにご注目ください)"

# --- 4. データ読み込み & 型の完全統一 ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # 日付型の強制統一 (errors='coerce'で不正データを排除)
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    total = latest['総資産']
    
    # ダッシュボード表示
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
        st.metric("目標達成率", f"{pct:.3%}")
    
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 AIマーケットダイジェスト (独立ブロック) ---
    st.divider()
    is_weekend = datetime.now().weekday() >= 5
    st.subheader("🗓️ 週末マーケット要約" if is_weekend else "📈 本日のマーケット要約")
    
    # プレースホルダーを使ってAIの待ち時間を視覚化
    with st.container():
        briefing = get_market_briefing(datetime.now().strftime('%Y-%m-%d'))
        st.markdown(briefing)

    # --- 📈 資産成長グラフ (安定化版) ---
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    
    try:
        # グラフ用データ準備
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['日付'], 
            y=df['総資産'], 
            fill='tozeroy', 
            line=dict(color='#007BFF', width=3),
            hovertemplate='日付: %{x}<br>総資産: ¥%{y:,.0f}<extra></extra>'
        ))
        fig.update_layout(
            template="plotly_dark", 
            height=400, 
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(type='date', tickformat='%m/%d'),
            yaxis=dict(tickformat=',d')
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception as e:
        st.error(f"グラフ表示エラー: {e}")

else:
    st.info("データが読み込めません。スクショをアップロードしてください。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産更新")
up_file = st.file_uploader("スクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析実行"):
    if up_file:
        with st.spinner('AIがスクショを解析中...'):
            try:
                img = Image.open(up_file)
                p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([p, img])
                st.write("解析結果:", res.text)
                st.info("↑内容が正しければ、値を入力して保存してください。")
            except:
                st.error("AI解析に失敗しました。直接数値を入力してください。")
