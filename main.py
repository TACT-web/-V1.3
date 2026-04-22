import streamlit as st
import google.generativeai as genai
from PIL import Image
import io, json, time, re, datetime
# 分割したファイルを読み込む
from config import set_page_config, SUBJECT_PROMPTS
from utils import load_history, save_history, speak_js, get_clean_speech_text

set_page_config()

# --- セッション初期化 ---
for key, val in {
    "agreed": False, "setup_completed": False, "history": {}, 
    "final_json": None, "font_size": 18, "user_api_key": "", 
    "voice_speed": 1.0, "show_voice_btns": False
}.items():
    if key not in st.session_state: st.session_state[key] = val

# --- (ここから下に、元の「同意画面」以降のUIコードを全て記述します) ---
# ※元のコードの「def」部分を消し、適切にimportしたものに置き換えた状態
