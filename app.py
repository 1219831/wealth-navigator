import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 設定 ---
GOAL_AMOUNT = 100000000  # 1億円
SPREADSHEET_URL = "https://docs.google.com/spreadsheets/d/1-Elv0TZJb6dVwHoGCx0fQinN2B1KYPOwWt0aWJEa_Is/edit"

st.set_page_config(page_title="Wealth Navigator", page_icon="🚀")

st.title("🚀 Wealth Navigator")

# Google Sheetsへの接続
conn = st.connection("gsheets", type=GSheetsConnection)

# 解析フラグの初期化（これを追加）
if 'analyzed' not in st.session_state:
    st.session_state.analyzed = False

# --- 最新データの読み込みと表示 ---
try:
    # ttl=0 で常に最新を取得
    df = conn.read(spreadsheet=SPREADSHEET_URL, ttl=0)
    if not df.empty:
        latest = df.iloc[-1]
        total = latest['総資産']
        
        # 前回のデータがあるか確認
        if len(df) > 1:
            diff = total - df.iloc[-2]['総資産']
        else:
            diff = 0
            
        col1, col2 = st.columns(2)
        col1.metric("現在の総資産", f"¥{int(total):,}", f"{int(diff):+,}")
        col2.metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")
    else:
        st.info("データがまだありません。最初のスクショをアップしてください。")
except Exception:
    st.info("データが読み込めません。スプレッドシートの1行目に「日付, 現物買付余力, 現物時価総額, 信用評価損益, 総資産, 1億円までの残り」と入力してください。")

# --- 画像アップロード ---
st.divider()
st.subheader("📸 資産状況を更新")
uploaded_files = st.file_uploader("松井証券のスクショをアップ（最大3枚）", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

# 解析実行ボタン
if st.button("AI解析を実行"):
    if uploaded_files:
        st.session_state.analyzed = True
    else:
        st.warning("ファイルを選択してください")

# 解析が終わっていたら入力フォームを表示（ここをボタンの外に出しました）
if st.session_state.analyzed:
    st.success("画像を認識しました。数値を確認してください。")
    with st.form("confirm_form"):
        cash = st.number_input("現物買付余力", value=195884)
        spot = st.number_input("現物時価総額", value=798250)
        margin = st.number_input("信用評価損益", value=272647)
        
        submitted = st.form_submit_button("この内容で記録する")
        
        if submitted:
            with st.spinner('スプレッドシートに書き込み中...'):
                new_total = cash + spot + margin
                new_data = pd.DataFrame([{
                    "日付": datetime.now().strftime('%Y/%m/%d'),
                    "現物買付余力": cash,
                    "現物時価総額": spot,
                    "信用評価損益": margin,
                    "総資産": new_total,
                    "1億円までの残り": GOAL_AMOUNT - new_total
                }])
                
                # スプレッドシートへ追記
                try:
                    # 既存のdfがある場合は合体、なければnew_dataのみ
                    if 'df' in locals() and not df.empty:
                        updated_df = pd.concat([df, new_data], ignore_index=True)
                    else:
                        updated_df = new_data
                    
                    # 書き込み実行
                    conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                    st.balloons()
                    # 成功したらフラグを戻す
                    st.session_state.analyzed = False
                    st.success("保存しました！")
                    st.rerun()
                except Exception as e:
                    st.error(f"書き込みに失敗しました。共有設定を確認してください: {e}")
