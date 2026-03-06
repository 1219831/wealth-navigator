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
st.set_page_config(page_title="保有資産管理シート", layout="wide")

# --- 2. 司令部接続（堅牢な認証） ---
@st.cache_resource
def init_system():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except: return None

def fetch_data():
    try:
        # 安全な認証コネクタを使用
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
        
        if df is None or df.empty: return None

        # データ洗浄
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        
        return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
    except Exception as e:
        st.error("データ同期エラー（401/403等）: " + str(e))
        st.info("💡 ヒント: スプレッドシートの共有設定が『閲覧可能』になっているか確認してください。")
        return None

model = init_system()
df = fetch_data()

# --- 3. 投資解析 ---
if df is not None and not df.empty:
    valid_df = df[df["総資産"] > 0]
    if valid_df.empty: st.stop()
        
    L = valid_df.iloc[-1]
    T_total = int(L["総資産"])
    now = dt.now()

    # 収支計算
    d_gain = T_total - valid_df.iloc[-2]["総資産"] if len(valid_df) > 1 else 0
    m_start = valid_df[valid_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_gain = T_total - m_start.iloc[0]["総資産"] if not m_start.empty else 0
    lm_start = (now.replace(day=1) - relativedelta(months=1))
    lm_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end) & (df["総資産"] > 0)]
    p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # --- 4. メイン表示 ---
    st.title("🚀 保有資産管理シート")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", "¥" + "{:,}".format(T_total))
        with st.expander("資産内訳"):
            st.write("┣ 現物時価: ¥" + "{:,}".format(int(L["現物時価総額"])))
            st.write("┣ 信用損益: ¥" + "{:,}".format(int(L["信用評価損益"])))
            st.write("┗ 買付余力: ¥" + "{:,}".format(int(L["現物買付余力"])))
    
    with c2: st.metric("📅 今日の収支", "¥" + "{:,}".format(int(d_gain)))
    with c3: st.metric("🗓️ 今月の収支", "¥" + "{:,}".format(int(m_gain)))
    with c4: st.metric("⏳ 先月の収支", "¥" + "{:,}".format(int(p_gain)))

    st.progress(max(0.0, min(float(T_total/GOAL), 1.0)), text="目標達成率: " + "{:.4%}".format(T_total/GOAL))

    # --- 5. 参謀本部：市場イベント自動調査 ---
    st.divider()
    st.subheader("⚔️ 参謀本部：本日の市場調査報告")
    
    if model:
        # プロフェッショナルな調査を指示するプロンプト
        research_prompt = """
        本日は2026年3月6日（金）です。投資のプロフェッショナルとして以下を厳密に調査し、報告せよ。
        
        【重要指標の調査】
        本日発表の国内・海外の重要経済指標を「指標名」「発表時刻」の形式で列挙せよ。発表がない場合は「発表なし」と明記せよ。
        【主要銘柄の決算調査】
        本日決算発表予定の国内主要銘柄（東証プライム中心）を「銘柄名」「銘柄コード」の形式で列挙せよ。発表がない場合は「発表なし」と明記せよ。
        【プロの注意喚起】
        上記イベントと、ボスの現在の信用評価損益（""" + str(int(L["信用評価損益"])) + """円）を考慮し、今日1日の取引に対するプロとしてのリスク管理、注意喚起を150字で述べよ。
        """
        try:
            res = model.generate_content(research_prompt)
            st.info(res.text)
        except: st.warning("司令部通信エラー。自力での情報確認を推奨。")

    # --- 6. グラフ解析 ---
    st.divider()
    def draw_chart(data, k):
        data["MA5"] = data["総資産"].rolling(5).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="総資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_min, y_max = data["総資産"].min()*0.95, data["総資産"].max()*1.05
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(range=[y_min, y_max], tickformat=",.0f"), xaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("グラフ表示:", ["日次", "週次", "月次"], horizontal=True)
    if "日次" in tab: draw_chart(valid_df, "d")
    elif "週次" in tab: draw_chart(valid_df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: draw_chart(valid_df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

# --- 7. 更新セクション ---
st.divider()
st.subheader("📸 スマホ更新：AIキャプチャ解析")
ups = st.file_uploader("スクショを選択（最大3枚）", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("AI統合解析を実行", use_container_width=True, type="primary"):
    if ups and model:
        with st.spinner("解析中..."):
            try:
                ims = ["画像から現物時価,買付余力,信用損益を数値で抽出せよ。"] + [Image.open(f) for f in ups[:3]]
                r = model.generate_content(ims)
                st.success("解析成功")
                st.write(r.text)
            except Exception as e: st.error(str(e))
