import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime
import google.generativeai as genai
from PIL import Image
import json
import re

# --- 設定 ---
GOAL_AMOUNT = 100000000  # 1億円
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

# ワイドレイアウト設定
st.set_page_config(page_title="Wealth Navigator", page_icon="🚀", layout="wide")

# --- 準備1: Gemini APIの設定 ---
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception:
    st.error("Secretsに 'GEMINI_API_KEY' が設定されていません。")
    st.stop()

st.title("🚀 Wealth Navigator")

# --- 準備2: Google Sheetsへの接続 ---
conn = st.connection("gsheets", type=GSheetsConnection)

# 状態管理（Session State）の初期化
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# ==========================================================
# AI解析関数（数値のみ抽出）
# ==========================================================
def perform_ai_analysis(uploaded_files):
    prompt = """
    松井証券の資産状況スクショから数値を抽出してください。
    1. 現物買付余力（現金）
    2. 現物時価総額
    3. 信用評価損益（マイナスなら - を付ける）
    以下のJSON形式のみで出力してください。
    {"cash": 123, "spot": 456, "margin": -789}
    """
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except Exception:
        return None

# ==========================================================
# 処理1: 最新データの読み込みと「月別リセット収支」の表示
# ==========================================================
try:
    df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    
    if not df.empty:
        # 日付処理とソート
        df['日付'] = pd.to_datetime(df['日付'])
        df = df.sort_values(by='日付').reset_index(drop=True)
        
        latest = df.iloc[-1]
        total = latest['総資産']
        
        # ① 前日（前回）比：常に1つ前のレコードと比較
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        
        # ② 【重要】今月の収支：月が変わったら自動でリセット
        # 最新のデータと同じ「年」かつ「月」のデータを抽出
        latest_date = latest['日付']
        this_month_df = df[(df['日付'].dt.year == latest_date.year) & (df['日付'].dt.month == latest_date.month)]
        
        # 今月の最初のデータと比較する
        if not this_month_df.empty:
            month_start_total = this_month_df.iloc[0]['総資産']
            monthly_diff = total - month_start_total
        else:
            monthly_diff = 0
            
        # 今月の月名を取得（表示用）
        current_month_label = f"{latest_date.month}月の収支"
        
        # --- ダッシュボード表示 ---
        st.subheader("📊 資産状況ダッシュボード")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        
        with m_col1:
            st.metric("現在の総資産", f"¥{int(total):,}")
        with m_col2:
            st.metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        with m_col3:
            # 前回（前日）からの増減
            st.metric("前日比(前回比)", f"¥{int(daily_diff):,}", delta=f"{int(daily_diff):+,}")
        with m_col4:
            # カレンダー通りの「今月の収支」
            st.metric(current_month_label, f"¥{int(monthly_diff):,}", delta=f"{int(monthly_diff):+,}")
            
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")
        
        df['日付'] = df['日付'].dt.strftime('%Y/%m/%d')
    else:
        st.info("データがまだありません。")
except Exception:
    st.info("データの読み込み中、またはシートの初期設定が必要です。")

# ==========================================================
# 処理2: 資産更新（AI解析 & 日付自動付与 & 強制ソート）
# ==========================================================
st.divider()
st.subheader("📸 資産状況を更新（AI自動解析）")
uploaded_files = st.file_uploader("スクショをアップロード", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('Geminiが解析中...'):
            res = perform_ai_analysis(uploaded_files)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析完了！内容を確認してください。")
            else:
                st.error("解析に失敗しました。")
                st.session_state.analyzed = True
    else:
        st.warning("ファイルを選択してください")

if st.session_state.analyzed:
    with st.form("confirm_form"):
        cash = st.number_input("現物買付余力", value=int(st.session_state.ocr_data.get('cash', 0)))
        spot = st.number_input("現物時価総額", value=int(st.session_state.ocr_data.get('spot', 0)))
        margin = st.number_input("信用評価損益", value=int(st.session_state.ocr_data.get('margin', 0)))
        
        if st.form_submit_button("この内容で記録する"):
            with st.spinner('保存中...'):
                # 実行した日の日付を付与
                today_str = datetime.now().strftime('%Y/%m/%d')
                new_total = cash + spot + margin
                
                new_entry = pd.DataFrame([{
                    "日付": today_str,
                    "現物買付余力": cash,
                    "現物時価総額": spot,
                    "信用評価損益": margin,
                    "総資産": new_total,
                    "1億円までの残り": GOAL_AMOUNT - new_total
                }])
                
                try:
                    # 合体
                    if 'df' in locals() and not df.empty:
                        updated_df = pd.concat([df, new_entry], ignore_index=True)
                    else:
                        updated_df = new_entry
                    
                    # 【規律】日付型に直してソートし、重複や順序を整理
                    updated_df['日付'] = pd.to_datetime(updated_df['日付'])
                    updated_df = updated_df.sort_values(by='日付').reset_index(drop=True)
                    updated_df['日付'] = updated_df['日付'].dt.strftime('%Y/%m/%d')
                    
                    # 更新
                    conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                    
                    st.balloons()
                    st.session_state.analyzed = False
                    st.success(f"{today_str} のデータを保存しました。")
                    st.rerun()
                except Exception as e:
                    st.error(f"保存失敗: {e}")
