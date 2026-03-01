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
GOAL_AMOUNT = 100000000 
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部サービス連携 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# AI解析エンジン
def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の資産状況から数値（現物買付余力、現物時価総額、信用評価損益）を抽出し、{"cash": 100, "spot": 200, "margin": -50} の形式で出力してください。"""
    try:
        img = Image.open(uploaded_files[0])
        # get_image_info は不要なので削除
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# --- 4. メインロジック ---
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values(by='日付').drop_duplicates(subset='日付', keep='last').reset_index(drop=True)
        
        latest = df.iloc[-1]
        latest_date = latest['日付']
        total = latest['総資産']
        
        # 内訳データ
        spot_val = latest['現物時価総額']
        margin_val = latest['信用評価損益']
        cash_val = latest['現物買付余力']
        
        # 指標計算
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_month_df = df[(df['日付'].dt.year == latest_date.year) & (df['日付'].dt.month == latest_date.month)]
        this_month_diff = total - this_month_df.iloc[0]['総資産'] if not this_month_df.empty else 0
        
        # 先月のデータ抽出（ここを修正しました）
        last_month_end = latest_date.replace(day=1) - timedelta(days=1)
        last_month_df = df[df['日付'].dt.to_period('M') == last_month_end.to_period('M')]
        last_month_diff = last_month_df.iloc[-1]['総資産'] - last_month_df.iloc[0]['総資産'] if not last_month_df.empty else 0

        # --- 5. ダッシュボード表示 ---
        st.title("🚀 Wealth Navigator PRO")
        st.subheader("📊 資産状況ダッシュボード")
        
        # 指標表示エリア
        m_cols = st.columns([1.2, 1, 1, 1, 1])
        
        # 0: 総資産と内訳（ツリー形式）
        with m_cols[0]:
            st.metric("現在の総資産", f"¥{int(total):,}")
            st.caption(f"┣ 現物資産時価総額: ¥{int(spot_val):,}")
            st.caption(f"┣ 信用保有資産損益: ¥{int(margin_val):+,}")
            st.caption(f"┗ 現物取得余力: ¥{int(cash_val):,}")

        # 1: 目標までの残り
        m_cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        
        # 2: 前日比
        m_cols[2].metric("前日(前回)比", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        
        # 3: 前月収支
        l_month_label = f"{last_month_end.month}月の収支" if not last_month_df.empty else "前月のデータなし"
        m_cols[3].metric(l_month_label, f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        
        # 4: 今月収支
        t_month_label = f"{latest_date.month}月の収支"
        m_cols[4].metric(t_month_label, f"¥{int(this_month_diff):,}", delta=f"{int(this_month_diff):+,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"目標達成率: {total/GOAL_AMOUNT:.2%}")

        # --- 6. チャートセクション ---
        st.divider()
        view_col, unit_col = st.columns([3, 1])
        with view_col:
            st.write("### 🏔️ 資産成長マウンテン")
        with unit_col:
            view_mode = st.selectbox("分析期間", ["日次 (直近30日)", "週次 (直近15週)", "月次 (直近2年)"], index=0)

        if "日次" in view_mode:
            plot_df = df[df['日付'] >= (latest_date - timedelta(days=30))].copy()
            x_format = "%m/%d"
        elif "週次" in view_mode:
            plot_df = df.set_index('日付').resample('W').last().dropna().tail(15).reset_index()
            x_format = "%m/%d"
        else:
            plot_df = df.set_index('日付').resample('M').last().dropna().tail(24).reset_index()
            x_format = "%y/%m"

        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=plot_df['日付'], 
            y=plot_df['総資産'], 
            fill='tozeroy', 
            mode='lines+markers' if "日次" in view_mode else 'lines',
            line=dict(color='#007BFF', width=4),
            fillcolor='rgba(0, 123, 255, 0.1)',
            hovertemplate='<b>%{x|%Y/%m/%d}</b><br>総資産: ¥%{y:,.0f}<extra></extra>'
        ))

        y_max_val = plot_df['総資産'].max() * 1.2 if not plot_df.empty else 1000000

        fig.update_layout(
            template="plotly_dark", height=500, margin=dict(l=50, r=20, t=20, b=50),
            xaxis=dict(tickformat=x_format, showgrid=False, type='date'),
            yaxis=dict(range=[0, y_max_val], showgrid=True, gridcolor="#333", tickformat=",d"),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)

    else:
        st.info("データがありません。")
except Exception as e:
    st.error(f"データ表示エラー: {e}")

# --- 7. 更新フォーム ---
st.divider()
st.subheader("📸 資産状況を更新")
uploaded_files = st.file_uploader("松井証券のスクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('Geminiが解析中...'):
            res = perform_ai_analysis([uploaded_files])
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析完了！")
            else:
                st.error("解析失敗")
                st.session_state.analyzed = True

if st.session_state.analyzed:
    with st.form("update_form"):
        c1, c2, c3 = st.columns(3)
        cash = c1.number_input("現物取得余力", value=int(st
