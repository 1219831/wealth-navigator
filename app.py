import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav PRO", layout="wide")

# --- 2. 司令部接続 ---
@st.cache_resource
def init_system():
    try:
        if "GEMINI_API_KEY" not in st.secrets: return None
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except: return None

def fetch_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
        if df is None or df.empty: return None
        
        # 列名の余計な空白を削除
        df.columns = [c.strip() for c in df.columns]
        
        # 日付変換
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        
        # 数値クレンジング（徹底排除）
        target_cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
        for c in target_cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except:
        return None

model, df = init_system(), fetch_data()

# --- 3. メイン解析・表示 ---
if df is not None:
    # 資産が入力されている最新行を特定
    valid_df = df[df["総資産"] > 0]
    if valid_df.empty: valid_df = df
    
    L = valid_df.iloc[-1]
    T = float(L.get("総資産", 0))
    M = float(L.get("信用評価損益", 0))
    S = float(L.get("現物時価総額", 0))
    C = float(L.get("現物買付余力", 0))
    now = dt.now()

    # 収支計算 (クラッシュ防止策)
    def safe_int(val):
        try: return int(float(val))
        except: return 0

    # 今日の収支
    d_g = T - float(valid_df.iloc[-2]["総資産"]) if len(valid_df) > 1 else 0
    
    # 今月の収支
    m_s = valid_df[valid_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_g = T - float(m_s.iloc[0]["総資産"]) if not m_s.empty else 0
    
    # 先月の収支
    lm_s = (now.replace(day=1, hour=0, minute=0, second=0) - relativedelta(months=1))
    lm_e = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_s) & (df["日付"] < lm_e) & (df["総資産"] > 0)]
    p_g = float(lm_df.iloc[-1]["総資産"]) - float(lm_df.iloc[0]["総資産"]) if not lm_df.empty else 0

    st.title("🚀 保有資産管理シート")
    
    # 【UI完全復元】
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥ " + "{:,}".format(safe_int(T)))
        with st.expander("内訳を表示"):
            st.write("┣ 現物時価: ¥ " + "{:,}".format(safe_int(S)))
            st.write("┣ 信用損益: ¥ " + "{:,}".format(safe_int(M)))
            st.write("┗ 買付余力: ¥ " + "{:,}".format(safe_int(C)))
    
    with c2: st.metric("📅 今日の収支", "¥ " + "{:,}".format(safe_int(d_g)))
    with c3: st.metric("🗓️ 今月の収支合計", "¥ " + "{:,}".format(safe_int(m_g)))
    with c4: st.metric("⏳ 先月の収支合計", "¥ " + "{:,}".format(safe_int(p_g)))

    st.progress(max(0.0, min(float(T/GOAL), 1.0)), text="目標達成率: " + "{:.4%}".format(T/GOAL))

    # --- 4. 参謀本部：市場調査 (2026/03/07土曜版) ---
    st.divider()
    st.subheader("⚔️ 参謀本部：マーケット調査報告")
    if model:
        p = f"""
        本日は2026年3月7日(土)です。週明けに向けた市場調査を行い、以下を報告せよ。
        1.【重要指標】昨夜(金)の米雇用統計の結果と市場の反応、および来週月曜の重要指標。
        2.【決算予定】来週月曜日に決算発表を控える国内主要銘柄。
        3.【アドバイス】ボスの信用損益({safe_int(M)}円)を踏まえた、週末の心構えを120字で。
        """
        try:
            with st.spinner("戦況を分析中..."):
                res = model.generate_content(p)
                st.markdown(res.text)
        except: st.warning("司令部通信エラー。週末の米国市場の結果をチェックしてください。")
    
    # --- 5. グラフ解析 ---
    st.divider()
    def draw(data, k):
        data["MA5"] = data["総資産"].rolling(5, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_r = [data["総資産"].min()*0.95, data["総資産"].max()*1.05]
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=y_r, tickformat=",.0f"))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("表示切替:", ["日次推移", "週次推移", "月次推移"], horizontal=True)
    if "日次" in tab: draw(valid_df, "d_g")
    elif "週次" in tab: draw(valid_df.set_index("日付").resample("W").last().dropna().reset_index(), "w_g")
    else: draw(valid_df.set_index("日付").resample("M").last().dropna().reset_index(), "m_g")

else:
    st.error("スプレッドシートが読み込めません。")

# --- 6. 更新セクション ---
st.divider()
st.subheader("📸 スマホ更新：AIキャプチャ解析")
ups = st.file_uploader("スクショを選択(最大3枚)", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])
if st.button("🚀 AI統合解析を実行", use_container_width=True, type="primary"):
    if ups and model:
        with st.spinner("解析中..."):
            try:
                ims = ["画像から(1)現物時価(2)買付余力(3)信用損益を抽出せよ。"] + [Image.open(f).convert("RGB") for f in ups[:3]]
                st.write(model.generate_content(ims).text)
            except Exception as e: st.error(str(e))
