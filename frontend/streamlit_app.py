import streamlit as st
import requests
import os
import json
import re
from datetime import datetime
import uuid

# --- Constants ---
API_URL = "https://calendar-bot-twkt.onrender.com/chat"
EVENTS_API_URL = "https://calendar-bot-twkt.onrender.com/events"
CHAT_HISTORY_FILE = "chat_history.json"

# --- Session ID ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

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
st.markdown("""<style>
/* Keep your full CSS unchanged here */
</style>""", unsafe_allow_html=True)

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
                    st.markdown(f"**{event['summary']}**  \n🕒 {start_time} → {end_time}")
        else:
            st.warning(f"Error fetching events ({res.status_code}): {res.text}")
    except Exception as e:
        st.warning(f"Event API error: {e}")

    st.header("💡 Try Prompts")
    prompts = [
        "📅 Book a 30 min meeting with Alice tomorrow at 10am",
        "🗓️ Show my meetings for next Monday",
        "🕒 Reschedule standup to Friday 3pm",
        "🗑️ Cancel demo session on July 15"
    ]
    for prompt in prompts:
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
            payload = {
                "input": user_input,
                "config": {"configurable": {"session_id": st.session_state.session_id}}
            }
            res = requests.post(API_URL, json=payload, headers={"Content-Type": "application/json"})
            if res.status_code == 200:
                reply = res.json().get("output", "🤖 Sorry, I couldn't understand.")
            else:
                reply = f"⚠️ Error {res.status_code}: {res.text}"
        except Exception as e:
            reply = f"⚠️ Exception: {e}"

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
