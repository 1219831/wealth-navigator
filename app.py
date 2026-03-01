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
GOAL_AMOUNT = 100000000 
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator", page_icon="🚀", layout="wide")

# --- 準備1: Gemini API ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    st.stop()

st.title("🚀 Wealth Navigator")

# --- 準備2: Google Sheets接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

def perform_ai_analysis(uploaded_files):
    prompt = """松井証券の数値抽出。{"cash": 123, "spot": 456, "margin": -789}のJSON形式で。"""
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception: return None

# ==========================================================
# 処理1: データ読み込みとダッシュボード表示
# ==========================================================
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df_raw.empty:
        # 日付処理
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values(by='日付').reset_index(drop=True)
        
        latest = df.iloc[-1]
        latest_date = latest['日付']
        total = latest['総資産']
        
        # 指標計算
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_month_df = df[(df['日付'].dt.year == latest_date.year) & (df['日付'].dt.month == latest_date.month)]
        this_month_diff = total - this_month_df.iloc[0]['総資産'] if not this_month_df.empty else 0
        
        last_month_date = latest_date.replace(day=1) - pd.Timedelta(days=1)
        last_month_df = df[(df['日付'].dt.year == last_month_date.year) & (df['日付'].dt.month == last_month_date.month)]
        last_month_diff = last_month_df.iloc[-1]['総資産'] - last_month_df.iloc[0]['総資産'] if not last_month_df.empty else 0

        # メトリックス
        st.subheader("📊 資産状況ダッシュボード")
        cols = st.columns(5)
        cols[0].metric("現在の総資産", f"¥{int(total):,}")
        cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        cols[2].metric("前日比(前回比)", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        
        l_month_label = f"{last_month_date.month}月の収支" if not last_month_df.empty else "前月のデータなし"
        cols[3].metric(l_month_label, f"¥{int(last_month_diff):,}", delta=f"{int(last_month_diff):+,}")
        
        t_month_label = f"{latest_date.month}月の収支"
        cols[4].metric(t_month_label, f"¥{int(this_month_diff):,}", delta=f"{int(this_month_diff):+,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")

        # --- 📈 シンプル版グラフ（日付表示: 26/2） ---
        st.divider()
        st.write("### 🏔️ 資産成長トレンド")
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=df['日付'], 
            y=df['総資産'], 
            fill='tozeroy', 
            name='総資産',
            line=dict(color='#007BFF', width=3),
            fillcolor='rgba(0, 123, 255, 0.2)'
        ))
        
        fig.update_layout(
            template="plotly_dark", 
            height=400, 
            margin=dict(l=20, r=20, t=20, b=20),
            xaxis=dict(
                tickformat="%y/%-m", # ここで「26/2」の形式に指定
                showgrid=False
            ),
            yaxis=dict(
                showgrid=True, 
                gridcolor="#333"
            )
        )
        st.plotly_chart(fig, use_container_width=True)

        df_raw['日付'] = df_raw['日付'].dt.strftime('%Y/%m/%d')
    else:
        st.info("データがまだありません。")
except Exception as e:
    st.error(f"エラーが発生しました: {e}")

# ==========================================================
# 処理2: 資産更新
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
                st.error("解析失敗")
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
                new_entry = pd.DataFrame([{"日付": today_str, "現物買付余力": cash, "現物時価総額": spot, "信用評価損益": margin, "総資産": new_total, "1億円までの残り": GOAL_AMOUNT - new_total}])
                try:
                    updated_df = pd.concat([df_raw, new_entry], ignore_index=True) if not df_raw.empty else new_entry
                    updated_df['日付'] = pd.to_datetime(updated_df['日付'])
                    updated_df = updated_df.sort_values(by='日付').reset_index(drop=True)
                    updated_df['日付'] = updated_df['日付'].dt.strftime('%Y/%m/%d')
                    conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                    st.balloons()
                    st.session_state.analyzed = False
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失敗: {e}")
