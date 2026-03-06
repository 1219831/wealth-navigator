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

# --- 2. 司令部接続（404対策済） ---
@st.cache_resource
def init_system():
    try:
        if "GEMINI_API_KEY" not in st.secrets: return None
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash") # 最も安定したモデル指定
    except: return None

def fetch_data():
    try:
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
        if df is None or df.empty: return None
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        # 数値クレンジング（カンマ・記号を排除）
        for c in ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except: return None

model, df = init_system(), fetch_data()

# --- 3. メイン解析・表示（お気に入りUIの復元） ---
if df is not None:
    valid_df = df[df["総資産"] > 0]
    if valid_df.empty: valid_df = df
    L = valid_df.iloc[-1]
    T, M, S, C = int(L["総資産"]), int(L["信用評価損益"]), int(L["現物時価総額"]), int(L["現物買付余力"])
    now = dt.now()

    # 収支計算
    d_g = T - valid_df.iloc[-2]["総資産"] if len(valid_df) > 1 else 0
    m_s = valid_df[valid_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_g = T - m_s.iloc[0]["総資産"] if not m_s.empty else 0
    lm_s = (now.replace(day=1) - relativedelta(months=1))
    lm_e = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_s) & (df["日付"] < lm_e) & (df["総資産"] > 0)]
    p_g = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    st.title("🚀 保有資産管理シート")
    
    # 【UI戻し】4連メトリクス配置
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥ " + "{:,}".format(T))
        with st.expander("内訳を表示"):
            st.write("┣ 現物時価: ¥ " + "{:,}".format(S))
            st.write("┣ 信用損益: ¥ " + "{:,}".format(M))
            st.write("┗ 買付余力: ¥ " + "{:,}".format(C))
    
    with c2: st.metric("📅 今日の収支", "¥ " + "{:,}".format(int(d_g)))
    with c3: st.metric("🗓️ 今月の収支合計", "¥ " + "{:,}".format(int(m_g)))
    with c4: st.metric("⏳ 先月の収支合計", "¥ " + "{:,}".format(int(p_g)))

    st.progress(max(0.0, min(float(T/GOAL), 1.0)), text="目標達成率: " + "{:.4%}".format(T/GOAL))

    # --- 4. 参謀本部：市場調査（本日 2026/03/06） ---
    st.divider()
    st.subheader("⚔️ 参謀本部：本日の市場調査報告")
    if model:
        p = f"""
        今日は2026年3月6日(金)です。投資参謀として、本日の市場情報を厳密に調査し、以下の3点を必ず報告せよ。
        1.【重要指標】今夜の米雇用統計(22:30)など、本日発表予定の国内外重要指標を時刻付で。ない場合は「なし」。
        2.【決算予定】本日発表予定の国内主要銘柄をコード付で。ない場合は「なし」。
        3.【注意喚起】ボスの信用損益({M}円)を踏まえた、今日一日の取引に対するプロのアドバイスを120字で。
        回答は必ず見やすい箇条書き、またはマークダウン形式で行え。
        """
        try:
            with st.spinner("市場情報を解析中..."):
                res = model.generate_content(p)
                st.markdown(res.text) # markdown形式で確実に表示
        except Exception as e:
            st.error("市場情報エリアでエラーが発生しました。時間を置いて再読み込みしてください。")
    
    # --- 5. グラフ解析（当面はこのまま維持） ---
    st.divider()
    def draw(data, k):
        data["MA5"] = data["総資産"].rolling(5, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_r = [data["総資産"].min()*0.95, data["総資産"].max()*1.05]
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=y_r, tickformat=",.0f"))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("グラフ表示切替:", ["日次推移", "週次推移", "月次推移"], horizontal=True)
    if "日次" in tab: draw(valid_df, "d")
    elif "週次" in tab: draw(valid_df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: draw(valid_df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

# --- 6. 更新セクション（404対策済） ---
st.divider()
st.subheader("📸 スマホ更新：AIキャプチャ解析")
ups = st.file_uploader("証券スクショを最大3枚まで選択", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("🚀 AI統合解析を実行", use_container_width=True, type="primary"):
    if ups and model:
        with st.spinner("AIが画像を統合解析中..."):
            try:
                # 404対策：Contentリスト形式で渡す。型変換を明示
                analysis_input = ["以下の画像から(1)現物時価総額 (2)現物買付余力 (3)信用評価損益 を数値で抽出せよ。"]
                for f in ups[:3]:
                    img = Image.open(f).convert("RGB")
                    analysis_input.append(img)
                
                response = model.generate_content(analysis_input)
                st.success("解析成功")
                st.write(response.text)
            except Exception as e:
                st.error(f"解析失敗: {e}")
