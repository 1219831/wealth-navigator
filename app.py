import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go

# --- 1. システム設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav Pro", layout="wide", page_icon="📈")

# --- 2. 外部API連携 (Gemini) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error("API設定エラー。Secretsを確認してください。")
    st.stop()

# --- 3. データ読み込み ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_and_process_data():
    try:
        raw = conn.read(spreadsheet=URL, ttl=0)
        if raw.empty: return None
        raw['日付'] = pd.to_datetime(raw['日付'], errors='coerce')
        df = raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
        return df
    except:
        return None

df = load_and_process_data()

# --- 4. メイン画面構築 ---
st.title("🚀 Wealth Navigator PRO")

if df is not None and not df.empty:
    L = df.iloc[-1]
    T = L['総資産']
    M = L['信用評価損益']
    now = datetime.now()
    
    # --- 収支計算 (日・先月・今月) ---
    d_gain, m_gain, p_gain = 0, 0, 0
    try:
        # 今日の収支 (前日比)
        if len(df) > 1: d_gain = T - df.iloc[-2]['総資産']
        # 今月の収支 (月初比)
        m_start = df[df['日付'] >= now.replace(day=1, hour=0, minute=0, second=0)]
        if not m_start.empty: m_gain = T - m_start.iloc[0]['総資産']
        # 先月の収支 (先月1日〜末日)
        lm_end = now.replace(day=1, hour=0, minute=0, second=0)
        lm_start = (lm_end - pd.DateOffset(months=1))
        lm_data = df[(df['日付'] >= lm_start) & (df['日付'] < lm_end)]
        if not lm_data.empty: p_gain = lm_data.iloc[-1]['総資産'] - lm_data.iloc[0]['総資産']
    except: pass

    # --- B. 資産ダッシュボード (順序：今日 -> 先月 -> 今月) ---
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    with c1:
        st.metric("今日の収支", f"¥{int(d_gain):+d}")
        st.caption(f"┣ 総資産: ¥{int(T):,}")
        st.caption(f"┗ 信用損益: ¥{int(M):+,}")
    with c2:
        st.metric("先月の収支", f"¥{int(p_gain):+,}")
        st.caption(f"現物時価: ¥{int(L['現物時価総額']):,}")
    with c3:
        st.metric("今月の収支", f"¥{int(m_gain):+,}")
        st.caption(f"買付余力: ¥{int(L['現物買付余力']):,}")
    with c4:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.caption(f"達成率: {T/GOAL:.4%}")
        st.progress(max(0.0, min(float(T/GOAL), 1.0)))

    # --- C. 参謀本部 (イベント & ジェミニの一言) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    st.success("📈 **【3/2 注目】**: 伊藤園(2593)・ピープル(7865)決算 / 24時 米ISM製造業景況指数")
    
    advice_placeholder = st.empty()
    prompt = f"投資参謀として助言せよ。信用損益{M}円のボスへ。3/2の伊藤園・ピープル決算と米ISMの影響、明日寄り付きの具体的行動を120字で。"
    try:
        res = model.generate_content(prompt)
        if res.text: advice_placeholder.info(f"💡 **参謀Geminiの進言**: {res.text}")
    except: advice_placeholder.warning("🚨 **参謀の緊急指令**: 深夜の米ISMによる円高リスクを警戒。余力を残し夜戦に備えよ。")

    # --- D. 期間切り替えグラフ (タブ形式) ---
    st.divider()
    st.write("### 🏔️ 資産トレンド推移")
    tabs = st.tabs(["日次 (Daily)", "週次 (Weekly)", "月次 (Monthly)"])
    
    def create_fig(data):
        f = go.Figure(go.Scatter(x=data['日付'], y=data['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
        f.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10))
        return f

    with tabs[0]: st.plotly_chart(create_fig(df), use_container_width=True, key="daily_chart")
    with tabs[1]:
        df_w = df.resample('W', on='日付').last().reset_index().dropna()
        st.plotly_chart(create_fig(df_w), use_container_width=True, key="weekly_chart")
    with tabs[2]:
        df_m = df.resample('M', on='日付').last().reset_index().dropna()
        st.plotly_chart(create_fig(df_m), use_container_width=True, key="monthly_chart")

else:
    st.info("データが読み込めません。スプレッドシートのURLまたは権限を確認してください。")

# --- 5. 更新セクション (3枚同時アップロード対応) ---
st.divider()
st.subheader("📸 資産状況の更新 (最大3枚)")
# 複数選択を許可
uploaded_files = st.file_uploader("証券アプリのスクショを選択（最大3枚まで選択可能）", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI統合解析実行"):
    if uploaded_files:
        if len(uploaded_files) > 3:
            st.error("ファイルは3枚以内にしてください。")
        else:
            with st.spinner('複数画像を統合解析中...'):
                try:
                    # AIに統合して読み取るよう指示
                    input_list = ["これら複数の画像（最大3枚）から、最新の資産状況を統合して抽出してください。抽出形式：{\"cash\": 数値, \"spot\": 数値, \"margin\": 数値}"]
                    for up_file in uploaded_files:
                        img = Image.open(up_file)
                        input_list.append(img)
                    
                    res = model.generate_content(input_list)
                    st.write("統合解析結果:", res.text)
                    st.info("※解析結果をスプレッドシートへ反映してください。")
                except Exception as e:
                    st.error(f"解析失敗: {e}")
