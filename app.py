import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime as dt
import google.generativeai as gai
from PIL import Image
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"
st.set_page_config(page_title="WealthNav", layout="wide")

# --- 2. API連携 ---
try:
    gai.configure(api_key=st.secrets["GEMINI_API_KEY"].strip())
    model = gai.GenerativeModel("gemini-1.5-flash")
except:
    st.error("API設定エラー"); st.stop()

# --- 3. データ処理 ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = conn.read(spreadsheet=URL, ttl=0)

if df_raw.empty:
    st.warning("スプレッドシートが空、または読み込めません。")
    st.stop()

df = df_raw.copy()
df["日付"] = pd.to_datetime(df["日付"])
df = df.dropna(subset=["日付"]).sort_values("日付")
df = df.drop_duplicates("日付", keep="last").reset_index(drop=True)

# --- 4. メイン画面 ---
st.title("🚀 Wealth Navigator PRO")
L = df.iloc[-1]
T = L["総資産"]
M = L["信用評価損益"]
now = dt.now()

# 収支計算
d_g, m_g, p_g = 0, 0, 0
try:
    if len(df) > 1:
        d_g = T - df.iloc[-2]["総資産"]
    
    # 今月 (1日以降)
    ms_date = now.replace(day=1, hour=0, minute=0, second=0)
    m_s = df[df["日付"] >= ms_date]
    if not m_s.empty:
        m_g = T - m_s.iloc[0]["総資産"]
    
    # 先月
    le_date = ms_date
    ls_date = (le_date - pd.DateOffset(months=1))
    ld = df[(df["日付"] >= ls_date) & (df["日付"] < le_date)]
    if not ld.empty:
        p_g = ld.iloc[-1]["総資産"] - ld.iloc[0]["総資産"]
except:
    pass

# --- A. 資産ダッシュボード (順序: 今日 -> 先月 -> 今月) ---
st.subheader("📊 収支成績 & 資産状況")
c1, c2, c3, c4 = st.columns(4)

with c1:
    st.metric("今日の収支", "¥" + str(int(d_g)))
    st.write("総資産: ¥" + str(int(T)))

with c2:
    st.metric("先月の収支", f"¥{int(p_g):,}")
    st.write("信用損益: ¥" + str(int(M)))

with c3:
    st.metric("今月の収支", f"¥{int(m_g):,}")
    st.write("余力: ¥" + str(int(L["現物買付余力"])))

with c4:
    st.metric("1億円まで", "¥" + str(int(GOAL - T)))
    st.progress(max(0.0, min(float(T/GOAL), 1.0)))

# --- B. 参謀本部 ---
st.divider()
st.subheader("⚔️ 参謀本部")
st.success("📈 3/3注目: 伊藤園・ピープル決算反応 / 今夜米ISM指数 / ドル円動向")

prompt = "信用損益" + str(M) + "円のボスへ、明日寄り付きの具体的行動を100字で指令せよ。"
try:
    res = model.generate_content(prompt)
    if res.text:
        st.info(res.text)
except:
    st.warning("参謀指令：ボラティリティ警戒。余力維持を最優先せよ。")

# --- C. 資産トレンドグラフ (タブを使わず直列表示で確認) ---
st.divider()
st.subheader("🏔️ 資産トレンド推移")

# グラフ作成用関数
def make_chart(data, title_text):
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=data["日付"], 
        y=data["総資産"], 
        mode='lines+markers',
        fill='tozeroy',
        line=dict(color='#007BFF', width=3)
    ))
    fig.update_layout(
        title=title_text,
        template="plotly_dark",
        height=400,
        margin=dict(l=20, r=20, t=40, b=20),
        xaxis=dict(showgrid=False),
        yaxis=dict(showgrid=True, gridcolor='gray')
    )
    return fig

# 期間切り替え用のラジオボタン
period = st.radio("表示期間:", ["日次", "週次", "月次"], horizontal=True)

if period == "日次":
    st.plotly_chart(make_chart(df, "Daily Trend"), use_container_width=True)
elif period == "週次":
    df_w = df.set_index("日付").resample("W").last().dropna().reset_index()
    st.plotly_chart(make_chart(df_w, "Weekly Trend"), use_container_width=True)
else:
    df_m = df.set_index("日付").resample("M").last().dropna().reset_index()
    st.plotly_chart(make_chart(df_m, "Monthly Trend"), use_container_width=True)

# --- 5. 更新 (3枚同時解析) ---
st.divider()
st.subheader("📸 スクショ更新 (最大3枚同時選択)")
ups = st.file_uploader("証券アプリの画像を選択", accept_multiple_files=True)

if st.button("AI統合解析実行"):
    if ups:
        with st.spinner("AIが複数画像をスキャン中..."):
            try:
                ins = ["画像から現物時価,買付余力,信用損益を数値で抽出せよ。"]
                for f in ups[:3]:
                    ins.append(Image.open(f))
                r = model.generate_content(ins)
                st.write("解析結果:", r.text)
            except Exception as e:
                st.error("解析失敗: " + str(e))
