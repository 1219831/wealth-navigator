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
    st.error("API Error: Secrets設定を確認してください")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. AIマーケット分析関数 (土日/平日 判定ロジック入り) ---
@st.cache_data(ttl=3600)
def get_market_briefing(date_str):
    now = datetime.now()
    is_weekend = now.weekday() >= 5 # 5:土, 6:日
    
    if is_weekend:
        # 土日のプロンプト：振り返りと展望
        prompt = f"""
        今日は {date_str} (週末)です。以下の情報を日本語で簡潔にまとめてください。
        1. 【先週末の振り返り】: 日米市場の主要指数の終値と動向。
        2. 【週明けの注目点】: 明日(月曜)からの国内注目決算銘柄や重要経済指標。
        3. 【🚨最重要イベント】: 今週の相場の分岐点となるイベントを強調。
        ※投資助言ではなく、スケジュールと実績のまとめとして出力してください。
        """
    else:
        # 平日のプロンプト：昨晩と今日
        prompt = f"""
        今日は {date_str} (平日)です。
        1. 【昨晩の米株動向】: 主要指数の動きと要因。
        2. 【本日の日本株予想】: 寄り付き前後の見通し。
        3. 【🚨本日の注目】: 今日発表される決算や経済指標。
        ※短く3行程度でまとめてください。
        """
        
    try:
        response = model.generate_content(prompt)
        if response and response.text:
            return response.text
        return "💡 市場データを整理中です。リロードをお試しください。"
    except:
        return "💡 AIとの接続を再試行しています。しばらくお待ちください。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続中...")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データ正規化
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    total = latest['総資産']
    
    # 資産ダッシュボード
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

    # --- 💎 動的マーケット情報 ---
    st.divider()
    is_weekend = datetime.now().weekday() >= 5
    title = "🗓️ 週末の振り返りと週明け展望" if is_weekend else "📈 本日のマーケット要約"
    st.subheader(title)
    
    market_text = get_market_briefing(datetime.now().strftime('%Y年%m月%d日'))
    st.markdown(market_text)

    # --- 📈 グラフセクション ---
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['日付'], 
        y=df['総資産'], 
        fill='tozeroy', 
        line=dict(color='#007BFF', width=3),
        hovertemplate='日付: %{x|%Y/%m/%d}<br>資産: ¥%{y:,.0f}<extra></extra>'
    ))
    fig.update_layout(
        template="plotly_dark", 
        height=400, 
        margin=dict(l=20, r=20, t=20, b=20),
        xaxis=dict(type='date', tickformat='%m/%d'),
        yaxis=dict(tickformat=',d')
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("データが読み込めません。スクショをアップロードしてください。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産更新")
up_file = st.file_uploader("スクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析実行"):
    if up_file:
        with st.spinner('解析中...'):
            try:
                img = Image.open(up_file)
                p = '抽出項目：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([p, img])
                st.write("解析結果:", res.text)
            except:
                st.error("解析失敗。手動入力をお願いします。")
