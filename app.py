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

# --- 2. 外部連携 (404エラー対策：正式なモデルパス) ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    # 2026年仕様の安定モデルパス
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except Exception as e:
    st.error(f"API接続エラー: {e}")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能（OCR解析 & 市場ダイジェスト） ---
def perform_ai_analysis(up_file):
    p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except: return None

@st.cache_data(ttl=3600)
def get_market_briefing(date_str):
    # ボスのご要望（決算・指標・重要度）を反映した最強のプロンプト
    prompt = f"""
    今日は {date_str} です。投資家向けの「本日のイベント」を作成してください。
    
    ■国内決算発表：
    本日または週明けの注目銘柄を数社ピックアップし、名称と総件数を表示。
    
    ■重要経済指標：
    日・米・欧州・中国のマーケティングに関わる重要指数を網羅。
    
    ■特記事項：
    🚨 特に重要度の高いイベントは、太字や警告絵文字で注意を引くように。
    
    ※投資助言ではなく、客観的なスケジュール情報のまとめとして出力してください。
    """
    try:
        response = model.generate_content(prompt)
        return response.text if response.text else "情報の取得を制限中"
    except Exception as e:
        return f"💡 マーケット情報は準備中です。 (API Wait: {str(e)[:20]})"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシート接続待ち...")

# --- 5. メイン表示 ---
st.title("🚀 Wealth Navigator PRO")

if not df_raw.empty:
    df_raw['日付'] = pd.to_datetime(df_raw['日付']).dt.normalize()
    df = df_raw.sort_values('日付').drop_duplicates('日付', keep='last').reset_index(drop=True)
    
    latest = df.iloc[-1]
    ld, total = latest['日付'], latest['総資産']
    
    # 指標計算
    d_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
    tm_df = df[df['日付'].dt.to_period('M') == ld.to_period('M')]
    tm_diff = total - tm_df.iloc[0]['総資産'] if not tm_df.empty else 0
    
    lm_target = ld.replace(day=1) - timedelta(days=1)
    lm_df = df[df['日付'].dt.to_period('M') == lm_target.to_period('M')]
    lm_diff = lm_df.iloc[-1]['総資産'] - lm_df.iloc[0]['総資産'] if not lm_df.empty else 0

    # 1. ダッシュボード
    st.subheader("📊 資産状況ダッシュボード")
    cols = st.columns([1.2, 1, 1, 1, 1])
    with cols[0]:
        st.metric("現在の総資産", f"¥{int(total):,}")
        st.caption(f"┣ 現物資産時価総額: ¥{int(latest['現物時価総額']):,}")
        st.caption(f"┣ 信用保有資産損益: ¥{int(latest['信用評価損益']):+,}")
        st.caption(f"┗ 現物取得余力: ¥{int(latest['現物買付余力']):,}")
    cols[1].metric("1億円まで", f"¥{int(GOAL - total):,}")
    cols[2].metric("前日比", f"¥{int(d_diff):,}", delta=f"{int(d_diff):+,}")
    cols[3].metric(f"{lm_target.month}月収支", f"¥{int(lm_diff):,}", delta=f"{int(lm_diff):+,}")
    cols[4].metric(f"{ld.month}月収支", f"¥{int(tm_diff):,}", delta=f"{int(tm_diff):+,}")
    
    prg = max(0.0, min(float(total / GOAL), 1.0))
    st.progress(prg, text=f"目標達成率: {prg:.2%}")

    # 2. 【新機能】本日のイベント (目標達成率のすぐ下に配置)
    st.markdown("---")
    with st.container():
        today_key = datetime.now().strftime('%Y年%m月%d日')
        st.markdown(get_market_briefing(today_key))

    # 3. グラフセクション
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc: st.write("### 🏔️ 資産成長トレンド")
    with uc: v_mode = st.radio("単位", ["日", "週", "月"], horizontal=True)

    if v_mode == "日":
        # 修正箇所：一行を短く分割してエラーを回避
        mask = df['日付'] >= (ld - timedelta(days=7))
        p_df = df[mask].copy()
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%m/%d", None
    elif v_mode == "週":
        p_df = df.set_index('日付').resample('W').last()
        p_df = p_df.dropna().tail(12).reset_index()
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%m/%d", None
    else:
        df_m = df.copy()
        df_m['m'] = df_m['日付'].dt.to_period('M')
        p_df = df_m.groupby('m').tail(1).copy().tail(12)
        p_df = p_df.reset_index(drop=True)
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%y/%m", "M1"

    ymax = p_df['総資産'].max() * 1.15 if not p_df
