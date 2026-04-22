import streamlit as st
import json, os, re

# --- 履歴管理 ---
def get_history_filename():
    s_type = st.session_state.get("school_type", "未設定")
    grade = st.session_state.get("grade", "未設定") [cite: 1, 2]
    return f"history_{s_type}_{grade}.json" [cite: 2]

def load_history():
    filename = get_history_filename()
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {} [cite: 2]

def save_history(history):
    filename = get_history_filename()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2) [cite: 2, 3]

# --- 音声再生エンジン ---
def speak_js(text, speed=1.0, lang="ja-JP"):
    if text:
        safe_text = text.replace("'", "\\'").replace("\n", " ")
        js_code = f"""<script>
        var synth = window.parent.speechSynthesis;
        synth.cancel();
        var uttr = new SpeechSynthesisUtterance('{safe_text}');
        uttr.rate = {speed};
        uttr.lang = '{lang}';
        synth.speak(uttr);
        </script>""" [cite: 3, 4, 5]
        st.components.v1.html(js_code, height=0) [cite: 5]
    else:
        st.components.v1.html("<script>window.parent.speechSynthesis.cancel();</script>", height=0) [cite: 5]

def get_clean_speech_text(text):
    if not text: return ""
    clean_text = re.sub(r'\[P\..+?\]', '', text)
    clean_text = re.sub(r'\|', ' ', clean_text)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = clean_text.replace('**', '').replace('---', '') [cite: 5]
    return clean_text.strip() [cite: 5]
