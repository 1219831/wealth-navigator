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

# --- 2. 外部連携 (接続チェック強化版) ---
def init_gemini():
    try:
        # Secretからキーを取得
        key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=key)
        
        # モデル候補（2026年現在の安定版）
        for m_name in ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-pro"]:
            try:
                m = genai.GenerativeModel(m_name)
                # 疎通テスト（1トークンだけ生成）
                m.generate_content("test", generation_config={"max_output_tokens": 1})
                return m
            except:
                continue
        return None
    except KeyError:
        st.error("Secretsに 'GEMINI_API_KEY' が登録されていません。")
        st.stop()
    except Exception as e:
        st.error(f"API初期化中にエラー: {e}")
        st.stop()

model = init_gemini()
if not model:
    st.error("API接続に失敗しました。Keyが有効か、またはGemini 1.5の利用権限があるか確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI分析エンジン ---
def perform_ai_analysis(up_file):
    p = '抽出項目：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except: return None

@st.cache_data(ttl=3600)
def get_market_briefing(d_str, is_weekend):
    if is_weekend:
        p = f"今日は{d_str}(週末)。先週の市場振り返りと明日からの指標・注目イベントを日本語で短くまとめて。"
    else:
        p = f"今日は{d_str}(平日)。昨晩の米株、本日の日本株見通し、重要決算・指標を日本語で短くまとめて。"
    try:
        res = model.generate_content(p)
        return res.text if res.text else "情報の取得制限中"
    except:
        return "💡 マーケット情報を整理中。リロードをお試しください。"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
    df_raw = df_raw.dropna(subset=['日付'])
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    # 1. ダッシュボード
    st.subheader("📊 資産状況")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物時価: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 買付余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("目標まで", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{ld.month}月収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
    cols[4].metric("達成率", f"{total/GOAL:.2%}")
    
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # 2. 動的マーケットダイジェスト
    st.divider()
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    title = "🗓️ 週末マーケット要約" if is_weekend else "📈 本日のマーケット要約"
    st.subheader(title)
    st.markdown(get_market_briefing(now.strftime('%Y-%m-%d'), is_weekend))

    # 3. グラフ
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc: st.write("### 🏔️ 資産トレンド")
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

        y_m = p_df['総資産'].max() * 1.15
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=p_df['日付'], y=p_df['総資産'], fill='tozeroy', 
            line=dict(color='#007BFF', width=4), fillcolor='rgba(0, 123, 255, 0.15)',
            mode='lines+markers' if len(p_df) < 20 else 'lines'
        ))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=50, r=20, t=20, b=50))
        fig.update_xaxes(tickformat=xf, type='date')
        fig.update_yaxes(range=[0, y_m], tickformat=",d")
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("グラフ生成中...")

else:
    st.info("データが読み込めません。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産更新")
up_file = st.file_uploader("スクショ選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析"):
    if up_file:
        with st.spinner('解析中...'):
            res = perform_ai_analysis(up_file)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("OK!")

if st.session_state.analyzed:
    with st.form("edit"):
        c1, c2, c3 = st.columns(3)
        ocr = st.session_state.ocr_data
        n_c = c1.number_input("余力", value=int(ocr.get('cash', 0)))
        n_s = c2.number_input("時価", value=int(ocr.get('spot', 0)))
        n_m = c3.number_input("損益", value=int(ocr.get('margin', 0)))
        if st.form_submit_button("記録"):
            td = datetime.now().strftime('%Y/%m/%d')
            tv = n_c + n_s + n_m
            ent = pd.DataFrame([{"日付": td, "現物買付余力": n_c, "現物時価総額": n_s, "信用評価損益": n_m, "総資産": tv, "1億円までの残り": GOAL - tv}])
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
                st.error(f"Error: {e}")
