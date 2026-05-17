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

# --- アプリ起動時：保存されている設定の自動ロード ---
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

# --- 固定サイドバーへのコントロール配置 ---
st.sidebar.header("🛑 音声コントロール")
if st.sidebar.button("🛑 音声を今すぐ停止", use_container_width=True, key="sidebar_stop_btn"):
    speak_js("")

st.sidebar.markdown("---")
st.sidebar.header("🛠️ 画面・音声調整")
st.session_state.font_size = st.sidebar.slider("🔍 文字サイズ", 14, 45, st.session_state.font_size)
st.session_state.voice_speed = st.sidebar.slider("🐌 音声速度", 0.5, 2.0, st.session_state.voice_speed, 0.1)

# 【重要】余計なHTMLタグを使わず、Streamlitのすべての文字・テーブルサイズをグローバルに強制変更するCSS
st.markdown(f"""
<style>
/* 通常のテキスト、箇条書き、マークダウン全ての文字サイズ */
.stMarkdown p, .stMarkdown li {{ font-size: {st.session_state.font_size}px !important; line-height: 1.6 !important; }}
/* テーブル（表形式）の文字サイズとデザイン */
.stMarkdown table {{ font-size: {st.session_state.font_size}px !important; width: 100% !important; border-collapse: collapse !important; }}
.stMarkdown th, .stMarkdown td {{ border: 1px solid #ccc !important; padding: 8px !important; text-align: left !important; }}
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
            
            save_app_config({
                "user_api_key": user_key, "school_type": school_type, "grade": grade, "quiz_count": quiz_count
            })
            st.session_state.history = load_history()
            st.session_state.setup_completed = True
            st.rerun()
    st.stop()


# --- 3. メインタブ管理 ---
tab_titles = ["📖 学習", "📈 履歴", "⚙️ 設定変更"]

if "current_tab" not in st.session_state:
    st.session_state.current_tab = "📖 学習"

selected_tab = st.radio("ナビゲーション", tab_titles, index=tab_titles.index(st.session_state.current_tab), horizontal=True, label_visibility="collapsed")
st.session_state.current_tab = selected_tab

st.markdown("---")

# 📈 履歴タブ
if st.session_state.current_tab == "📈 履歴":
    st.markdown(f"### 📂 {st.session_state.school_type} {st.session_state.grade} の学習履歴")
    
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
        all_logs_sorted = sorted(all_logs, key=lambda x: x["date"], reverse=True)
        
        with st.container(height=400, border=True):
            for item in all_logs_sorted:
                with st.expander(f"【{item['subject']}】 p.{item['page']} - 正解率: {item['score']} ({item['date']})"):
                    orig_log = st.session_state.history[item['subject']][item['orig_idx']]
                    st.write(f"📝 収録問題数: {len(orig_log.get('quizzes', []))}問")
                    
                    if st.button("🔁 このクイズを解き直す", key=f"rev_btn_{item['subject']}_{item['orig_idx']}"):
                        st.session_state.final_json = {
                            "explanation_blocks": [{"text": f"### 🕒 復習モード（{item['subject']} p.{item['page']}）"}],
                            "quizzes": orig_log["quizzes"],
                            "used_subject": item['subject'],
                            "page": item['page']
                        }
                        st.session_state.review_mode = True
                        st.session_state.current_tab = "📖 学習"
                        st.rerun()

# ⚙️ 設定変更タブ
elif st.session_state.current_tab == "⚙️ 設定変更":
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
            st.session_state.current_tab = "📖 学習"
            st.rerun()

# 📖 学習タブ
elif st.session_state.current_tab == "📖 学習":
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
            
            # 【修正点】未完だったf-stringのプロンプトとJSONテンプレートを閉じカッコ「"""」できちんと閉じました。
            # また、プロンプト内で「{」や「}」を変数展開ではなく単なる文字として扱うため「{{」「}}」にエスケープしています。
            full_prompt = f"""あなたは{st.session_state.school_type}{st.session_state.grade}担当。
【最優先指令】クイズを必ず【例外なく{count}問】作成せよ。
【ミッション: {subject_choice}】{SUBJECT_PROMPTS[subject_choice]}
【重要】解説ブロック（explanation_blocks）の文章は、必ず【解説スタイル：{style_choice}】に適合する口調・雰囲気・トーンで出力せよ。
【絶対ルール】
1. 要約禁止。画像内の全文章を一言一句100%網羅せよ。
2. ブロック（explanation_blocks）は最大5行とし、意味のまとまりで分割せよ。
3. ページ番号 [P.xx] は必ず各ブロックの先頭に記述し、直後で改行せよ。
###JSONフォーマット###
{{ 
  "detected_subject": "{subject_choice}", 
  "page": "数字(判定不可なら0)", 
  "explanation_blocks": [{{"text": "[P.〇]\\n(本文)" }}], 
  "english_only_script": "英文", 
  "boost_comments": {{ 
    "high": {{"text":"素晴らしい！満点です！この調子でどんどん進みましょう！","script":"すばらしい まんてんです このちょうしでどんどんすすみましょう"}}, 
    "mid": {{"text":"よく頑張りました！間違えたところを復習して、もう一度挑戦してみよう！","script":"よくがんばりました まちがえたところをふくしゅうして もういちどちょうせんしてみよう"}}, 
    "low": {{"text":"次に期待です！教科書をもう一度よく読み直してみましょう。","script":"つぎにきたいです きょうかしょをもういちどよくよみなおしてみましょう"}}
  }},
  "quizzes": [
    {{
      "question": "問題文",
      "options": ["選択肢1", "選択肢2", "選択肢3", "選択肢4"],
      "answer": 0
    }}
  ]
}}"""
            
            img = Image.open(cam_file)
            res_raw = model.generate_content([full_prompt, img])
            match = re.search(r"(\{.*?\})", res_raw.text, re.DOTALL)
           
            if match:
                st.session_state.final_json = json.loads(match.group(1))
                st.session_state.final_json["used_subject"] = subject_choice

    if st.session_state.final_json:
        res = st.session_state.final_json
        used_sub = res.get("used_subject", subject_choice)
        
        # ページ調整入力
        st.markdown("---")
        try:
            ai_detected_page = int(res.get("page", 0))
        except:
            ai_detected_page = 0
            
        final_page_input = st.number_input("📖 対象ページ", min_value=0, max_value=999, value=ai_detected_page)
        res["page"] = str(final_page_input)
        st.markdown("---")

        # 全体音声ボタン
        v_cols = st.columns(3)
        if v_cols[0].button("🔊 全文再生"):
            full_text = " ".join([b["text"] for b in res["explanation_blocks"]])
            speak_js(get_clean_speech_text(full_text), st.session_state.voice_speed)
        if used_sub == "英語" and v_cols[1].button("🔊 英語のみ連続再生"):
            speak_js(res.get("english_only_script"), st.session_state.voice_speed, "en-US")
        if v_cols[2].button("🔊 個別再生ボタンを表示"):
            st.session_state.show_voice_btns = not st.session_state.show_voice_btns
            st.rerun()

        # 本文ブロックループ
        for i, block in enumerate(res["explanation_blocks"]):
            with st.container(border=True):
                # HTMLタグがマークダウンの表構造を破壊しないよう、外側をセーフティラップ
                st.markdown(f'<div class="content-body">', unsafe_allow_html=True)
                st.markdown(block["text"])
                st.markdown(f'</div>', unsafe_allow_html=True)
                
                if st.session_state.show_voice_btns:
                    if st.button(f"▶ 再生", key=f"v_{i}"):
                        if used_sub == "英語":
                            # 表形式マークダウン（揺れ対応版）から英文列を正確に抽出
                            lines = block["text"].split("\n")
                            english_sentences = []
                            for line in lines:
                                if "|" in line:
                                    # 先頭や末尾の空要素を除去しつつ分割
                                    parts = [p.strip() for p in line.split("|") if p.strip() or line.startswith("|")]
                                    # 分割された要素から英文（2番目のデータ）を安全に追跡
                                    if len(parts) >= 3:
                                        # ヘッダーや区切り線を弾く
                                        role_check = parts[0].replace("*", "")
                                        en_text = parts[1].replace("*", "")
                                        if "役割" not in role_check and "---" not in role_check and en_text != "英文":
                                            english_sentences.append(en_text)
                            
                            speech_target = " ".join(english_sentences)
                            if not speech_target:
                                speech_target = get_clean_speech_text(block["text"])
                                
                            speak_js(speech_target, st.session_state.voice_speed, "en-US")
                        else:
                            speak_js(get_clean_speech_text(block["text"]), st.session_state.voice_speed, "ja-JP")

        # クイズコーナー
        with st.expander("📝 確認クイズ", expanded=True):
            score = 0
            all_answered = True
            q_list = res.get("quizzes", [])
            
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
              
                speak_js(res["boost_comments"][rank]["script"], st.session_state.voice_speed)
                
                subj = res.get("used_subject", "不明")
                if subj not in st.session_state.history: 
                    st.session_state.history[subj] = []
                     
                st.session_state.history[subj].append({
                    "date": get_jst_now_str(), 
                    "page": res.get("page", "--"), 
                    "score": f"{rate:.0f}%", 
                    "quizzes": q_list
                })
                save_history(st.session_state.history)
                st.toast("保存完了！")
