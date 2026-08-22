import json
import os
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="近大和歌山 入試対策AIアプリ", layout="wide")

# 1. 復習データの保存用ファイル設定（アプリと同じフォルダに自動作成）
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MISSED_FILE = os.path.join(BASE_DIR, "missed_questions.json")

def load_missed_questions():
    if os.path.exists(MISSED_FILE):
        try:
            with open(MISSED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return []
    return []

def save_missed_questions(data):
    with open(MISSED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# 2. セッション状態の初期化
if "missed_questions" not in st.session_state:
    st.session_state.missed_questions = load_missed_questions()
if "current_q" not in st.session_state:
    st.session_state.current_q = None
if "user_answered" not in st.session_state:
    st.session_state.user_answered = False

# 3. APIキーとモデルの設定
st.sidebar.header("🔑 API設定")
api_key_input = st.sidebar.text_input(
    "Gemini API Key", 
    type="password", 
    help="Google AI Studioで取得したAPIキーを入力してください"
)
api_key = api_key_input or os.environ.get("GEMINI_API_KEY")

selected_model = st.sidebar.selectbox(
    "使用AIモデル",
    ["gemini-3.6-flash", "gemini-2.5-flash"],
    index=0
)

# 4. AIによる問題生成関数
def generate_full_question_from_gemini(client, subject, hensachi, model_name):
    target_subject = subject if subject != "すべて" else "英語"
    
    prompt = f"""
あなたは和歌山県の難関私立「近畿大学附属和歌山高等学校」の入試問題に精通したプロ家庭教師です。
中学3年生向けに、近大和歌山高校の過去問傾向を踏まえた4択問題と、その解説セットを1問作成してください。

【対象教科】{target_subject}
【目標偏差値】{hensachi}

以下のJSONフォーマットのみで出力してください（他の文章は一切含めないでください）：
{{
  "subject": "{target_subject}",
  "hensachi": {hensachi},
  "question": "問題文",
  "options": [
    "1. 選択肢1",
    "2. 選択肢2",
    "3. 選択肢3",
    "4. 選択肢4"
  ],
  "answer_idx": 正解のインデックス(0〜3の整数),
  "explanation": "なぜそれが正解なのかの詳しい解説",
  "trap_explanation": "受験生が選びがちな誤答パターンや引っかかりやすい罠の解説",
  "tip": "近大和歌山合格のための覚え方のコツ"
}}
"""
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json"
        )
    )
    return json.loads(response.text)

# 5. メイン画面
st.title("🎓 近大和歌山高校 入試対策アプリ")

st.sidebar.header("🎯 出題条件設定")
user_hensachi = st.sidebar.slider("現在の目標・偏差値", 50, 70, 60, step=5)
selected_subject = st.sidebar.selectbox("教科選択", ["英語", "理科", "社会"])

tab_quiz, tab_review = st.tabs(["📝 AI新規問題演習", f"📚 復習リスト ({len(st.session_state.missed_questions)}問)"])

# --- AI新規問題演習モード ---
with tab_quiz:
    if not api_key:
        st.warning("👈 サイドバーに Gemini API キーを入力してください。")
    else:
        client = genai.Client(api_key=api_key)

        if st.session_state.current_q is None:
            with st.spinner("🤖 Geminiが近大和歌山の過去問傾向から問題を作成中..."):
                try:
                    st.session_state.current_q = generate_full_question_from_gemini(
                        client, selected_subject, user_hensachi, selected_model
                    )
                    st.session_state.user_answered = False
                except Exception as e:
                    st.error(f"問題生成エラー: {e}")

        q = st.session_state.current_q

        if q:
            st.markdown(f"### 【{q['subject']}】 目標偏差値レベル: {q['hensachi']}")
            st.info(q["question"])

            user_choice = st.radio("回答を選択してください:", q["options"], key=f"q_radio_{q['question'][:10]}")

            col1, col2 = st.columns([1, 3])
            with col1:
                submit_btn = st.button("回答を送信")
            with col2:
                next_btn = st.button("次の問題をAIに作らせる")

            if submit_btn:
                st.session_state.user_answered = True
                chosen_idx = q["options"].index(user_choice)
                is_correct = (chosen_idx == q["answer_idx"])

                if not is_correct:
                    existing_qs = [m["q"]["question"] for m in st.session_state.missed_questions]
                    if q["question"] not in existing_qs:
                        st.session_state.missed_questions.append({
                            "q": q,
                            "user_choice": user_choice
                        })
                        save_missed_questions(st.session_state.missed_questions)

            if st.session_state.user_answered:
                chosen_idx = q["options"].index(user_choice)
                is_correct = (chosen_idx == q["answer_idx"])

                st.markdown("---")
                if is_correct:
                    st.success("⭕ **正解です！よくできました！**")
                else:
                    st.error(f"❌ **不正解です...（正解: {q['options'][q['answer_idx']]})**")

                st.markdown(f"#### 📖 詳しい解説\n{q['explanation']}")
                st.markdown(f"#### ⚠️ 間違いやすいポイント・罠\n{q['trap_explanation']}")
                st.info(f"💡 **覚え方のコツ:** {q['tip']}")

            if next_btn:
                st.session_state.current_q = None
                st.session_state.user_answered = False
                st.rerun()

# --- 復習モード ---
with tab_review:
    st.subheader("📚 復習が必要な問題")
    
    if not st.session_state.missed_questions:
        st.success("現在、復習が必要な問題はありません！素晴らしい集中力です！")
    else:
        st.write("間違えた問題をもう一度解き直してみましょう！正解したらリストから消去できます。")
        
        to_remove_idx = None

        for idx, item in enumerate(st.session_state.missed_questions):
            mq = item["q"]
            
            with st.expander(f"【第{idx+1}問】 {mq['subject']} (難易度:{mq['hensachi']}) - {mq['question'][:25]}..."):
                st.markdown(f"**問題:** {mq['question']}")
                
                review_choice = st.radio(
                    "もう一度挑戦してみよう:", 
                    mq["options"], 
                    key=f"review_q_{idx}"
                )
                
                col_r1, col_r2 = st.columns([1, 2])
                with col_r1:
                    check_r_btn = st.button("回答をチェック", key=f"btn_check_{idx}")
                with col_r2:
                    clear_btn = st.button("克服した（リストから消去）", key=f"btn_clear_{idx}")

                if check_r_btn:
                    chosen_idx = mq["options"].index(review_choice)
                    if chosen_idx == mq["answer_idx"]:
                        st.success("⭕ 正解！完璧です！「克服した」ボタンを押してリストから消去しましょう。")
                    else:
                        st.error(f"❌ まだおしい！正解は: {mq['options'][mq['answer_idx']]}")
                    
                    st.markdown(f"**【解説】**\n{mq['explanation']}")
                    st.info(f"**覚え方のコツ:** {mq['tip']}")

                if clear_btn:
                    to_remove_idx = idx

        if to_remove_idx is not None:
            st.session_state.missed_questions.pop(to_remove_idx)
            save_missed_questions(st.session_state.missed_questions)
            st.success("復習リストから問題を消去しました！")
            st.rerun()
