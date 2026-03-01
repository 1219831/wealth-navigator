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

# --- 2. 外部サービス連携（Gemini / GSheets） ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# セッション状態の初期化
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI解析エンジン（OCR） ---
def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の資産状況から数値（現物買付余力、現物時価総額、信用評価損益）を抽出し、{"cash": 100, "spot": 200, "margin": -50} の形式で出力してください。"""
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# --- 4. メインロジック：データ読み込みと加工 ---
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df_raw.empty:
        # 型変換とクリーニング
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values(by='日付').drop_duplicates(subset='日付', keep='last').reset_index(drop=True)
        
        # 指標の計算
        latest = df.iloc[-1]
        total = latest['総資産']
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        
        this_month_start = df[df['日付'] >= latest['日付'].replace(day=1)]
        this_month_diff = total - this_month_start.iloc[0]['総資産'] if not this_month_start.empty else 0
        
        last_month_end = latest['日付'].replace(day=1) - timedelta(days=1)
        last_month_data = df[df['日付'].dt.to_period('M') == last_month_end.to_period('M')]
        last_month_diff = last_month_data.iloc[-1]['総資産'] - last_month_data.iloc[0]['総資産'] if not last_month_data.empty else 0

        # --- 5. ダッシュボード表示 ---
        st.title("🚀 Wealth Navigator PRO")
        
        m_cols = st.columns(5)
        m_cols[0].metric("現在の総資産", f"¥{int(total):,}")
        m_cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        m_cols[2].metric("前日(前回)比", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        m_cols[3].metric(f"{last_month_end.month}月の収支", f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        m_cols[4].metric(f"{latest['日付'].month}月の収支", f"¥{int(this_month_diff):,}", delta=f"{int(this_month_diff):+,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"目標達成率: {total/GOAL_AMOUNT:.2%}")

        # --- 6. チャートセクション（プロの視点） ---
        st.divider()
        view_col, unit_col = st.columns([3, 1])
        with view_col:
            st.subheader("🏔️ 資産成長マウンテン")
        with unit_col:
            view_mode = st.selectbox("分析期間", ["日次 (直近30日)", "週次 (直近15週)", "月次 (直近2年)"], index=0)

        # 表示データのフィルタリング
        if "日次" in view_mode:
            plot_df = df[df['日付'] >= (latest['日付'] - timedelta(days=30))].copy()
            x_format = "%m/%d"
        elif "週次" in view_mode:
            plot_df = df.set_index('日付').resample('W').last().dropna().tail(15).reset_index()
            x_format = "%m/%d"
        else:
            plot_df = df.set_index('日付').resample('M').last().dropna().tail(24).reset_index()
            x_format = "%y/%m"

        # グラフ作成
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

        # Y軸のゆとり設定（0固定＋上部に20%の余白）
        y_max_val = plot_df['総資産'].max() * 1.2

        fig.update_layout(
            template="plotly_dark",
            height=500,
            margin=dict(l=50, r=20, t=20, b=50),
            xaxis=dict(
                tickformat=x_format,
                showgrid=False,
                title="Timeframe",
                type='date'
            ),
            yaxis=dict(
                range=[0, y_max_val],
                showgrid=True,
                gridcolor="#333",
                title="Assets (JPY)",
                tickformat=",d"
            ),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
        

    else:
        st.info("データがありません。スクショをアップしてください。")
except Exception as e:
    st.info(f"データ準備中... (初回はデータを登録してください)")

# --- 7. 更新フォーム ---
st.divider()
st.subheader("📸 資産状況を更新")
uploaded_files = st.file_uploader("松井証券のスクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('Geminiが画像を読み解いています...'):
            res = perform_ai_analysis([uploaded_files])
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析完了！")
            else:
                st.error("解析に失敗しました。手動で入力してください。")
                st.session_state.analyzed = True

if st.session_state.analyzed:
    with st.form("update_form"):
        c1, c2, c3 = st.columns(3)
        cash = c1.number_input("現物買付余力", value=int(st.session_state.ocr_data.get('cash', 0)))
        spot = c2.number_input("現物時価総額", value=int(st.session_state.ocr_data.get('spot', 0)))
        margin = c3.number_input("信用評価損益", value=int(st.session_state.ocr_data.get('margin', 0)))
        
        if st.form_submit_button("この内容でスプレッドシートに記録"):
            today_str = datetime.now().strftime('%Y/%m/%d')
            new_total = cash + spot + margin
            new_entry = pd.DataFrame([{
                "日付": today_str, "現物買付余力": cash, "現物時価総額": spot,
                "信用評価損益": margin, "総資産": new_total, "1億円までの残り": GOAL_AMOUNT - new_total
            }])
            
            try:
                # データのマージと保存
                combined_df = pd.concat([df_raw, new_entry], ignore_index=True) if 'df_raw' in locals() else new_entry
                combined_df['日付'] = pd.to_datetime(combined_df['日付'])
                combined_df = combined_df.sort_values('日付').drop_duplicates(subset='日付', keep='last')
                combined_df['日付'] = combined_df['日付'].dt.strftime('%Y/%m/%d')
                
                conn.update(spreadsheet=SPREADSHEET_URL, data=combined_df)
                st.balloons()
                st.session_state.analyzed = False
                st.success("スプレッドシートを更新しました！")
                st.rerun()
            except Exception as e:
                st.error(f"保存失敗: {e}")
