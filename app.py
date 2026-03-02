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
st.set_page_config(page_title="WealthNav PRO", layout="wide", page_icon="📈")

# --- 2. API連携 (徹底的なエラー捕捉) ---
# 前回の「Keyを確認してください」という固定メッセージを廃止し、詳細を表示します
@st.cache_resource
def init_gemini():
    try:
        if "GEMINI_API_KEY" not in st.secrets:
            return None, "Streamlit Secretsに 'GEMINI_API_KEY' が見つかりません。"
        
        api_key = st.secrets["GEMINI_API_KEY"].strip()
        genai.configure(api_key=api_key)
        # 接続確認のためのダミー実行
        model = genai.GenerativeModel("gemini-1.5-flash")
        return model, None
    except Exception as e:
        return None, f"初期化エラー: {str(e)}"

model, api_err = init_gemini()

# --- 3. データ処理ロジック ---
conn = st.connection("gsheets", type=GSheetsConnection)
df_raw = conn.read(spreadsheet=URL, ttl=0)

if df_raw.empty:
    st.error("スプレッドシートの読み込みに失敗しました。URLを確認してください。")
    st.stop()

# データクレンジング
df = df_raw.copy()
df["日付"] = pd.to_datetime(df["日付"])
df = df.dropna(subset=["日付"]).sort_values("日付")
df = df.drop_duplicates("日付", keep="last").reset_index(drop=True)

# --- 4. メイン画面：資産ダッシュボード ---
st.title("📈 Wealth Navigator PRO")

if not df.empty:
    L = df.iloc[-1]
    T = L["総資産"]
    now = datetime.now()
    
    # 収支計算 (Pandasの時系列演算を強化)
    try:
        # 今日の収支 (前日比)
        d_gain = T - df.iloc[-2]["総資産"] if len(df) > 1 else 0
        
        # 今月の収支 (当月初日のデータと比較)
        m_start_date = now.replace(day=1, hour=0, minute=0, second=0)
        m_data = df[df["日付"] >= m_start_date]
        m_gain = T - m_data.iloc[0]["総資産"] if not m_data.empty else 0
        
        # 先月の収支
        lm_end = m_start_date
        lm_start = (lm_end - pd.DateOffset(months=1))
        lm_df = df[(df["日付"] >= lm_start) & (df["日付"] < lm_end)]
        p_gain = lm_df.iloc[-1]["総資産"] - lm_df.iloc[0]["総資産"] if not lm_df.empty else 0
    except:
        d_gain, m_gain, p_gain =
