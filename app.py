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
    # 404対策：最も汎用的なモデル名を空白なしで指定
    model_name = "gemini-1.5-flash"
    model = genai.GenerativeModel(model_name)
except Exception as e:
    st.error(f"初期化エラー: {e}")
    st.stop()

conn = st.connection("gsheets", type=GSheetsConnection)

if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- 3. AI機能（OCR & 市場分析） ---
def perform_ai_analysis(up_file):
    p = '抽出：{"cash": 数値, "spot": 数値, "margin": 数値}'
    try:
        img = Image.open(up_file)
        res = model.generate_content([p, img])
        j_str = re.search(r'\{.*\}', res.text, re.DOTALL).group()
        return json.loads(j_str)
    except:
        return None

@st.cache_data(ttl=86400) # 1日キャッシュ
def get_market_briefing(today_str):
    # APIの拒否反応を避けるため「予定表の整理」を依頼
    p = f"今日は{today_str}。直近の国内決算、日米欧中の重要経済指標、🚨注目イベントを簡潔な箇条書きでまとめてください。投資助言は不要です。"
    try:
        response = model.generate_content(p)
        if response and hasattr(response, 'text'):
            return response.text
        return "🚨 情報の生成に失敗しました。時間をおいてリロードしてください。"
    except Exception as e:
        # エラー詳細を少し出しつつ、404時は別の案内を出す
        if "404" in str(e):
            return "💡 AIモデル接続中... (API設定を再確認しています)"
        return f"💡 マーケット情報は準備中です。 ({str(e)[:30]})"

# --- 4. データ読み込み ---
df_raw = pd.DataFrame()
try:
    df_raw = conn.read(spreadsheet=URL, ttl=0)
except:
    st.warning("スプレッドシートへの接続を確認中...")

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

    # --- 💎 AI投資ダイジェスト ---
    st.markdown("---")
    with st.expander("🗓️ 本日の投資イベント・ダイジェスト", expanded=True):
        today_key = datetime.now().strftime('%Y-%m-%d')
        st.write(get_market_briefing(today_key))

    # --- 📈 グラフセクション ---
    st.divider()
    vc, uc = st.columns([3, 1])
    with vc: st.write("### 🏔️ 資産成長トレンド")
    with uc: v_mode = st.radio("表示単位", ["日", "週", "月"], horizontal=True)

    if v_mode == "日":
        p_df = df[df['日付'] >= (ld - timedelta(days=7))].copy()
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%m/%d", None
    elif v_mode == "週":
        p_df = df.set_index('日付').resample('W').last().dropna().tail(12).reset_index()
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%m/%d", None
    else:
        df_m = df.copy()
        df_m['m'] = df_m['日付'].dt.to_period('M')
        p_df = df_m.groupby('m').tail(1).copy().tail(12).reset_index(drop=True)
        if len(p_df) < 2: p_df = df.copy()
        xf, dtk = "%y/%m", "M1"

    y_m = p_df['総資産'].max() * 1.15 if not p_df.empty else 1000000
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=p_df['日付'], y=p_df['総資産'], fill='tozeroy', 
        line=dict(color='#007BFF', width=4), fillcolor='rgba(0, 123, 255, 0.15)',
        mode='lines+markers' if v_mode == "日" else 'lines'
    ))
    fig.update_layout(
        template="plotly_dark", height=450, margin=dict(l=50, r=20, t=20, b=50),
        xaxis=dict(tickformat=xf, dtick=dtk, type='date'),
        yaxis=dict(range=[0, y_m], tickformat=",d"),
        hovermode="x unified"
    )
    st.plotly_chart(fig, use_container_width=True)

else:
    st.info("データがまだありません。最初のスクショをアップしてください。")

# --- 6. 更新フォーム ---
st.divider()
st.subheader("📸 資産状況を更新")
up_file = st.file_uploader("スクショを選択", type=['png', 'jpg', 'jpeg'])

if st.button("AI解析を実行"):
    if up_file:
        with st.spinner('Geminiが解析中...'):
            res = perform_ai_analysis(up_file)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析成功！")

if st.session_state.analyzed:
    with st.form("edit_form"):
        c1, c2, c3 = st.columns(3)
        ocr = st.session_state.ocr_data
        n_c = c1.number_input("現物取得余力", value=int(ocr.get('cash', 0)))
        n_s = c2.number_input("現物資産時価総額", value=int(ocr.get('spot', 0)))
        n_m = c3.number_input("信用保有資産損益", value=int(ocr.get('margin', 0)))
        
        if st.form_submit_button("記録する"):
            td_str = datetime.now().strftime('%Y/%m/%d')
            t_v = n_c + n_s + n_m
            ent = pd.DataFrame([{
                "日付": td_str, "現物買付余力": n_c, "現物時価総額": n_s,
                "信用評価損益": n_m, "総資産": t_v, "1億円までの残り": GOAL - t_v
            }])
            try:
                out = pd.concat([df_raw, ent], ignore_index=True) if not df_raw.empty else ent
                out['日付'] = pd.to_datetime(out['日付'])
                out = out.sort_values('日付').drop_duplicates('日付', keep='last')
                out['日付'] = out['日付'].dt.strftime('%Y/%m/%d')
                conn.update(spreadsheet=URL, data=out)
                st.balloons()
                st.session_state.analyzed = False
                st.rerun()
            except Exception as e:
                st.error(f"保存失敗: {e}")
