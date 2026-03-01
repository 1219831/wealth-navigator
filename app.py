import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta
import google.generativeai as genai
from PIL import Image
import json
import re
import plotly.graph_objects as go

# --- 1. 基本設定 ---
GOAL = 100000000 
URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator PRO", page_icon="📈", layout="wide")

# --- 2. 外部連携設定 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("APIキーの設定を確認してください。")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能（OCR & 投資ダイジェスト） ---
def perform_ai_analysis(up_file):
    p = '松井証券の数値抽出。{"cash": 100, "spot": 200, "margin": -50} の形式。'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except Exception:
        return None

@st.cache_data(ttl=86400) # 1日キャッシュ
def get_investment_briefing(date_key):
    # AIが拒否反応を示さないよう、客観的な予定表の作成を依頼
    prompt = f"""
    今日は {date_key} です。マーケットカレンダーを作成してください。
    
    1. 国内決算：本日または週明けの主な決算発表企業（3〜5社）と、総件数を教えてください。
    2. 重要経済指標：日本、アメリカ、欧州、中国の順で、直近の重要指標（PMI、雇用、インフレ率、金利決定など）を挙げてください。
    3. 🚨最注目イベント：市場への影響が特に大きいものを太字で強調してください。
    
    注意：投資助言ではなく、公開情報の要約として出力してください。
    """
    try:
        response = model.generate_content(prompt)
        # 生成されたコンテンツが空、またはブロックされた場合のチェック
        if response and response.text:
            return response.text
        else:
            return "🚨 本日の重要イベント：経済カレンダーを確認してください。（AIフィルターにより詳細制限中）"
    except Exception as e:
        return f"💡 マーケット情報は準備中です。 (詳細: {str(e)[:50]}...)"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except Exception:
    st.warning("シート接続待ち...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld = latest['日付']
    total = latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    lm_target = ld.replace(day=1) - timedelta(days=1)
    lm_df = df[df['日付'].dt.to_period('M') == lm_target.to_period('M')]
    lm_diff = lm_df.iloc[-1]['総資産'] - lm_df.iloc[0]['総資産'] if not lm_df.empty else 0

    # ダッシュボード
    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    
    cols[1].metric("1億円まであと", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{lm_target.month}月の収支", f"¥{int(lm_diff):,}", delta=f"{int(lm_diff):+,}")
    cols[4].metric(f"{ld.month}月の収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
    
    prg = max(0.0, min(float(total / GOAL), 1.0))
    st.progress(prg, text=f"目標達成率: {prg:.2%}")

    # --- 💎 AI投資イベントダイジェスト ---
    st.markdown("---
