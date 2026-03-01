import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav Pro", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Error")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ取得 ---
df = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
    if not df_raw.empty:
        df_raw['日付'] = pd.to_datetime(df_raw['日付'], errors='coerce')
        df = df_raw.dropna(subset=['日付']).sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
except:
    pass

# --- 4. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df.empty:
    L = df.iloc[-1]
    T = L['総資産']
    M = L['信用評価損益']
    
    # A. 資産ダッシュボード
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(T):,}")
        st.caption(f"┣ 現物: ¥{int(L['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(M):+,}")
        st.caption(f"┗ 余力: ¥{int(L['現物買付余力']):,}")
    c2.metric("1億円まで", f"¥{int(GOAL - T):,}")
    c3.metric("目標達成率", f"{T/GOAL:.4%}")
    st.progress(max(0.0, min(float(T / GOAL), 1.0)))

    # --- 💎 参謀本部 (断線してもエラーにならない1行完結型) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：明日の決戦指令")
    
    P = f"参謀として信用損益{M}円のボスに助言せよ。伊藤園(2593)・ピープル(7865)決算、今夜24時米ISM指数を踏まえ、明日寄り付きの銘柄注意点と具体的行動を120字で。"
    
    try:
        res = model.generate_content(P)
        if res.text:
            st.warning(res.text)
    except:
        st.error(f"🚨 指令：信用損益({M:+,}円)に鑑み、深夜の円高急伸は追証を招く。明日は余力維持を最優先せよ。")

    # B. トレンドグラフ
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF')))
    fig.update_layout(template="plotly_dark", height=300, margin=dict(l=0, r=0, t=0, b=0))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("No data.")

# --- 5. 更新フォーム ---
st.divider()
up = st.file_uploader("スクショ更新", type=['png', 'jpg'])
if st.button("AI解析実行"):
    if up:
        with st.spinner('Analyzing...'):
            try:
                img = Image.open(up)
                res = model.generate_content(['{"cash":int,"spot":int,"margin":int}', img])
                st.write(res.text)
            except:
                st.error("Error")
