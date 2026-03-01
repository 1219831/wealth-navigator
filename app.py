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

# --- 2. 外部連携 (接続チェック強化) ---
def init_gemini():
    try:
        # 1. Secretからキーを安全に取得
        if "GEMINI_API_KEY" not in st.secrets:
            st.error("Secretsに 'GEMINI_API_KEY' が見つかりません。")
            return None
        
        api_key = st.secrets["GEMINI_API_KEY"]
        genai.configure(api_key=api_key)
        
        # 2. 複数のモデル名を順に試す
        for m_name in ["gemini-1.5-flash", "models/gemini-1.5-flash", "gemini-pro"]:
            try:
                m = genai.GenerativeModel(m_name)
                # 3. 疎通テスト
                m.generate_content("ok", generation_config={"max_output_tokens": 1})
                return m
            except:
                continue
        return None
    except Exception as e:
        st.error(f"API初期化中にエラー発生: {e}")
        return None

model = init_gemini()

# モデルが取得できない場合の緊急表示
if not model:
    st.warning("⚠️ AI機能（OCR・マーケット情報）がオフになっています。APIキーの設定を確認してください。")
    # 接続できなくてもダッシュボードだけは表示させるため、ダミー関数を作成
    class DummyModel:
        def generate_content(self, *args, **kwargs):
            class DummyRes: text = "AI接続エラーのため表示できません。"
            return DummyRes()
    model = DummyModel()

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
        p = f"今日は{d_str}(週末)。先週の振り返りと明日からの重要イベントを日本語で短くまとめて。"
    else:
        p = f"今日は{d_str}(平日)。昨晩の米株、本日の日本株見通しを日本語で短くまとめて。"
    try:
        res = model.generate_content(p)
        return res.text if hasattr(res, 'text') else "情報の取得制限中"
    except:
        return "💡 マーケット情報を整理中。"

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

    # 2. マーケットダイジェスト
    st.divider()
    now = datetime.now()
    is_weekend = now.weekday() >= 5
    title = "🗓️ 週末マーケット要約" if is_weekend else "📈 本日のマーケット要約"
    st.subheader(title)
    st.markdown(get_market_briefing(now.strftime('%Y-%m-%d'), is_weekend))

    # 3. グラフ
    st.divider()
    p_df = df.copy() # デフォルト
    v_mode = st.radio("表示単位", ["日", "週", "月"], horizontal=True)
    try:
        if v_mode == "日":
            p_df = df[df['日付'] >= (ld - timedelta(days=30))].copy()
        elif v_mode == "週":
            p_df = df.set_index('日付').resample('W').last().dropna().reset_index()
        else:
            p_df = df.set_index('日付').resample('M').last().dropna().reset_index()
        
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=p_df['日付'], y=p_df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=4)))
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=20, r=20, t=20, b=20))
        st.plotly_chart(fig, use_container_width=True)
    except:
        st.info("グラフ生成中...")

else:
    st.info("データが読み込めません。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産状況を更新")
up_file = st.file_uploader("スクショを選択", type=['png', 'jpg', 'jpeg'])
if st.button("AI解析"):
    if up_file:
        with st.spinner('解析中...'):
            res = perform_ai_analysis(up_file)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("OK!")
