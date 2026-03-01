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

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部連携設定 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("API設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能 ---
def perform_ai_analysis(up_file):
    p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except: return None

@st.cache_data(ttl=3600)
def get_market_briefing(d_str):
    p = f"今日は{d_str}。週明けの日本株決算予定、重要指標、🚨注目イベントを簡潔にまとめて。投資助言は不要。"
    try:
        res = model.generate_content(p)
        return res.text if res.text else "情報の取得を制限中"
    except: return "💡 市場データを確認中です。リロードをお試しください。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    # データの徹底的なクレンジング
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 1. 指標計算（エラー耐性強化）
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    # ダッシュボード
    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{ld.month}月収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
    cols[4].metric("目標達成率", f"{total/GOAL:.2%}")
    
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # 2. AIマーケットダイジェスト（独立ブロックで確実に表示）
    st.divider()
    st.subheader("🗓️ 本日のマーケット・ダイジェスト")
    today_key = datetime.now().strftime('%Y-%m-%d')
    st.markdown(get_market_briefing(today_key))

    # 3. グラフセクション（データフィルタリングを安全に）
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc: st.write("### 🏔️ 資産成長トレンド")
    with uc: v_mode = st.radio("表示", ["日", "週", "月"], horizontal=True)

    try:
        if v_mode == "日":
            p_df = df[df['日付'] >= (ld - timedelta(days=30))].copy()
            xf = "%m/%d"
        elif v_mode == "週":
            p_df = df.set_index('日付').resample('W').last().dropna().reset_index()
            xf = "%m/%d"
        else:
            p_df = df.set_index('日付').resample('M').last().dropna().reset_index()
            xf = "%y/%m"
        
        if p_df.empty: p_df = df.copy()

        ymax = p_df['総資産'].max() * 1.15 if not p_df.empty else 1000000
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=p_df['日付'], y=p_df['総資産'], fill='tozeroy', 
            line=dict(color='#007BFF', width=4), fillcolor='rgba(0, 123, 255, 0.15)',
            mode='lines+markers' if len(p_df) < 20 else 'lines'
        ))
        fig.update_layout(
            template="plotly_dark", height=400, margin=dict(l=50, r=20, t=20, b=50),
            xaxis=dict(tickformat=xf, type='date'),
            yaxis=dict(range=[0, ymax], tickformat=",d"),
            hovermode="x unified"
        )
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.error("グラフの生成に失敗しました。十分なデータが蓄積されるまでお待ちください。")
else:
    st.info("データがありません。松井証券の資産スクショをアップしてください。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産状況を更新")
up_file = st.file_uploader("スクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析を実行"):
    if up_file:
        with st.spinner('解析中...'):
            res = perform_ai_analysis(up_file)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("成功！内容を確認してください。")

if st.session_state.analyzed:
    with st.form("edit_form"):
        c1, c2, c3 = st.columns(3)
        ocr = st.session_state.ocr_data
        n_c = c1.number_input("現物取得余力", value=int(ocr.get('cash', 0)))
        n_s = c2.number_input("現物資産時価総額", value=int(ocr.get('spot', 0)))
        n_m = c3.number_input("信用保有資産損益", value=int(ocr.get('margin', 0)))
        if st.form_submit_button("記録する"):
            today_str = datetime.now().strftime('%Y/%m/%d')
            t_v = n_c + n_s + n_m
            ent = pd.DataFrame([{"日付": today_str, "現物買付余力": n_c, "現物時価総額": n_s, "信用評価損益": n_m, "総資産": t_v, "1億円までの残り": GOAL - t_v}])
            try:
                out = pd.concat([df_raw, ent], ignore_index=True) if not df_raw.empty else ent
                out['日付'] = pd.to_datetime(out['日付'])
                out = out.sort_values('日付').drop_duplicates('日付', keep='last')
                out['日付'] = out['日付'].dt.strftime('%Y/%m/%d')
                conn.update(spreadsheet=URL, data=out)
                st.balloons()
                st.session_state.analyzed = False
                st.rerun()
            except Exception as e:
                st.error(f"保存失敗: {e}")
