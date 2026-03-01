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

# セッション状態の保持
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI解析エンジン ---
def perform_ai_analysis(up_file):
    prompt = """松井証券の数値抽出。{"cash": 100, "spot": 200, "margin": -50} の形式で。"""
    try:
        img = Image.open(up_file)
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
except Exception as e:
    st.error(f"スプレッドシート接続エラー: {e}")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # --- データ加工ブロック ---
    try:
        df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
        df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
        
        latest = df.iloc[-1]
        l_date = latest['日付']
        total = latest['総資産']
        
        # 内訳
        s_v, m_v, c_v = latest['現物時価総額'], latest['信用評価損益'], latest['現物買付余力']
        
        # 指標計算
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        this_mo = df[df['日付'].dt.to_period('M') == l_date.to_period('M')]
        this_mo_diff = total - this_mo.iloc[0]['総資産']
        
        last_mo_day = l_date.replace(day=1) - timedelta(days=1)
        last_mo_df = df[df['日付'].dt.to_period('M') == last_mo_day.to_period('M')]
        last_mo_diff = last_mo_df.iloc[-1]['総資産'] - last_mo_df.iloc[0]['総資産'] if not last_mo_df.empty else 0
    except Exception as e:
        st.error(f"データ加工エラー: {e}")
        st.stop()

    # --- UI表示ブロック (インデントに注意) ---
    st.subheader("📊 資産状況ダッシュボード")
    m_cols = st.columns([1.2, 1, 1, 1, 1])
    
    with m_cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(s_v):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(m_v):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(c_v):,}")
    
    m_cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
    m_cols[2].metric("前日比", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
    m_cols[3].metric(f"{last_mo_day.month}月の収支", f"¥{int(last_mo_diff):,}", delta=f"{int(last_mo_diff):+,}")
    m_cols[4].metric(f"{l_date.month}月の収支", f"¥{int(this_mo_diff):,}", delta=f"{int(this_mo_diff):+,}")
    
    st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"目標達成率: {total/GOAL_AMOUNT:.2%}")

    # --- グラフ表示ブロック ---
    st.divider()
    v_c, u_c = st.columns([3, 1])
    with v_c:
        st.write("### 🏔️ 資産成長トレンド")
    with u_c:
        v_mode = st.radio("表示単位", ["日次", "週次", "月次"], horizontal=True)

    if v_mode == "日次":
        plot_df = df[df['日付'] >= (l_date - timedelta(days=30))].copy()
        x_fmt = "%m/%d"
    elif v_mode == "週次":
        plot_df = df.set_index('日付').resample('W').last().dropna().tail(15).reset_index()
        x_fmt = "%m/%d"
    else:
        plot_df = df.set_index('日付').resample('M').last().dropna().tail(24).reset_index()
        x_fmt = "%y/%m"

    y_max = plot_df['総資産'].max() * 1.15 if not plot_df.empty else 10000
