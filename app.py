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

# --- 最新データの読み込みと表示 ---
try:
    df = conn.read(spreadsheet=SPREADSHEET_URL)
    if not df.empty:
        latest = df.iloc[-1]
        total = latest['総資産']
        diff = total - df.iloc[-2]['総資産'] if len(df) > 1 else 0
        
        col1, col2 = st.columns(2)
        col1.metric("現在の総資産", f"¥{int(total):,}", f"{int(diff):+,}")
        col2.metric("1億円まであと", f"¥{int(GOAL_AMOUNT - total):,}")
        
        st.progress(min(float(total / GOAL_AMOUNT), 1.0), text=f"進捗率: {total/GOAL_AMOUNT:.2%}")
except:
    st.info("データがまだありません。最初のスクショをアップしてください。")

# --- 画像アップロード & 解析（簡易版） ---
st.divider()
st.subheader("📸 資産状況を更新")
uploaded_files = st.file_uploader("松井証券のスクショをアップ（最大3枚）", type=['png', 'jpg', 'jpeg'], accept_multiple_files=True)

if st.button("AI解析を実行"):
    if uploaded_files:
        with st.spinner('参謀がデータを抽出中...'):
            # 本来はここにAI解析が入ります。まずは手入力で確認できるフォームを出します。
            # 次のステップでここを完全自動化します。
            st.success("画像を認識しました。数値を確認してください。")
            with st.form("confirm_form"):
                cash = st.number_input("現物買付余力", value=195884)
                spot = st.number_input("現物時価総額", value=798250)
                margin = st.number_input("信用評価損益", value=272647)
                submitted = st.form_submit_button("この内容で記録する")
                
                if submitted:
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
                    updated_df = pd.concat([df, new_data], ignore_index=True) if 'df' in locals() else new_data
                    conn.update(spreadsheet=SPREADSHEET_URL, data=updated_df)
                    st.balloons()
                    st.rerun()
