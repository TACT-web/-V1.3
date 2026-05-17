import streamlit as st
import google.generativeai as genai
from PIL import Image
import io, json, time, re, datetime, os

# 他のファイルから部品を読み込む
from config import set_page_config, SUBJECT_PROMPTS
from utils import (
    load_history, save_history, speak_js, get_clean_speech_text,
    load_app_config, save_app_config, get_jst_now_str
)

# ページ設定の実行
set_page_config()

# --- アプリ起動時：永続保存された初期セットアップデータの自動読込 (①対策) ---
if "app_config_loaded" not in st.session_state:
    saved_cfg = load_app_config()
    if saved_cfg:
        st.session_state.user_api_key = saved_cfg.get("user_api_key", "")
        st.session_state.school_type = saved_cfg.get("school_type", "中学生")
        st.session_state.grade = saved_cfg.get("grade", "1年生")
        st.session_state.quiz_count = saved_cfg.get("quiz_count", 10)
        st.session_state.setup_completed = True
        st.session_state.history = load_history()
    st.session_state.app_config_loaded = True

# --- セッション初期化 ---
if "agreed" not in st.session_state: st.session_state.agreed = False
if "setup_completed" not in st.session_state: st.session_state.setup_completed = False
if "history" not in st.session_state: st.session_state.history = {}
if "final_json" not in st.session_state: st.session_state.final_json = None
if "font_size" not in st.session_state: st.session_state.font_size = 18
if "user_api_key" not in st.session_state: st.session_state.user_api_key = ""
if "voice_speed" not in st.session_state: st.session_state.voice_speed = 1.0
if "show_voice_btns" not in st.session_state: st.session_state.show_voice_btns = False
if "review_mode" not in st.session_state: st.session_state.review_mode = False

# CSS適用（表形式対応）
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
        school_type = c1.selectbox("学校区分", ["小学生", "中学生", "高校生"], index=1)
        grade = c1.selectbox("学年", [f"{i}年生" for i in range(1, 7)], index=0)
        quiz_count = c2.selectbox("問題数", [10, 15, 20, 25], index=0)
        
        if st.form_submit_button("🚀 設定を保存して学習を開始"):
            st.session_state.user_api_key = user_key
            st.session_state.school_type = school_type
            st.session_state.grade = grade
            st.session_state.quiz_count = quiz_count
            
            # ローカルJSONに初期値を保存 (①固定化)
            save_app_config({
                "user_api_key": user_key, "school_type": school_type, "grade": grade, "quiz_count": quiz_count
            })
            st.session_state.history = load_history()
            st.session_state.setup_completed = True
            st.rerun()
    st.stop()

# --- サイドバー設定 ---
st.sidebar.header("🛠️ 調整")
st.session_state.font_size = st.sidebar.slider("🔍 文字サイズ", 14, 45, st.session_state.font_size)
st.session_state.voice_speed = st.sidebar.slider("🐌 音声速度", 0.5, 2.0, st.session_state.voice_speed, 0.1)

# --- 3. メインタブ管理 ---
tab_study, tab_history, tab_config = st.tabs(["📖 学習", "📈 履歴", "⚙️ 設定変更"])

# ⑤ 履歴の一覧化・見やすさ大幅改善
with tab_history:
    st.markdown(f"### 📂 {st.session_state.school_type} {st.session_state.grade} の学習履歴一覧")
    
    all_logs = []
    for sub, logs in st.session_state.history.items():
        for idx, log in enumerate(logs):
            all_logs.append({
                "subject": sub,
                "date": log.get("date", "不明"),
                "page": log.get("page", "--"),
                "score": log.get("score", "0%"),
                "orig_idx": idx
            })
            
    if not all_logs:
        st.info("履歴がまだありません。")
    else:
        # 日時で並び替え（最新が上）
        all_logs_sorted = sorted(all_logs, key=lambda x: x["date"], reverse=True)
        
        with st.container(height=350, border=True):
            for item in all_logs_sorted:
                with st.expander(f"【{item['subject']}】 p.{item['page']} - 正解率: {item['score']} ({item['date']})"):
                    orig_log = st.session_state.history[item['subject']][item['orig_idx']]
                    st.write(f"📝 収録問題数: {len(orig_log.get('quizzes', []))}問")
                    
                    # ④ 解き直しのキー競合バグを完全修正
                    if st.button("🔁 このクイズを解き直す", key=f"rev_btn_{item['subject']}_{item['orig_idx']}"):
                        st.session_state.final_json = {
                            "explanation_blocks": [{"text": f"### 🕒 復習モード（{item['subject']} p.{item['page']}）"}],
                            "quizzes": orig_log["quizzes"],
                            "used_subject": item['subject'],
                            "page": item['page']
                        }
                        st.session_state.review_mode = True
                        st.toast("学習タブにクイズを読み込みました！")

# ② 設定変更タブの配置
with tab_config:
    st.markdown("### ⚙️ アプリ環境設定の変更")
    with st.form("edit_config_form"):
        new_key = st.text_input("Gemini API Key 更新", value=st.session_state.user_api_key, type="password")
        c1, c2 = st.columns(2)
        new_school = c1.selectbox("学校区分", ["小学生", "中学生", "高校生"], index=["小学生", "中学生", "高校生"].index(st.session_state.school_type))
        new_grade = c1.selectbox("学年", [f"{i}年生" for i in range(1, 7)], index=[f"{i}年生" for i in range(1, 7)].index(st.session_state.grade))
        new_count = c2.selectbox("標準問題数", [10, 15, 20, 25], index=[10, 15, 20, 25].index(st.session_state.quiz_count))
        
        if st.form_submit_button("💾 設定を上書き保存"):
            st.session_state.user_api_key = new_key
            st.session_state.school_type = new_school
            st.session_state.grade = new_grade
            st.session_state.quiz_count = new_count
            
            save_app_config({
                "user_api_key": new_key, "school_type": new_school, "grade": new_grade, "quiz_count": new_count
            })
            st.session_state.history = load_history()
            st.success("設定を更新しました！")
            st.rerun()

with tab_study:
    if st.session_state.get("review_mode", False):
        st.warning("⚠️ 現在「履歴からの解き直し（復習モード）」を実行中です。")
        if st.button("❌ 復習モードを終了して通常スキャンに戻る"):
            st.session_state.final_json = None
            st.session_state.review_mode = False
            st.rerun()

    c_s1, c_s2 = st.columns(2)
    subject_choice = c_s1.selectbox("🎯 教科", list(SUBJECT_PROMPTS.keys()))
    style_choice = c_s2.selectbox("🎨 解説スタイル", ["定型", "対話形式", "ニュース風"])
    cam_file = st.file_uploader("📸 教科書をスキャン", type=['png', 'jpg', 'jpeg'])

    if cam_file and st.button("✨ ブースト開始", use_container_width=True):
        st.session_state.review_mode = False
        genai.configure(api_key=st.session_state.user_api_key)
        model = genai.GenerativeModel('gemini-3-flash-preview') 
        with st.status("教科書を全文解析中..."):
            count = st.session_state.quiz_count
            # ⑦ 解説スタイル(style_choice)の命令をプロンプトへ完全注入
            full_prompt = f"""あなたは{st.session_state.school_type}{st.session_state.grade}担当。
【最優先指令】クイズを必ず【例外なく{count}問】作成せよ。
【ミッション: {subject_choice}】{SUBJECT_PROMPTS[subject_choice]}
【重要】解説ブロック（explanation_blocks）の文章は、必ず【解説スタイル：{style_choice}】に適合する口調・雰囲気・トーンで出力せよ。
【絶対ルール】
1. 要約禁止。画像内の全文章を一言一句100%網羅せよ。
2. ブロック（explanation_blocks）は最大5行とし、意味のまとまりで分割せよ。
3. ページ番号 [P.xx] は必ず各ブロックの先頭に記述し、直後で改行せよ。
###JSONフォーマット###
{{ "detected_subject": "{subject_choice}", "page": "数字(判定不可なら0)", "explanation_blocks": [{{"text": "[P.〇]\\n(本文)" }}], "english_only_script": "英文", "boost_comments": {{ "high": {{"text":"素晴らしい！満点です！この調子でどんどん進みましょう！","script":"すばらしい まんてんです このちょうしでどんどんすすみましょう"}}, "mid": {{"text":"よく頑張りました！間違えたところを復習して、もう一度挑戦してみよう！","script":"よくがんばりました まちがえたところをふくしゅうして もういちどちょうせんしてみよう"}}, "low": {{"text":"次に期待です！教科書をもう一度よく読んで、ゆっくり解き直してみよう。","script":"つぎにきたいです きょうかしょをもういちどよくよんで ゆっくりときなおしてみよう"}} }}, "quizzes": [{{ "question":"..", "options":[".."], "answer":0 }}] }}"""
            img = Image.open(cam_file)
            res_raw = model.generate_content([full_prompt, img])
            match = re.search(r"(\{.*\})", res_raw.text, re.DOTALL)
            if match:
                st.session_state.final_json = json.loads(match.group(1))
                st.session_state.final_json["used_subject"] = subject_choice

    if st.session_state.final_json:
        res = st.session_state.final_json
        used_sub = res.get("used_subject", subject_choice)
        
        # ⑥ 【ページ数連動 ＆ 手動修正ボックス】の設置
        st.markdown("---")
        try:
            # AIが検出したページ数を初期値にする（読み取れなかった場合は 0 に倒す）
            ai_detected_page = int(res.get("page", 0))
        except:
            ai_detected_page = 0
            
        # 画面上に「AI判定値」を初期値とした入力ボックスを生成
        final_page_input = st.number_input("📖 対象ページ（AIの誤認識はここで手入力修正できます）", min_value=0, max_value=999, value=ai_detected_page)
        
        # ユーザーが変更した値をリアルタイムでデータに反映
        res["page"] = str(final_page_input)
        st.markdown("---")

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
                if used_sub == "英語":
                    st.markdown(block["text"])
                else:
                    st.markdown(f'<div class="content-body">{block["text"]}</div>', unsafe_allow_html=True)
                
                if st.session_state.show_voice_btns:
                    if st.button(f"▶ 再生", key=f"v_{i}"):
                        # ⑨ 英語の時は個別音声も「en-US」を確定で割り当てる
                        lang = "en-US" if used_sub == "英語" else "ja-JP"
                        speak_js(get_clean_speech_text(block["text"]), st.session_state.voice_speed, lang)

        # 確認クイズコーナー
        with st.expander("📝 確認クイズ", expanded=True):
            score = 0
            all_answered = True
            q_list = res.get("quizzes", [])
            
            # 通常時と復習時でキーの重複を防ぐ
            k_prefix = "review" if st.session_state.get("review_mode", False) else "normal"
            
            for i, q in enumerate(q_list):
                ans = st.radio(f"問{i+1}: {q['question']}", q['options'], key=f"{k_prefix}_q_{i}", index=None)
                if ans:
                    if q['options'].index(ans) == q['answer']:
                        st.success("⭕ 正解")
                        score += 1
                    else: 
                        st.error(f"❌ 正解: {q['options'][q['answer']]}")
                else: 
                    all_answered = False
            
            if all_answered and st.button("✨ 履歴に保存", use_container_width=True, key=f"{k_prefix}_save_btn"):
                rate = (score / len(q_list)) * 100
                st.metric("正解率", f"{rate:.0f}%")
                rank = "high" if rate == 100 else "mid" if rate >= 50 else "low"
                
                # ⑧ 単語切れ端ではなく、文章になった完全なスクリプトを再生
                speak_js(res["boost_comments"][rank]["script"], st.session_state.voice_speed)
                
                subj = res.get("used_subject", "不明")
                if subj not in st.session_state.history: 
                    st.session_state.history[subj] = []
                    
                # ③ タイムゾーン問題対策（日本時間の関数を利用）
                st.session_state.history[subj].append({
                    "date": get_jst_now_str(), 
                    "page": res.get("page", "--"), 
                    "score": f"{rate:.0f}%", 
                    "quizzes": q_list
                })
                save_history(st.session_state.history)
                st.toast("日本時間で履歴を記録しました！")
