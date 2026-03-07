import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav PRO", layout="wide")

# --- 2. 司令部接続 ---
@st.cache_resource
def init_ai():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel('gemini-1.5-flash')
    except: return None

conn = st.connection("gsheets", type=GSheetsConnection)

def fetch():
    try:
        df = conn.read(spreadsheet=URL, ttl=0)
        df.columns = [c.strip() for c in df.columns]
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        for c in ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except: return None

model, df = init_ai(), fetch()

# --- 3. 手入力セクション (サイドバー) ---
st.sidebar.header("📝 資産データ手入力")
with st.sidebar:
    in_s = st.number_input("現物時価総額 (円)", value=0, step=10000)
    in_m = st.number_input("信用評価損益合計 (円)", value=0, step=10000)
    in_c = st.number_input("現物買付余力 (円)", value=0, step=10000)
    in_t = in_s + in_m + in_c
    
    st.divider()
    st.write("📊 入力値の総資産: ¥ {:+,}".format(in_t))
    
    # 書き出しボタン (Service Account設定時のみ有効)
    if st.button("✅ スプレッドシートに記録", use_container_width=True):
        try:
            new_row = pd.DataFrame([{
                "日付": dt.now().strftime("%Y/%m/%d"),
                "総資産": in_t,
                "現物時価総額": in_s,
                "現物買付余力": in_c,
                "信用評価損益": in_m
            }])
            conn.create(spreadsheet=URL, data=new_row)
            st.success("Driveへ書き込みました！")
            st.balloons()
        except:
            st.warning("書き込み権限がありません。解析結果をコピーしてシートに貼ってください。")
            st.code(f"{dt.now().strftime('%Y/%m/%d')},{in_t},{in_s},{in_c},{in_m}")

# --- 4. メイン表示 (ボスお気に入りUI) ---
st.title("🚀 保有資産管理シート")

if df is not None:
    v_df = df[df["総資産"] > 0]
    L = v_df.iloc[-1]
    
    # 入力値があればそれを使う、なければ最新データを使う
    cur_t = in_t if in_t != 0 else int(L["総資産"])
    cur_m = in_m if in_t != 0 else int(L["信用評価損益"])
    cur_s = in_s if in_t != 0 else int(L["現物時価総額"])
    cur_c = in_c if in_t != 0 else int(L["現物買付余力"])
    
    now = dt.now()

    # 収支計算 (最新行との比較)
    d_g = cur_t - v_df.iloc[-1]["総資産"] if in_t != 0 else (cur_t - v_df.iloc[-2]["総資産"] if len(v_df)>1 else 0)
    m_s = v_df[v_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_g = cur_t - m_s.iloc[0]["総資産"] if not m_s.empty else 0
    lm_s = (now.replace(day=1) - relativedelta(months=1))
    lm_e = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_s) & (df["日付"] < lm_e) & (df["総資産"] > 0)]
    p_g = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # 4連メトリクス
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥ {:,}".format(cur_t))
        with st.expander("内訳を表示"):
            st.write("現物: ¥{:,}\n信用: ¥{:+,.0f}\n余力: ¥{:,}".format(cur_s, cur_m, cur_c))
    c2.metric("📅 今日の収支", "¥ {:+,}".format(int(d_g)))
    c3.metric("🗓️ 今月の収支合計", "¥ {:+,}".format(int(m_g)))
    c4.metric("⏳ 先月の収支合計", "¥ {:+,}".format(int(p_g)))
    st.progress(max(0.0, min(float(cur_t/GOAL), 1.0)), text="目標達成率: {:.2%}".format(cur_t/GOAL))

    # --- 5. 参謀本部：市場調査 (2026/03/07 土曜) ---
    st.divider()
    if model:
        try:
            p = "今日は2026/03/07土曜。昨夜の米雇用統計結果(NFP)を踏まえ、来週月曜の日本市場への影響と、ボスの信用損益({}円)への具体的な戦略を150字で。表形式含。".format(cur_m)
            st.info(model.generate_content(p).text)
        except: st.warning("市場調査中...")

    # --- 6. グラフ ---
    def draw(data, k):
        data["MA5"] = data["総資産"].rolling(5, min_periods=1).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_r = [data["総資産"].min()*0.95, data["総資産"].max()*1.05]
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10), yaxis=dict(range=y_r, tickformat=",.0f"))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("表示切替:", ["日次", "週次", "月次"], horizontal=True)
    if "日次" in tab: draw(v_df, "d")
    elif "週次" in tab: draw(v_df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: draw(v_df.set_index("日付").resample("M").last().dropna().reset_index(), "m")
