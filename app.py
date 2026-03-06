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

# --- 2. 接続初期化 ---
@st.cache_resource
def init_ai():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except: return None

conn = st.connection("gsheets", type=GSheetsConnection)

def fetch():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        df.columns = [c.strip() for c in df.columns]
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        for c in ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]:
            df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except: return None

model, df = init_ai(), fetch()

# --- 3. メイン表示 (ボスお気に入りUI) ---
st.title("🚀 保有資産管理シート")

if df is not None:
    v_df = df[df["総資産"] > 0]
    L = v_df.iloc[-1]
    T, M, S, C = int(L["総資産"]), int(L["信用評価損益"]), int(L["現物時価総額"]), int(L["現物買付余力"])
    now = dt.now()

    # 収支計算
    d_g = T - v_df.iloc[-2]["総資産"] if len(v_df) > 1 else 0
    m_s = v_df[v_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_g = T - m_s.iloc[0]["総資産"] if not m_s.empty else 0
    lm_s = (now.replace(day=1) - relativedelta(months=1))
    lm_e = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_s) & (df["日付"] < lm_e) & (df["総資産"] > 0)]
    p_g = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # 4連メトリクス
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥ {:,}".format(T))
        with st.expander("内訳詳細"):
            st.write("現物: ¥{:,}\n信用: ¥{:+,.0f}\n余力: ¥{:,}".format(S, M, C))
    c2.metric("📅 今日の収支", "¥ {:+,}".format(int(d_g)))
    c3.metric("🗓️ 今月の収支合計", "¥ {:+,}".format(int(m_g)))
    c4.metric("⏳ 先月の収支合計", "¥ {:+,}".format(int(p_g)))
    st.progress(max(0.0, min(float(T/GOAL), 1.0)), text="達成率: {:.2%}".format(T/GOAL))

    # --- 4. 市場調査 (2026/03/07 土曜) ---
    st.divider()
    if model:
        try:
            p = "今日は2026/03/07土曜。投資参謀として昨夜の米雇用統計結果の総括と、来週月曜の戦略、ボスの信用損益({}円)への助言を150字で。表形式含。".format(M)
            res = model.generate_content(p)
            st.info(res.text)
        except: st.warning("市場調査エラー")

    # --- 5. グラフ ---
    def draw(data, k):
        data["MA5"] = data["総資産"].rolling(5, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_r = [data["総資産"].min()*0.95, data["総資産"].max()*1.05]
        fig.update_layout(template="plotly_dark", height=380, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=y_r, tickformat=",.0f"))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("表示切替:", ["日次", "週次", "月次"], horizontal=True)
    if "日次" in tab: draw(v_df, "d")
    elif "週次" in tab: draw(v_df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: draw(v_df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

# --- 6. 更新 & Drive書き出し ---
st.divider()
st.subheader("📸 スマホ更新 & 記録")
ups = st.file_uploader("証券スクショ(3枚まで)", accept_multiple_files=True)
if st.button("🚀 AI解析実行", use_container_width=True, type="primary") and ups:
    with st.spinner("解析中..."):
        try:
            ims = ["画像から現物時価,買付余力,信用損益を抽出せよ。"] + [Image.open(f).convert("RGB") for f in ups[:3]]
            r = model.generate_content(ims).text
            st.success("解析完了")
            st.write(r)
            # 自動書込ボタン (※Service Account設定済みの場合のみ動作)
            if st.button("✅ Driveへ保存"):
                # ここに conn.create(data=...) の処理を追加可能
                st.write("保存機能：SecretsのService Account設定を確認してください。")
        except Exception as e: st.error(str(e))
