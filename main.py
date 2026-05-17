import streamlit as st
import google.generativeai as genai
from PIL import Image
import io, json, time, re, datetime, os

# 他のファイルから部品を読み込む
from config import set_page_config, SUBJECT_PROMPTS
from utils import load_history, save_history, speak_js, get_clean_speech_text

# ページ設定の実行
set_page_config()

# --- セッション初期化 ---
if "agreed" not in st.session_state: st.session_state.agreed = False
if "setup_completed" not in st.session_state: st.session_state.setup_completed = False
if "history" not in st.session_state: st.session_state.history = {}
if "final_json" not in st.session_state: st.session_state.final_json = None
if "font_size" not in st.session_state: st.session_state.font_size = 18
if "user_api_key" not in st.session_state: st.session_state.user_api_key = ""
if "voice_speed" not in st.session_state: st.session_state.voice_speed = 1.0
if "show_voice_btns" not in st.session_state: st.session_state.show_voice_btns = False

# CSS適用（表の文字サイズや余白もきれいに整える設定を追加しています）
st.markdown(f"""
<style>
.content-body {{ font-size: {st.session_state.font_size}px !important; line-height: 1.6; }}
.content-body table {{ font-size: {st.session_state.font_size}px !important; width: 100%; border-collapse: collapse; }}
.content-body th, .content-body td {{ border: 1px solid #ccc; padding: 8px; text-align: left; }}
</style>
""", unsafe_allow_html=True)

# --- 1. 同意画面 ---
if not st.session_state.agreed:
    st.title("🚀 教科書ブースター V1.3")
    with st.container(border=True):
        st.markdown("### 【本ソフトウェア利用に関する同意事項】\n**第1条（著作権の遵守）**\n利用者は、本アプリで取り扱う著作物が著作権法により保護されていることを認識し、解析結果等を第三者に公開してはならないものとします。\n\n**第2条（AI生成物の免責）**\nAIによる推論に基づくものであり、その正確性、完全性を保証するものではありません。\n\n**第3条（利用目的）**\n私的な学習補助を目的として提供されるものです。")
        if st.checkbox("上記の内容に同意します。"):
            st.session_state.agreed = True
            st.rerun()
    st.stop()

# --- 2. 初期セットアップ ---
if not st.session_state.setup_completed:
    st.subheader("⚙️ 初期セットアップ")
    with st.form("setup_form"):
        user_key = st.text_input("Gemini API Key", type="password", value=st.session_state.user_api_key)
        c1, c2 = st.columns(2)
        school_type = c1.selectbox("学校区分", ["小学生", "中学生", "高校生"])
        grade = c1.selectbox("学年", [f"{i}年生" for i in range(1, 7)])
        quiz_count = c2.selectbox("問題数", [10, 15, 20, 25])
        
        if st.form_submit_button("🚀 学習を開始"):
            st.session_state.user_api_key = user_key
            st.session_state.school_type = school_type
            st.session_state.grade = grade
            st.session_state.quiz_count = quiz_count
            
            st.session_state.history = load_history()
            st.session_state.setup_completed = True
            st.rerun()
    st.stop()

# --- サイドバー設定 ---
st.sidebar.header("🛠️ 調整")
st.session_state.font_size = st.sidebar.slider("🔍 文字サイズ", 14, 45, st.session_state.font_size)
st.session_state.voice_speed = st.sidebar.slider("🐌 音声速度", 0.5, 2.0, st.session_state.voice_speed, 0.1)
st.session_state.user_api_key = st.sidebar.text_input("API Key 更新", value=st.session_state.user_api_key, type="password")

# --- 3. メインタブ管理 ---
tab_study, tab_history, tab_config = st.tabs(["📖 学習", "📈 履歴", "⚙️ 設定変更"])

with tab_history:
    st.write(f"📂 {st.session_state.school_type} {st.session_state.grade} の履歴")
    for sub, logs in st.session_state.history.items():
        with st.expander(f"📙 {sub} ({len(logs)}件)"):
            for idx, log in enumerate(reversed(logs)):
                c1, c2, c3 = st.columns([2, 1, 1])
                c1.write(f"📅 {log['date']} (P.{log.get('page','--')})")
                c2.write(f"🎯 {log['score']}")
                if c3.button("解き直す", key=f"hist_{sub}_{idx}"):
                    st.session_state.final_json = {"explanation_blocks": [{"text": "### 🕒 復習モード"}], "quizzes": log["quizzes"], "used_subject": sub}
                    st.rerun()

with tab_study:
    c_s1, c_s2 = st.columns(2)
    subject_choice = c_s1.selectbox("🎯 教科", list(SUBJECT_PROMPTS.keys()))
    style_choice = c_s2.selectbox("🎨 解説スタイル", ["定型", "対話形式", "ニュース風"])
    cam_file = st.file_uploader("📸 教科書をスキャン", type=['png', 'jpg', 'jpeg'])

    if cam_file and st.button("✨ ブースト開始", use_container_width=True):
        genai.configure(api_key=st.session_state.user_api_key)
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        with st.status("教科書を全文解析中..."):
            count = st.session_state.quiz_count
            full_prompt = f"""あなたは{st.session_state.school_type}{st.session_state.grade}担当。
【最優先指令】クイズを必ず【例外なく{count}問】作成せよ。
【ミッション: {subject_choice}】{SUBJECT_PROMPTS[subject_choice]}
【絶対ルール】
1. 要約禁止。画像内の全文章を一言一句100%網羅せよ。
2. ブロック（explanation_blocks）は最大5行とし、意味のまとまりで分割せよ。
3. ページ番号 [P.xx] は必ず各ブロックの先頭に記述し、直後で改行せよ。
###JSONフォーマット###
{{ "detected_subject": "{subject_choice}", "page": "数字", "explanation_blocks": [{{"text": "[P.〇]\\n(本文)" }}], "english_only_script": "英文", "boost_comments": {{ "high": {{"text":"正解","script":"正解"}}, "mid": {{"text":"中","script":"中"}}, "low": {{"text":"低","script":"低"}} }}, "quizzes": [{{ "question":"..", "options":[".."], "answer":0 }}] }}"""
            img = Image.open(cam_file)
            res_raw = model.generate_content([full_prompt, img])
            match = re.search(r"(\{.*\})", res_raw.text, re.DOTALL)
            if match:
                st.session_state.final_json = json.loads(match.group(1))
                st.session_state.final_json["used_subject"] = subject_choice

    if st.session_state.final_json:
        res = st.session_state.final_json
        used_sub = res.get("used_subject", subject_choice)
        
        v_cols = st.columns(4)
        if v_cols[0].button("🔊 全文"):
            full_text = " ".join([b["text"] for b in res["explanation_blocks"]])
            speak_js(get_clean_speech_text(full_text), st.session_state.voice_speed)
        if used_sub == "英語" and v_cols[1].button("🔊 英語のみ"):
            speak_js(res.get("english_only_script"), st.session_state.voice_speed, "en-US")
        if v_cols[2].button("🛑 停止"): 
            speak_js("")
        if v_cols[3].button("🔊 個別"):
            st.session_state.show_voice_btns = not st.session_state.show_voice_btns
            st.rerun()

        # 解説ブロックの表示と個別再生
        for i, block in enumerate(res["explanation_blocks"]):
            with st.container(border=True):
                # 英語（スラッシュリーディングの表）を綺麗にMarkdownとして解釈させて表示する修正
                # <div>で囲むと表が壊れるため、英語の場合はst.markdownを直接、他はHTMLを適用します
                if used_sub == "英語":
                    st.markdown(block["text"])
                else:
                    st.markdown(f'<div class="content-body">{block["text"]}</div>', unsafe_allow_html=True)
                
                if st.session_state.show_voice_btns:
                    if st.button(f"▶ 再生", key=f"v_{i}"):
                        lang = "en-US" if used_sub == "英語" and not any(c in block["text"] for c in "あいうえお") else "ja-JP"
                        speak_js(get_clean_speech_text(block["text"]), st.session_state.voice_speed, lang)

        # 確認クイズコーナー
        with st.expander("📝 確認クイズ", expanded=True):
            score = 0
            all_answered = True
            q_list = res.get("quizzes", [])
            for i, q in enumerate(q_list):
                ans = st.radio(f"問{i+1}: {q['question']}", q['options'], key=f"q_{i}", index=None)
                if ans:
                    if q['options'].index(ans) == q['answer']:
                        st.success("⭕ 正解")
                        score += 1
                    else: 
                        st.error(f"❌ 正解: {q['options'][q['answer']]}")
                else: 
                    all_answered = False
            
            if all_answered and st.button("✨ 履歴に保存", use_container_width=True):
                rate = (score / len(q_list)) * 100
                st.metric("正解率", f"{rate:.0f}%")
                rank = "high" if rate == 100 else "mid" if rate >= 50 else "low"
                speak_js(res["boost_comments"][rank]["script"], st.session_state.voice_speed)
                subj = res.get("used_subject", "不明")
                if subj not in st.session_state.history: 
                    st.session_state.history[subj] = []
                st.session_state.history[subj].append({
                    "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M"), 
                    "page": res.get("page","--"), 
                    "score": f"{rate:.0f}%", 
                    "quizzes": q_list
                })
                save_history(st.session_state.history)
                st.toast("保存完了")
