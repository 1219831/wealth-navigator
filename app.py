import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
from dateutil.relativedelta import relativedelta
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# ==========================================
# 1. 構成定義 (Configuration)
# ==========================================
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
ST_COLOR = {"blue": "#007BFF", "orange": "#FFA500", "grid": "rgba(255,255,255,0.1)"}

st.set_page_config(page_title="Wealth Navigator PRO", layout="wide", page_icon="📈")

# ==========================================
# 2. 司令部接続 (API & Data Connection)
# ==========================================
@st.cache_resource
def initialize_system():
    # API初期化
    try:
        gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
        model = gai.GenerativeModel("gemini-1.5-flash")
    except:
        st.error("AI司令部への接続に失敗しました。API Keyを確認してください。")
        st.stop()
    return model

def load_and_clean_data():
    conn = st.connection("gsheets", type=GSheetsConnection)
    try:
        raw = conn.read(spreadsheet=URL, ttl=0)
        if raw.empty: return None
        
        # データクレンジング・エンジン
        df = raw.copy()
        df["日付"] = pd.to_datetime(df["日付"])
        
        # 金融数値の正規化（記号・カンマを排除し整数化）
        target_cols = ["総資産", "現物時価総額", "信用評価損益", "現物買付余力"]
        for col in target_cols:
            if col in df.columns:
                df[col] = pd.to_numeric(
                    df[col].astype(str).replace('[^0-9.-]', '', regex=True), 
                    errors='coerce'
                ).fillna(0).astype(int)
        
        return df.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)
    except Exception as e:
        st.error(f"データ整合性エラー: {e}")
        return None

# システム起動
model = initialize_system()
df = load_and_clean_data()

# ==========================================
# 3. 投資解析エンジン (Analysis Logic)
# ==========================================
if df is not None:
    now = dt.now()
    L = df.iloc[-1] # 最新レコード
    
    # 資産クラス
    T_total = int(L["総資産"])
    V_spot = int(L["現物時価総額"])
    P_margin = int(L["信用評価損益"])
    C_cash = int(L["現物買付余力"])
    
    # 収支演算
    def calc_diff(target_date):
        past_data = df[df["日付"] < target_date]
        if past_data.empty: return 0
        return T_total - past_data.iloc[-1]["総資産"]

    today_gain = T_total - df.iloc[-2]["総資産"] if len(df) > 1 else 0
    this_month_gain = calc_diff(now.replace(day=1, hour=0, minute=0, second=0))
    
    # 先月収支の厳密計算
    last_month_start = (now.replace(day=1) - relativedelta(months=1))
    last_month_end = now.replace(day=1, hour=0, minute=0, second=0)
    lm_df = df[(df["日付"] >= last_month_start) & (df["日付"] < last_month_end)]
    prev_month_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0

    # ==========================================
    # 4. メインUI：タクティカル・ダッシュボード
    # ==========================================
    st.title("🚀 Wealth Navigator PRO")
    
    # KPIセクション
    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    
    with kpi1:
        st.metric("💰 現状総資産合計", f"¥{T_total:,}")
        with st.expander("資産内訳詳細"):
            st.write(f"┣ 現物保有時価: ¥{V_spot:,}")
            st.write(f"┣ 信用評価損益: ¥{P_margin:+,}")
            st.write(f"┗ 現物買付余力: ¥{C_cash:,}")

    with kpi2:
        st.metric("📅 今日の収支", f"¥{today_gain:+,}")
        st.write(f"目標(1億)まで: ¥{GOAL - T_total:,}")

    with kpi3:
        st.metric("🗓️ 今月の収支合計", f"¥{this_month_gain:+,}")
        st.progress(max(0.0, min(float(T_total/GOAL), 1.0)))

    with kpi4:
        st.metric("⏳ 先月の収支合計", f"¥{prev_month_gain:+,}")
        st.write(f"目標達成率: {T_total/GOAL:.4%}")

    # ==========================================
    # 5. 参謀本部：AIマーケット・ストラテジー
    # ==========================================
    st.divider()
    st.subheader("⚔️ 参謀本部：マーケット指令")
    
    current_date_str = now.strftime("%Y年%m月%d日")
    # 投資家としてのコンテキストをAIに注入
    strategy_prompt = f"""
    あなたはプロの投資参謀です。本日の日付は{current_date_str}。
    ボスの現在の運用状況：
    - 総資産：{T_total}円
    - 信用損益：{P_margin}円（リスク許容度の判断材料）
    - 買付余力：{C_cash}円
    
    上記を踏まえ、本日および直近の重要市場イベント（国内・海外指標、決算銘柄）を予測・列挙し、
    ボスのポートフォリオを守り、攻めるための具体的アクションを150字以内で「断固たる指令」として述べてください。
    """
    
    with st.container():
        try:
            response = model.generate_content(strategy_prompt)
            st.info(f"💡 **参謀Geminiの進言** ({current_date_str}時点)\n\n{response.text}")
        except:
            st.warning("⚠️ 司令部通信途絶。市場ボラティリティに備え、余力を維持しつつ待機せよ。")

    # ==========================================
    # 6. 分析セクション：マルチタイムフレーム・チャート
    # ==========================================
    st.divider()
    st.subheader("🏔️ 資産トレンド推移（プロ仕様解析）")
    
    def render_chart(target_df, key_suffix):
        # 5日移動平均線の算出
        target_df["MA5"] = target_df["総資産"].rolling(window=5).mean()
        
        fig = go.Figure()
        # メインライン（総資産）
        fig.add_trace(go.Scatter(
            x=target_df["日付"], y=target_df["総資産"], 
            name="総資産額", fill='tozeroy',
            line=dict(color=ST_COLOR["blue"], width=3)
        ))
        # 5日移動平均線
        fig.add_trace(go.Scatter(
            x=target_df["日付"], y=target_df["MA5"], 
            name="MA5 (5日線)", 
            line=dict(color=ST_COLOR["orange"], width=2, dash='dot')
        ))
        
        # プロ仕様のY軸マージン設定
        y_buffer = (target_df["総資産"].max() - target_df["総資産"].min()) * 0.1
        y_min = target_df["総資産"].min() - y_buffer
        y_max = target_df["総資産"].max() + y_buffer
        
        fig.update_layout(
            template="plotly_dark", height=450,
            margin=dict(l=20, r=20, t=30, b=20),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
            yaxis=dict(range=[y_min, y_max], showgrid=True, gridcolor=ST_COLOR["grid"], tickformat=",.0f"),
            xaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig, use_container_width=True, key=f"chart_{key_suffix}")

    chart_tab = st.radio("時間軸切り替え:", ["日次", "週次", "月次"], horizontal=True)
    
    if chart_tab == "日次":
        render_chart(df, "daily")
    elif chart_tab == "週次":
        df_w = df.set_index("日付").resample("W").last().dropna().reset_index()
        render_chart(df_w, "weekly")
    else:
        df_m = df.set_index("日付").resample("M").last().dropna().reset_index()
        render_chart(df_m, "monthly")

else:
    st.error("スプレッドシートへの接続が確認できません。URLとSecrets設定を再点検してください。")

# ==========================================
# 7. センサー入力：3枚同時スクショ解析
# ==========================================
st.divider()
st.subheader("📸 資産状況の更新（AIマルチ・スキャン）")
uploaded_files = st.file_uploader("松井証券の各画面スクショを選択（最大3枚）", accept_multiple_files=True, type=['png', 'jpg', 'jpeg'])

if st.button("AI統合解析実行"):
    if uploaded_files:
        with st.spinner("3枚の画像を統合解析中..."):
            try:
                # AIへのOCR指示
                ocr_instructions = "画像から(1)現物時価総額 (2)現物買付余力 (3)信用評価損益 を探し、その合計と内訳を数値で抽出せよ。"
                analysis_payload = [ocr_instructions]
                for file in uploaded_files[:3]:
                    analysis_payload.append(Image.open(file))
                
                result = model.generate_content(analysis_payload)
                st.success("解析完了")
                st.write(result.text)
                st.info("※解析結果をコピーし、スプレッドシートへ反映させてください。")
            except Exception as e:
                st.error(f"解析失敗: {e}")
