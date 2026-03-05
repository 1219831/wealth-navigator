import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# ==========================================
# 1. コンフィグ（モバイル最適化）
# ==========================================
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="WealthNav PRO", layout="wide", page_icon="📈")

# スマホでの視認性を高めるCSS
st.markdown("""
    <style>
    .stMetric { background-color: rgba(255, 255, 255, 0.05); padding: 10px; border-radius: 10px; }
    div[data-testid="stExpander"] { border: none !important; }
    button { height: 3em !important; }
    </style>
    """, unsafe_allow_html=True)

# ==========================================
# 2. 司令部接続（堅牢なデータ読み込み）
# ==========================================
@st.cache_resource
def init_ai():
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        return gai.GenerativeModel("gemini-1.5-flash")
    except:
        st.error("AI設定エラー：Secretsを確認せよ")
        return None

def load_data():
    try:
        # 接続1: コネクタ試行
        conn = st.connection("gsheets", type=GSheetsConnection)
        df = conn.read(spreadsheet=URL, ttl=0)
    except:
        # 接続2: 直接CSV変換試行（コネクタ不調時のバックアップ）
        csv_url = URL.replace('/edit#gid=', '/export?format=csv&gid=')
        df = pd.read_csv(csv_url)
    
    if df.empty: return None

    # 数値クレンジング
    df["日付"] = pd.to_datetime(df["日付"])
    cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c].astype(str).replace('[^0-9.-]', '', regex=True), errors='coerce').fillna(0).astype(int)
    return df.dropna(subset=["日付"]).sort_values("日付").reset_index(drop=True)

model = init_ai()
df = load_data()

# ==========================================
# 3. 投資解析セクション
# ==========================================
if df is not None:
    now = dt.now()
    L = df.iloc[-1]
    T_total = int(L["総資産"])
    
    # 収支演算（より正確なデルタ計算）
    def get_gain(start_date):
        temp = df[df["日付"] >= start_date]
        return T_total - temp.iloc[0]["総資産"] if not temp.empty else 0

    d_gain = T_total - df.iloc[-2]["総資産"] if len(df) > 1 else 0
    m_gain = get_gain(now.replace(day=1, hour=0, minute=0, second=0))
    # 先月計算
    lm_start = (now.replace(day=1) - relativedelta(months=1))
    lm_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end)]
    p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # ==========================================
    # 4. タクティカル・ダッシュボード（スマホ対応）
    # ==========================================
    st.title("🚀 Wealth Navigator PRO")
    
    # モバイルでは縦に並び、PCでは横に並ぶ
    c1, c2, c3, c4 = st.columns([1.2, 1, 1, 1])
    
    with c1:
        st.metric("💰 総資産合計", f"¥{T_total:,}")
        with st.expander("内訳を表示"):
            st.write(f"┣ 現物時価: ¥{int(L['現物時価総額']):,}")
            st.write(f"┣ 信用損益: ¥{int(L['信用評価損益']):+,}")
            st.write(f"┗ 買付余力: ¥{int(L['現物買付余力']):,}")

    with c2: st.metric("📅 今日の収支", f"¥{d_gain:+,}")
    with c3: st.metric("🗓️ 今月の収支", f"¥{m_gain:+,}")
    with c4: st.metric("⏳ 先月の収支", f"¥{p_gain:+,}")

    st.progress(max(0.0, min(float(T_total/GOAL), 1.0)), text=f"目標達成率: {T_total/GOAL:.4%}")

    # ==========================================
    # 5. 参謀本部（最新イベント動的解析）
    # ==========================================
    st.divider()
    st.subheader("⚔️ 参謀本部：最新マーケット分析")
    
    if model:
        # 日付と信用状況を注入し、リアルタイム性を高める
        prompt = f"""
        本日は{now.strftime('%Y/%m/%d')}です。投資参謀として以下の任務を遂行せよ。
        1. 本日および今週の日本・米国の最重要市場イベント（雇用統計、ISM、決算など）を列挙せよ。
        2. ボスの信用損益（{int(L['信用評価損益'])}円）を踏まえ、明日寄り付きで取るべき「防衛」または「攻め」の具体的な一手を150字以内で指令せよ。
        """
        try:
            res = model.generate_content(prompt)
            st.info(f"💡 **参謀Geminiの進言** ({now.strftime('%m/%d %H:%M')})\n\n{res.text}")
        except:
            st.warning("司令部通信エラー。余力を残しつつ待機せよ。")

    # ==========================================
    # 6. 分析グラフ（プロ仕様）
    # ==========================================
    st.divider()
    st.subheader("🏔️ 資産トレンド（MA5解析）")
    
    def plot_pro(data, key):
        data["MA5"] = data["総資産"].rolling(5).mean()
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=data["日付"], y=data["総資産"], name="資産", fill='tozeroy', line=dict(color='#007BFF', width=3)))
        fig.add_trace(go.Scatter(x=data["日付"], y=data["MA5"], name="5日線", line=dict(color='#FFA500', dash='dot')))
        
        y_min = data["総資産"].min() * 0.98
        y_max = data["総資産"].max() * 1.02
        fig.update_layout(template="plotly_dark", height=400, margin=dict(l=10, r=10, t=10, b=10),
                          legend=dict(orientation="h", y=1.1),
                          yaxis=dict(range=[y_min, y_max], tickformat=",.0f"))
        st.plotly_chart(fig, use_container_width=True, key=key)

    tab = st.radio("表示切替:", ["日次", "週次", "月次"], horizontal=True)
    if tab == "日次": plot_pro(df, "d")
    elif tab == "週次": plot_pro(df.set_index("日付").resample("W").last().dropna().reset_index(), "w")
    else: plot_pro(df.set_index("日付").resample("M").last().dropna().reset_index(), "m")

else:
    st.error("スプレッドシートの読み込みに失敗しました。URLを確認してください。")

# ==========================================
# 7. 更新（スマホ最適化アップローダー）
# ==========================================
st.divider()
st.subheader("📸 スマホ更新：AIマルチスキャン")
# accept_multiple_files=True でカメラロールから複数選択しやすく
ups = st.file_uploader("松井証券の各画面（最大3枚）", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("AI統合解析を実行", use_container_width=True, type="primary"):
    if ups and model:
        with st.spinner("AIが戦況を解析中..."):
            try:
                ims = ["画像から現物時価,買付余力,信用損益を数値で抽出せよ。"] + [Image.open(f) for f in ups[:3]]
                r = model.generate_content(ims)
                st.success("解析成功")
                st.write(r.text)
            except Exception as e:
                st.error(f"解析エラー: {e}")
