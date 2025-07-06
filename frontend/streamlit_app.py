import streamlit as st
import requests
import os
import json
import re
from datetime import datetime

# --- Constants ---
API_URL = "http://127.0.0.1:8000/chat"
EVENTS_API_URL = "http://127.0.0.1:8000/events"
CHAT_HISTORY_FILE = "chat_history.json"

# --- Utility: Linkify calendar URLs ---
def render_message_with_links(text):
    url_pattern = r'(https?://[^\s]+)'
    return re.sub(url_pattern, lambda m: f'<a href="{m.group(1)}" target="_blank" style="color:#bbdefb;text-decoration:underline;">{m.group(1)}</a>', text)

# --- Page Setup ---
st.set_page_config(
    page_title="📅 Calendar AI Assistant",
    page_icon="📅",
    layout="centered",
    initial_sidebar_state="expanded"
)

# --- CSS Styling ---
st.markdown("""
<style>
html, body, [class*="stApp"] {
    background: linear-gradient(135deg, #002f2f, #121212) !important;
    color: #f0f0f0 !important;
    font-family: 'Segoe UI', 'Roboto', sans-serif;
    margin: 0;
    padding: 0;
}
.block-container {
    padding: 2rem 3rem !important;
    display: flex;
    flex-direction: column;
    align-items: center;
}
[data-testid="stSidebar"] {
    background: rgba(30, 30, 30, 0.95);
    color: white;
    border-right: 1px solid rgba(255,255,255,0.05);
}
[data-testid="stSidebar"] .stButton > button {
    background-color: #1e88e5;
    color: white;
    width: 100%;
    margin-bottom: 0.5rem;
    border-radius: 6px;
    padding: 0.5rem;
    font-size: 0.9rem;
    border: none;
    transition: background 0.2s ease;
}
[data-testid="stSidebar"] .stButton > button:hover {
    background-color: #1565c0;
}
.title-wrapper {
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2rem;
    font-weight: 600;
    color: #e0f2f1;
    margin-bottom: 0.25rem;
}
.title-wrapper .emoji {
    font-size: 2.2rem;
    margin-right: 0.5rem;
}
.subtitle {
    text-align: center;
    color: #f0f0f0;
    margin-bottom: 1rem;
}
.chat-container {
    padding: 1.5rem 0;
    border-radius: 12px;
    margin-top: 1rem;
    max-width: 100%;
}
.stChatMessage {
    display: flex;
    align-items: flex-start;
    margin: 0.6rem 0;
}
.user-msg, .bot-msg {
    display: flex;
    max-width: 75%;
    padding: 0.75rem 1rem;
    border-radius: 16px;
    color: white;
    font-size: 1rem;
}
.user-msg {
    background-color: #1976d2;
    margin-left: auto;
    border-radius: 16px 4px 16px 16px;
    flex-direction: row-reverse;
}
.bot-msg {
    background-color: #43a047;
    margin-right: auto;
    border-radius: 4px 16px 16px 16px;
}
.avatar {
    font-size: 1.3rem;
    margin: 0 0.5rem;
    line-height: 1;
}
.message-text {
    flex: 1;
    word-break: break-word;
}
.stTextInput > div > div > input {
    background-color: rgba(255,255,255,0.1);
    border-radius: 10px;
    border: 1px solid rgba(255,255,255,0.2);
    padding: 0.6rem 1rem;
    color: white;
    font-size: 1rem;
}
.footer-text {
    text-align: center;
    font-size: 0.9rem;
    color: #bbb;
    margin-top: 2rem;
    border-top: 1px solid rgba(255,255,255,0.1);
    padding-top: 1rem;
    opacity: 0.8;
}
#MainMenu, footer {
    visibility: hidden;
}
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("""
<div class="title-wrapper">
  <span class="emoji">📅</span>
  <span>Google Calendar Booking Assistant</span>
</div>
<div class="subtitle">
  Let me help you manage your schedule! Just tell me what you want. 🧠
</div>
""", unsafe_allow_html=True)

# --- Load Chat History ---
if "messages" not in st.session_state:
    if os.path.exists(CHAT_HISTORY_FILE):
        try:
            with open(CHAT_HISTORY_FILE, "r") as f:
                st.session_state.messages = json.load(f)
        except json.JSONDecodeError:
            st.warning("Chat history corrupted. Starting new chat.")
            st.session_state.messages = []
    else:
        st.session_state.messages = []

# --- Sidebar ---
with st.sidebar:
    st.header("📅 Upcoming Events")
    try:
        res = requests.get(EVENTS_API_URL, headers={'Accept': 'application/json'})
        if res.status_code == 200:
            events = res.json().get("events", [])
            if not events:
                st.info("No upcoming events.")
            else:
                for event in events:
                    start_time = datetime.fromisoformat(event['start'].replace('Z', '+00:00')).strftime('%b %d, %I:%M %p')
                    end_time = datetime.fromisoformat(event['end'].replace('Z', '+00:00')).strftime('%I:%M %p')
                    st.markdown(f"""
                    **{event['summary']}**  
                    🕒 {start_time} → {end_time}
                    """)
        else:
            st.warning(f"Error fetching events ({res.status_code}): {res.text}")
    except Exception as e:
        st.warning(f"Event API error: {e}")

    st.header("💡 Try Prompts")
    example_prompts = [
        "📅 Book a 30 min meeting with Alice tomorrow at 10am",
        "🗓️ Show my meetings for next Monday",
        "🕒 Reschedule standup to Friday 3pm",
        "🗑️ Cancel demo session on July 15"
    ]
    for prompt in example_prompts:
        if st.button(prompt, key=prompt):
            st.session_state.user_input = prompt
            st.rerun()

    if st.button("🧹 Clear Chat History"):
        st.session_state.messages = []
        if os.path.exists(CHAT_HISTORY_FILE):
            os.remove(CHAT_HISTORY_FILE)
        st.rerun()

# --- Chat Input ---
user_input = st.chat_input("Ask me to book or check your calendar...")

if "user_input" in st.session_state:
    user_input = st.session_state.pop("user_input")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.spinner("🤖 Thinking..."):
        try:
            res = requests.post(API_URL, json={"message": user_input}, headers={'Content-Type': 'application/json'})
            if res.status_code == 200:
                reply = res.json().get("response", "🤖 Sorry, I couldn't understand.")
            else:
                reply = f"⚠️ Backend Error ({res.status_code}): {res.text}"
        except Exception as e:
            reply = f"⚠️ Error: {e}"
    st.session_state.messages.append({"role": "bot", "content": reply})

    with open(CHAT_HISTORY_FILE, "w") as f:
        json.dump(st.session_state.messages, f)

# --- Display Chat ---
st.markdown('<div class="chat-container">', unsafe_allow_html=True)
for msg in st.session_state.messages:
    role_class = "user-msg" if msg["role"] == "user" else "bot-msg"
    avatar = "👤" if msg["role"] == "user" else "🤖"
    content = render_message_with_links(msg["content"]) if msg["role"] == "bot" else msg["content"]
    st.markdown(
        f'<div class="stChatMessage {role_class}">' 
        f'<div class="avatar">{avatar}</div>' 
        f'<div class="message-text">{content}</div>' 
        f'</div>',
        unsafe_allow_html=True
    )
st.markdown('</div>', unsafe_allow_html=True)

# --- Footer ---
st.markdown('<div class="footer-text">', unsafe_allow_html=True)
st.markdown(
    f"🤖 Built by Sanchit Panda | ✨ Powered by Streamlit + LangChain + OpenAI {datetime.now().year}",
    unsafe_allow_html=True
)
st.markdown('</div>', unsafe_allow_html=True)
