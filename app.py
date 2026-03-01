import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.graph_objects as go

# --- 設定 ---
GOAL_AMOUNT = 100000000  # 1億円
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

# ワイドレイアウト設定
st.set_page_config(page_title="Wealth Navigator", page_icon="🚀", layout="wide")

# --- 準備1: Gemini APIの設定 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("Secretsに 'GEMINI_API_KEY' が正しく設定されていません。")
    st.stop()

st.title("🚀 Wealth Navigator")

# --- 準備2: Google Sheetsへの接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 状態管理（Session State）の初期化
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# AI解析関数（数値抽出）
def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の資産状況スクショから数値を抽出してください。{"cash": 123, "spot": 456, "margin": -789}形式のJSONのみで出力。"""
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# ==========================================================
# 処理1: 最新データの読み込みと「5つの指標」の表示
# ==========================================================
try:
    df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df.empty:
        # 日付処理（一度datetime型にする）
        df['日付'] = pd.to_datetime(df['日付'])
        df = df.sort_values(by='日付').reset_index(drop=True)
        
        latest = df.iloc[-1]
        latest_date = latest['日付']
        total = latest['総資産']
        
        # ① 前日（前回）比
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        
        # ② 今月の収支
        this_month_df = df[(df['日付'].dt.year == latest_date.year) & (df['日付'].dt.month == latest_date.month)]
        this_month_diff = total - this_month_df.iloc[0]['総資産'] if not this_month_df.empty else 0
            
        # ③ 先月の収支
        first_day_of_this_month = latest_date.replace(day=1)
        last_day_of_last_month = first_day_of_this_month - pd.Timedelta(days=1)
        last_month_df = df[(df['日付'].dt.year == last_day_of_last_month.year) & (df['日付'].dt.month == last_day_of_last_month.month)]
        
        if not last_month_df.empty:
            last_month_diff = last_month_df.iloc[-1]['総資産'] - last_month_df.iloc[0]['総資産']
            last_month_label = f"{last_day_of_last_month.month}月の収支"
        else:
            last_month_diff = 0
            last_month_label = "前月のデータなし"

        # --- ダッシュボード表示 ---
        st.subheader("📊 資産状況ダッシュボード")
        cols = st.columns(5)
        cols[0].metric("現在の総資産", f"¥{int(total):,}")
        cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        cols[2].metric("前日比(前回比)", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        cols[3].metric(last_month_label, f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        cols[4].metric(f"{latest_date.month}月の収支", f"¥{int(this_month_diff):,}", delta=f"{int(this_month_diff):+,}")
            
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")

        # --- 📈 グラフ表示設定 ---
        st.divider()
        st.write("### 🏔️ 資産成長マウンテン")
        
        # 表示切り替えスイッチ
        view_option = st.radio("表示範囲:", ["日次表示", "月次表示"], horizontal=True)

        if view_option == "日次表示":
            plot_df = df.copy()
            tick_format = "%m/%d" # 「2/28」形式
            hovertemplate = '%{x|%Y/%m/%d}<br>資産: ¥%{y:,.0f}<extra></extra>'
        else:
            # 各月の最終データを抽出（月末時点の資産）
            plot_df = df.set_index('日付').resample('M').last().dropna().reset_index()
            tick_format = "%Y/%m" # 「2026/02」形式
            hovertemplate = '%{x|%Y/%m}<br>月末資産: ¥%{y:,.0f}<extra></extra>'

        # メイングラフ作成
        fig = go.Figure()
        
        # 資産エリア
        fig.add_trace(go.Scatter(
            x=plot_df['日付'], 
            y=plot_df['総資産'], 
            fill='
