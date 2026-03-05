import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定（モバイルUI最適化） ---
GOAL = 100000000
# スプレッドシートのURL（共有設定が「リンクを知っている全員」であることを確認してください）
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="保有資産管理シート", layout="wide", page_icon="📈")

# --- 2. 司令部接続（AI & データ同期） ---
@st.cache_resource
def init_system():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except:
        return None

def fetch_data():
    try:
        # コネクタを通さず、直接エクスポートURLを叩く（最も確実な方法）
        csv_url = URL.replace('/edit', '/export?format=csv')
        df = pd.read_csv(csv_url)
        
        # 数値クレンジング（カンマ、¥、全角を排除）
        df["日付"] = pd.to_datetime(df["日付"], errors='coerce')
        cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
        for c in cols:
            if c in df.columns:
                df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0)
        
        df = df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)
        return df
    except Exception as e:
        st.error(f"データ同期エラー: {e}")
        return None

model = init_system()
df = fetch_data()

# --- 3. 投資解析ロジック ---
if df is not None and not df.empty:
    # 「総資産」が0でない最新の行を取得（入力中の0円行を無視）
    valid_df = df[df["総資産"] > 0]
    if valid_df.empty:
        st.warning("有効な資産データが見つかりません。シートを確認してください。")
        st.stop()
        
    L = valid_df.iloc[-1] # 最新の有効データ
    T_total = int(L["総資産"])
    V_spot = int(L["現物時価総額"])
    P_margin = int(L["信用評価損益"])
    C_cash = int(L["現物買付余力"])
    
    # 収支計算
    now = dt.now()
    d_gain = T_total - valid_df.iloc[-2]["総資産"] if len(valid_df) > 1 else 0
    
    # 今月
    m_start = valid_df[valid_df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
    m_gain = T_total - m_start.iloc[0]["総資産"] if not m_start.empty else 0
    
    # 先月
    lm_start = (now.replace(day=1) - relativedelta(months=1))
    lm_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end) & (df["総資産"] > 0)]
    p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # --- 4. メインUI表示（要求仕様順） ---
    st.title("🚀 保有資産管理シート PRO")
    
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("💰 現状総資産合計", f"¥{T_total:,}")
        with st.expander("内訳を表示"):
            st.write(f"┣ 現物保有銘柄: ¥{V_spot:,}")
            st.write(f"┣ 信用評価損益: ¥{P_margin:+,}")
            st.write(f"┗ 現物買付余力: ¥{C_cash:,}")
    
    with c2: st.metric("📅 今日の収支", f"¥{d_gain:+,}")
    with c3: st.metric("🗓️ 今月の収支合計", f"¥{m_gain:+,}")
    with c4: st.metric("⏳ 先月の収支合計", f"¥{p_gain:+,}")

    # 目標達成率
    progress = max(0.0, min(float(T_total/GOAL), 1.0))
    st.progress(progress, text=f"目標達成率: {T_total/GOAL:.4%}")

    # --- 5. 参謀本部：市場イベント調査報告 ---
    st.divider()
    st.subheader("⚔️ 参謀本部：本日の市場調査報告")
    
    if model:
        # 2026年3月6日のコンテキストでプロンプト作成
        prompt = f"""
        本日は2026年3月6日（金）です。投資参謀として以下の情報を調査し、報告せよ。
        1. 【重要指標】本日発表予定の国内・海外の重要経済指標（指標名・日本時間）を列挙せよ。ない場合は「なし」とせよ。
        2. 【決算予定】本日決算発表予定の国内主要銘柄（銘柄名・コード）を列挙せよ。ない場合は「なし」とせよ。
        3. 【注意喚起】上記イベントと、ボスの現在の信用評価損益（{P_margin}円）を考慮し、プロの投資家として今日1日の取引に対する具体的な注意喚起とコメントを150字で述べよ。
        """
        try:
            res = model.generate_content(prompt)
            st.info(f"💡 **ジェミニの戦略分析** (2026/03/06)\n\n{res.text}")
        except:
            st.warning("司令部通信エラー。重要指標の発表に備え、警戒を怠るな。")

    # --- 6. グラフ解析（日次・週次・月次） ---
    st.divider()
    st.subheader("🏔️ 資産・収支トレンド")
    
    def render_pro_chart(data, k):
        data["MA5"] = data["総資産"].rolling(5).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="総資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        y_range = [data["総資産"].min()*0.95, data["総資産"].max()*1.05]
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10),
                          yaxis=dict(range=y_range, tickformat=",.0f"), xaxis=dict(showgrid=False))
        st.plotly_chart(fig, use_container_width=True, key=k)

    tab = st.radio("グラフ表示切替:", ["日次推移", "週次推移", "月次推移"], horizontal=True)
    if "日次" in tab: render_pro_chart(valid_df, "d")
    elif "週次" in tab: render_pro_chart(valid_df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: render_pro_chart(valid_df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

# --- 7. 更新（スマホ・キャプチャ対応） ---
st.divider()
st.subheader("📸 スマホ更新：証券キャプチャ解析")
st.caption("松井証券の画面スクショを3枚まで選択してください。AIが自動集計します。")
ups = st.file_uploader("画像を選択", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("AI統合解析を実行", use_container_width=True, type="primary"):
    if ups and model:
        with st.spinner("戦況を解析中..."):
            try:
                ims = ["画像から現物時価、買付余力、信用損益を数値で抽出せよ。"] + [Image.open(f) for f in ups[:3]]
                r = model.generate_content(ims)
                st.success("解析成功")
                st.write(r.text)
            except Exception as e:
                st.error(f"解析エラー: {e}")
