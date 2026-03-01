import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.express as px
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
    prompt = """松井証券の資産状況スクショから数値を抽出してください。{"cash": 123, "spot": 456, "margin": -789}形式のJSONのみで出力してください。"""
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
        # 日付処理とソート
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

        # --- ダッシュボード表示（前日→前月→今月） ---
        st.subheader("📊 資産状況ダッシュボード")
        cols = st.columns(5)
        
        cols[0].metric("現在の総資産", f"¥{int(total):,}")
        cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        cols[2].metric("前日比(前回比)", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        cols[3].metric(last_month_label, f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        cols[4].metric(f"{latest_date.month}月の収支", f"¥{int(this_month_diff):,}", delta=f"{int(this_month_diff):+,}")
            
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")

        # --- 📈 グラフエリア ---
        st.divider()
        g_col1, g_col2 = st.columns([2, 1])

        with g_col1:
            st.write("### 🏔️ 資産成長マウンテン (1億円への軌跡)")
            fig_area = go.Figure()
            # 資産推移
            fig_area.add_trace(go.Scatter(
                x=df['日付'], 
                y=df['総資産'], 
                fill='tozeroy', 
                name='総資産', 
                line=dict(color='#00FFAA', width=3)
            ))
            # 1億円目標線
            fig_area.add_hline(y=GOAL_AMOUNT, line_dash="dash", line_color="red", annotation_text="Goal: 1億円")
            
            fig_area.update_layout(
                template="plotly_dark", 
                height=400, 
                margin=dict(l=20, r=20, t=20, b=20),
                xaxis=dict(showgrid=False), 
                yaxis=dict(title="資産額 (円)", showgrid=True, gridcolor="#333")
            )
            st.plotly_chart(fig_area, use_container_width=True)

        with g_col2:
            st.write("### 🚀 月別収支推移")
            # 月別の収支を計算
            df['年月'] = df['日付'].dt.strftime('%Y/%m')
            monthly_summary = df.groupby('年月')['総資産'].agg(['first', 'last'])
            monthly_summary['diff'] = monthly_summary['last'] - monthly_summary['first']
            
            fig_bar = px.bar(
                monthly_summary, 
                x=monthly_summary.index, 
                y='diff', 
                color='diff', 
                color_continuous_scale=['#FF4B4B', '#00FFAA']
            )
            fig_bar.update_layout(
                template="plotly_dark", 
                height=400, 
                showlegend=False, 
                coloraxis_showscale=False,
                margin=dict(l=20, r=20, t=20, b=20), 
                xaxis_title="", 
                yaxis_title="収支 (円)"
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        df['日付'] = df['日付'].dt.strftime('%Y/%m/%d')
    else:
        st.info("データがまだありません。")
except Exception:
    st.info("データの読み込み中...")

# ==========================================================
# 処理2: 資産更新（AI解析 & 保存）
# ==========================================================
st.divider()
st.subheader("📸 資産状況を更新（AI自動解析）")
uploaded_files = st.file_uploader("スクショをアップロード", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('Geminiが解析中...'):
            res = perform_ai_analysis(uploaded_files)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析完了！内容を確認してください。")
            else:
                st.error("解析に失敗しました。")
                st.session_state.analyzed = True
    else:
        st.warning("ファイルを選択してください")

if st.session_state.analyzed:
    with st.form("confirm_form"):
        cash = st.number_input("現物買付余力", value=int(st.session_state.ocr_data.get('cash', 0)))
        spot = st.number_input("現物時価総額", value=int(st.session_state.ocr_data.get('spot', 0)))
        margin = st.number_input("信用評価損益", value=int(st.session_state.ocr_data.get('margin', 0)))
        
        if st.form_submit_button("この内容で記録する"):
            with st.spinner('保存中...'):
                today_str = datetime.now().strftime('%Y/%m/%d')
                new_total = cash + spot + margin
                new_entry = pd.DataFrame([{
                    "日付": today_str, 
                    "現物買付余力": cash, 
                    "現物時価総額": spot,
                    "信用評価損益": margin, 
                    "総資産": new_total, 
                    "1億円までの残り": GOAL_AMOUNT - new_total
                }])
                
                try:
                    if 'df' in locals() and not df.empty:
                        updated_df = pd.concat([df, new_entry], ignore_index=True)
                    else:
                        updated_df = new_entry
                    
                    updated_df['日付'] = pd.to_datetime(updated_df['日付'])
                    updated_df = updated_df.sort_values(by='日付').reset_index(drop=True)
                    updated_df['日付'] = updated_df['日付'].dt.strftime('%Y/%m/%d')
                    
                    conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                    st.balloons()
                    st.session_state.analyzed = False
                    st.success(f"保存完了: {today_str}")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失敗: {e}")
