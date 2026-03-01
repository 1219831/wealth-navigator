import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Nav Pro", page_icon="📈", layout="wide")

# --- 2. 外部連携 ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("API Error")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 3. データ読み込み ---
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
    latest = df.iloc[-1]
    total = latest['総資産']
    m_profit = latest['信用評価損益']
    
    # 資産ダッシュボード
    st.subheader("📊 資産状況")
    c1, c2, c3 = st.columns([1.5, 1, 1])
    with c1:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用損益: ¥{int(m_profit):+,}")
        st.caption(f"┗ 余力: ¥{int(latest['現物買付余力']):,}")
    with c2: st.metric("1億円まで", f"¥{int(GOAL - total):,}")
    with c3:
        pct = (total / GOAL)
        st.metric("目標達成率", f"{pct:.4%}")
    st.progress(max(0.0, min(float(total / GOAL), 1.0)))

    # --- 💎 参謀本部：銘柄直撃アラート (断線対策済み) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：ポートフォリオ防衛指令")
    
    # 指令エリアの確保
    alert_box = st.empty()
    
    # プロンプトの単語分割（断線してもエラーにならない形式）
    p_parts = [
        "あなたは投資参謀です。",
        f"現在の信用損益は {m_profit}円です。",
        "明日の伊藤園(2593)とピープル(7865)の決算による銘柄波及リスク、",
        "および深夜24時の米ISM指数による円高・信用維持率への警告、",
        "ボスが寄り付きで取るべき具体的な防衛・攻めの行動を100字で答えて。"
    ]
    p_final = " ".join(p_parts)

    try:
        # AI解析
        res = model.generate_content(p_final, generation_config={"temperature": 0.4})
        if res and res.text:
            alert_box.warning(res.text)
    except:
        # バックアップメッセージも分割して安全に表示
        b_msg = [
            "🚨 【緊急参謀警告】",
            f"信用損益 {m_profit:+,}円 を考慮すると、",
            "深夜の米ISMによる円高急伸は追証リスクに直結します。",
            "明日は【余力維持】を最優先し、現物株の利確ラインを5%上に再設定してください。"
        ]
        alert_box.error("\n".join(b_msg))

    # グラフ表示
    st.divider()
    st.write("### 🏔️ 資産トレンド")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['日付'], y=df['総資産'], fill='tozeroy', line=dict(color='#007BFF', width=3)))
    fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("データが読み込めません。")

# --- 5. 更新フォーム ---
st.divider()
up_file = st.file_uploader("資産スクショを選択", type=['png', 'jpg', 'jpeg'])
if st.button("AI解析実行"):
    if up_file:
        with st.spinner('Analyzing...'):
            try:
                img = Image.open(up_file)
                # 解析プロンプトも短縮
                ocr_p = '抽出: {"cash":数値, "spot":数値, "margin":数値}'
                res = model.generate_content([ocr_p, img])
                st.write(res.text)
            except:
                st.error("解析エラー")
