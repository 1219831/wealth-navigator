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

# --- 3. データ読み込み & 収支ロジック ---
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
    # --- A. 資産・収支計算 ---
    L = df.iloc[-1]
    T = L['総資産']
    M = L['信用評価損益']
    now = datetime.now()
    
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

    # --- B. 資産ダッシュボード (指定順序: 今日 -> 先月 -> 今月) ---
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
        pct = (T/GOAL)
        st.caption(f"目標達成率: {pct:.4%}")
        st.progress(max(0.0, min(float(pct), 1.0)))

    # --- C. 参謀本部 (イベント & 戦略指令) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    
    # 注目イベントの固定表示
    st.success("📈 **【3/2 注目】**: 伊藤園(2593)・ピープル(7865)決算 / 24時 米ISM製造業景況指数")
    
    # AIアドバイス (信用損益に基づいた注意喚起)
    advice_placeholder = st.empty()
    prompt = (
        f"参謀として助言せよ。信用損益{M}円のボスに対し、"
        "3/2の伊藤園・ピープル決算と米ISM指数が保有株に与える影響、"
        "明日寄り付きの具体的アクションを120文字で指令せよ。"
    )
    
    try:
        res = model.generate_content(prompt)
        if res.text:
            advice_placeholder.info(f"💡 **参謀Geminiの進言**: {res.text}")
    except:
        advice_placeholder.warning("🚨 **参謀の緊急指令**: 深夜の米ISMによる円高リスクを警戒。余力維持を最優先し、現物株の指値を再確認せよ。")

    # --- D. 期間切り替えグラフ (Duplicate ID対策済み) ---
    st.divider()
    st.write("### 🏔️ 資産トレンド推移")
    
    tabs = st.tabs(["日次 (Daily)", "週次 (Weekly)", "月次 (Monthly)"])
    
    def create_fig(data):
        f = go.Figure(go.Scatter(x=data['日付'], y=data['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
        f.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10),
                        xaxis=dict(type='date', tickformat='%m/%d'))
        return f

    with tabs[0]:
        st.plotly_chart(create_fig(df), use_container_width=True, key="graph_daily")
    
    with tabs[1]:
        df_w = df.resample('W', on='日付').last().reset_index().dropna()
        st.plotly_chart(create_fig(df_w), use_container_width=True, key="graph_weekly")
        
    with tabs[2]:
        df_m = df.resample('M', on='日付').last().reset_index().dropna()
        st.plotly_chart(create_fig(df_m), use_container_width=True, key="graph_monthly")

else:
    st.info("スプレッドシートからデータを読み込めませんでした。URLと権限を確認してください。")

# --- 5. 更新セクション ---
st.divider()
st.subheader("📸 資産状況の更新")
up = st.file_uploader("証券アプリのスクショをアップロード", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析実行"):
    if up:
        with st.spinner('解析中...'):
            try:
                img = Image.open(up)
                ocr_prompt = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
                res = model.generate_content([ocr_prompt, img])
                st.write("解析結果（確認用）:", res.text)
            except Exception as e:
                st.error(f"解析失敗: {e}")
