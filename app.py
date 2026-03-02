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

st.set_page_config(page_title="Wealth Nav Pro", layout="wide", page_icon="📈")

# --- 2. API連携 (404エラー対策) ---
try:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
    # モデル名は文字列で直接指定し、エラーを回避
    model = genai.GenerativeModel("gemini-1.5-flash")
except Exception as e:
    st.error("API設定エラー")
    st.stop()

# --- 3. データ取得 ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data():
    try:
        raw = conn.read(spreadsheet=URL, ttl=0)
        if raw.empty: return None
        raw["日付"] = pd.to_datetime(raw["日付"], errors="coerce")
        df = raw.dropna(subset=["日付"]).sort_values("日付").drop_duplicates("日付", keep="last").reset_index(drop=True)
        return df
    except:
        return None

df = load_data()

# --- 4. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")

if df is not None and not df.empty:
    L = df.iloc[-1]
    T = L["総資産"]
    M = L["信用評価損益"]
    now = datetime.now()
    
    # 収支計算
    d_gain, m_gain, p_gain = 0, 0, 0
    try:
        if len(df) > 1: d_gain = T - df.iloc[-2]["総資産"]
        m_start = df[df["日付"] >= now.replace(day=1, hour=0, minute=0, second=0)]
        if not m_start.empty: m_gain = T - m_start.iloc[0]["総資産"]
        lm_end = now.replace(day=1, hour=0, minute=0, second=0)
        lm_start = (lm_end - pd.DateOffset(months=1))
        lm_data = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end)]
        if not lm_data.empty: p_gain = lm_data.iloc[-1]["総資産"] - lm_data.iloc[0]["総資産"]
    except: pass

    # --- A. 資産ダッシュボード (断線対策: f-stringを最小限に) ---
    st.subheader("📊 資産状況 & 収支成績")
    c1, c2, c3, c4 = st.columns([1, 1, 1, 1])
    
    with c1:
        st.metric("今日の収支", f"¥{int(d_gain):+d}")
        st.write("総資産:", f"¥{int(T):,}")
        st.write("信用損益:", f"¥{int(M):+,}")
    
    with c2:
        st.metric("先月の収支", f"¥{int(p_gain):+,}")
        st.write("現物時価:", f"¥{int(L['現物時価総額']):,}")

    with c3:
        st.metric("今月の収支", f"¥{int(m_gain):+,}")
        st.write("買付余力:", f"¥{int(L['現物買付余力']):,}")

    with c4:
        st.metric("1億円まで", f"¥{int(GOAL - T):,}")
        st.write("達成率:", f"{T/GOAL:.4%}")
        st.progress(max(0.0, min(float(T/GOAL), 1.0)))

    # --- B. 参謀本部 ---
    st.divider()
    st.subheader("⚔️ 参謀本部：決戦指令ボード")
    st.success("📈 **【3/2 注目】**: 伊藤園(2593)・ピープル(7865)決算 / 24時 米ISM指数")
    
    # 指令テキスト
    prompt = "投資参謀として助言せよ。信用損益" + str(M) + "円のボスへ。3/2の伊藤園・ピープル決算と米ISMの影響、明日寄り付きの具体的行動を120字で。"
    try:
        res = model.generate_content(prompt)
        if res.text:
            st.info("💡 **参謀Geminiの進言**: " + res.text)
    except:
        st.warning("🚨 **参謀の緊急指令**: 深夜の米ISMによる円高リスクを警戒せよ。")

    # --- C. 期間切り替えグラフ ---
    st.divider()
    st.write("### 🏔️ 資産トレンド推移")
    tabs = st.tabs(["日次", "週次", "月次"])
    
    def plot(data):
        fig = go.Figure(go.Scatter(x=data["日付"], y=data["総資産"], fill="tozeroy", line=dict(color="#007BFF")))
        fig.update_layout(template="plotly_dark", height=350, margin=dict(l=10, r=10, t=10, b=10))
        return fig

    with tabs[0]: st.plotly_chart(plot(df), use_container_width=True, key="d")
    with tabs[1]:
        df_w = df.resample("W", on="日付").last().reset_index().dropna()
        st.plotly_chart(plot(df_w), use_container_width=True, key="w")
    with tabs[2]:
        df_m = df.resample("M", on="日付").last().reset_index().dropna()
        st.plotly_chart(plot(df_m), use_container_width=True, key="m")

else:
    st.info("データが読み込めません。")

# --- 5. 更新セクション (404エラー & 複数枚対応) ---
st.divider()
st.subheader("📸 資産状況の更新 (最大3枚)")
up_files = st.file_uploader("スクショを選択(最大3枚)", type=["png", "jpg", "jpeg"], accept_multiple_files=True)

if st.button("AI統合解析実行"):
    if up_files:
        with st.spinner("解析中..."):
            try:
                # 404対策: 非常にシンプルなリストで渡す
                contents = ["以下の画像から現物時価(spot),買付余力(cash),信用損益(margin)を数値で抽出して。"]
                for f in up_files[:3]:
                    contents.append(Image.open(f))
                
                response = model.generate_content(contents)
                st.write("解析結果:", response.text)
            except Exception as e:
                st.error("解析失敗: モデルへのアクセスに問題があります。")
