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

st.set_page_config(page_title="Wealth Navigator", page_icon="🚀", layout="wide")

# Gemini APIの設定
try:
    genai.configure(api_key=st.secrets["GEMINI_API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except:
    st.error("Secretsに GEMINI_API_KEY が設定されていません。")
    st.stop()

st.title("🚀 Wealth Navigator")

# Google Sheetsへの接続
conn = st.connection("gsheets", type=GSheetsConnection)

# 状態管理（Session State）の初期化
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False
if 'ocr_data' not in st.session_state:
    st.session_state.ocr_data = {"cash": 0, "spot": 0, "margin": 0}

# --- AI解析関数（OCR） ---
def perform_ai_analysis(uploaded_files):
prompt = """
    松井証券の資産状況スクショから数値を抽出してください。
    1. 日付（画像内にあればその日付、なければ2026/01/01形式で推測）
    2. 現物買付余力
    3. 現物時価総額
    4. 信用評価損益（マイナスなら - を付ける）
    以下のJSON形式のみで出力してください。
    {"date": "2026/03/01", "cash": 123, "spot": 456, "margin": -789}
    """
    try:
        img = Image.open(uploaded_files[0])
        response = model.generate_content([prompt, img])
        # JSON部分を抽出
        json_str = re.search(r'\{.*\}', response.text, re.DOTALL).group()
        return json.loads(json_str)
    except:
        return None

# --- 最新データの読み込みと表示 ---
try:
    df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    if not df.empty:
        # 日付処理と並べ替え
        df['日付'] = pd.to_datetime(df['日付'])
        df = df.sort_values(by='日付').reset_index(drop=True)
        
        latest = df.iloc[-1]
        total = latest['総資産']
        
        # ① 前日（前回）比
        daily_diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        
        # ② 当月比
        now = datetime.now()
        month_df = df[(df['日付'].dt.year == now.year) & (df['日付'].dt.month == now.month)]
        monthly_diff = total - month_df.iloc[0]['総資産'] if not month_df.empty else 0
        
        # --- ダッシュボード表示 ---
        st.subheader("📊 資産状況ダッシュボード")
        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
        m_col1.metric("現在の総資産", f"¥{int(total):,}")
        m_col2.metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        m_col3.metric("前日比(前回比)", f"¥{int(daily_diff):,}", f"{int(daily_diff):+,}")
        m_col4.metric("今月の収支", f"¥{int(monthly_diff):,}", f"{int(monthly_diff):+,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")
    else:
        st.info("データがまだありません。")
except Exception as e:
    st.info("データの読み込み中、またはシートが空です。")

# --- 資産更新エリア ---
st.divider()
st.subheader("📸 資産状況を更新（AI自動解析）")
uploaded_files = st.file_uploader("スクショをアップ", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('Geminiが解析中...'):
            res = perform_ai_analysis(uploaded_files)
            if res:
                st.session_state.ocr_data = res
                st.session_state.analyzed = True
                st.success("解析完了！内容を確認してください。")
            else:
                st.error("解析に失敗しました。手入力してください。")
                st.session_state.analyzed = True
    else:
        st.warning("ファイルを選択してください")

# 入力フォーム
if st.session_state.analyzed:
    with st.form("confirm_form"):
        cash = st.number_input("現物買付余力", value=int(st.session_state.ocr_data.get('cash', 0)))
        spot = st.number_input("現物時価総額", value=int(st.session_state.ocr_data.get('spot', 0)))
        margin = st.number_input("信用評価損益", value=int(st.session_state.ocr_data.get('margin', 0)))
        
if st.form_submit_button("この内容で記録する"):
            new_total = cash + spot + margin
            new_entry = pd.DataFrame([{
                "日付": datetime.now().strftime('%Y/%m/%d'), # ※ここを後でAI読取に変更可能
                "現物買付余力": cash,
                "現物時価総額": spot,
                "信用評価損益": margin,
                "総資産": new_total,
                "1億円までの残り": GOAL_AMOUNT - new_total
            }])
            
            try:
                # 1. 既存データと結合
                if 'df' in locals() and not df.empty:
                    updated_df = pd.concat([df, new_entry], ignore_index=True)
                else:
                    updated_df = new_entry
                
                # --- ★ここに追加！「規律」を守るソート処理 ---
                updated_df['日付'] = pd.to_datetime(updated_df['日付'])
                updated_df = updated_df.sort_values(by='日付').reset_index(drop=True)
                # ------------------------------------------
                
                # 2. 書き込み実行
                conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                
                st.balloons()
                st.session_state.analyzed = False
                st.success("スプレッドシートを日付順に整理して保存しました！")
                st.rerun()
            except Exception as e:
                st.error(f"保存失敗: {e}")
