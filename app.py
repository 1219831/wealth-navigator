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
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部連携 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# セッション管理
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI解析関数 ---
def perform_ai_analysis(up_file):
    p = '松井証券の数値抽出。{"cash": 100, "spot": 200, "margin": -50} の形式。'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except Exception:
        return None

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except Exception as e:
    st.error(f"接続エラー: {e}")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データ加工
    df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld = latest['日付']
    total = latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産']
    
    lm_day = ld.replace(day=1) - timedelta(days=1)
    lm_df = df[df['日付'].dt.to_period('M') == lm_day.to_period('M')]
    lm_diff = lm_df.iloc[-1]['総資産'] - lm_df.iloc[0]['総資産'] if not lm_df.empty else 0

    # 1. ダッシュボード表示
    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{lm_day.month}月の収支", f"¥{int(lm_diff):,}", delta=f"{int(lm_diff):+,}")
    cols[4].metric(f"{ld.month}月の収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
    
    prg = max(0.0, min(float(total / GOAL_AMOUNT), 1.0))
    st.progress(prg, text=f"目標達成率: {prg:.2%}")

    # 2. グラフセクション
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc:
        st.write("### 🏔️ 資産成長トレンド")
    with uc:
        v_mode = st.radio("表示単位", ["日", "週", "月"], horizontal=True)

    # グラフ用データフィルタリングと安全策
    if v_mode == "日":
        plot_df = df[df['日付'] >= (ld - timedelta(days=7))].copy()
        if len(plot_df) < 2: plot_df = df.tail(10) # 7日分なければ直近10件
        x_fmt, dtk = "%m/%d", None
    elif v_mode == "週":
        plot_df = df.set_index('日付').resample('W').last().dropna().tail(12).reset_index()
        if len(plot_df) < 2: plot_df = df.tail(15) # 週次データがなければ直近15件
        x_fmt, dtk = "%m/%d", None
    else:
        # 月別
        df_p = df.copy()
        df_p['m'] = df_p['日付'].dt.to_period('M')
        plot_df = df_p.groupby('m').tail(1).copy().tail(12).reset_index(drop=True)
        if len(plot_df) < 2: plot_df = df.tail(30) # 月次がなければ直近30件
        x_fmt, dtk = "%y/%m", "M1"

    # グラフ描画
    y_m = plot_df['総資産'].max() * 1.15 if not plot_df.empty else 1000000
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=plot_df['日付'], 
        y=plot_df['総資産'], 
        fill='tozeroy', 
        name='総資産',
        line=dict(color='#007BFF', width=4), 
        fillcolor='rgba(0, 123, 255, 0.15)',
        mode='lines+markers' if v_mode == "日" else 'lines',
        hovertemplate='<b>%{x|%Y/%m/%d}</b><br>資産: ¥%{y:,.0f}<extra></extra>'
    ))
    
    fig.update_layout(
        template="plotly_dark", 
        height=
