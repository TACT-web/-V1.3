import streamlit as st
import json, os, re, datetime

# --- アプリ全体設定の保存先（APIキーや区分など） ---
CONFIG_FILENAME = "app_config.json"

def load_app_config():
    if os.path.exists(CONFIG_FILENAME):
        try:
            with open(CONFIG_FILENAME, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_app_config(cfg_data):
    with open(CONFIG_FILENAME, "w", encoding="utf-8") as f:
        json.dump(cfg_data, f, ensure_ascii=False, indent=2)

# --- 履歴管理 ---
def get_history_filename():
    s_type = st.session_state.get("school_type", "未設定")
    grade = st.session_state.get("grade", "未設定")
    return f"history_{s_type}_{grade}.json"

def load_history():
    filename = get_history_filename()
    if os.path.exists(filename):
        try:
            with open(filename, "r", encoding="utf-8") as f:
                return json.load(f)
        except: return {}
    return {}

def save_history(history):
    filename = get_history_filename()
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

# --- 日本標準時（JST）の現在時刻を取得 ---
def get_jst_now_str():
    # サーバー時間に依存せず常に日本時間に補正
    now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
    return now.strftime("%Y-%m-%d %H:%M")

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
        </script>"""
        st.components.v1.html(js_code, height=0)
    else:
        st.components.v1.html("<script>window.parent.speechSynthesis.cancel();</script>", height=0)

def get_clean_speech_text(text):
    if not text: return ""
    clean_text = re.sub(r'\[P\..+?\]', '', text)
    clean_text = re.sub(r'\|', ' ', clean_text)
    clean_text = re.sub(r'<[^>]+>', '', clean_text)
    clean_text = clean_text.replace('**', '').replace('---', '')
    return clean_text.strip()
