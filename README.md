# 🧠 Calendar AI Assistant (LangChain + FastAPI + Streamlit + Google Calendar API)

An AI-powered assistant that can **book**, **reschedule**, or **cancel** events in your **Google Calendar** using natural language input. Built with **LangChain**, **FastAPI**, **Streamlit**, and **Google Calendar API**.

---

## 🚀 Live Deployment
🔗 [Streamlit App](https://your-streamlit-app-url)

---

## ✨ Features
- Book appointments using natural language (e.g., "Schedule a call with John at 5pm tomorrow")
- Reschedule existing calendar events ("Move standup to next Monday at 9am")
- Cancel appointments by name ("Cancel the demo with Alice")
- Multi-turn conversation support via LangChain + OpenAI Function Calling
- Beautiful, responsive UI built with Streamlit

---

## 🧰 Tech Stack

| Layer       | Technology                          |
|-------------|--------------------------------------|
| **Frontend**| Streamlit + Custom CSS               |
| **Backend** | FastAPI                              |
| **LLM Agent** | OpenAI GPT-4 + LangChain Functions |
| **Calendar API** | Google Calendar API             |
| **Auth**    | OAuth2 (Service Account)             |

---

## 📁 Project Structure

```
calendar_bot/
├── backend/
│   ├── main.py               # FastAPI app and chat endpoint
│   ├── agent.py              # LangChain agent with tools
│   ├── calendar_utils.py     # Google Calendar interaction utils
│   ├── credentials.json      # Service account key (NOT COMMITTED)
│   └── requirements.txt      # Backend dependencies
│
├── frontend/
│   ├── streamlit_app.py      # Streamlit frontend
│   └── chat_history.json     # Local chat history (optional)
└── README.md
```

---

## 🔧 Local Setup

### 1. Clone the Repo
```bash
git clone https://github.com/your-username/calendar-bot.git
cd calendar-bot
```

### 2. Create Virtual Environment & Install Backend Dependencies
```bash
cd backend
python -m venv venv
venv\Scripts\activate     # On Windows
# or
source venv/bin/activate  # On macOS/Linux

pip install -r requirements.txt
```

### 3. Add Environment Variables
Create a `.env` file in `backend/`:
```
OPENAI_API_KEY=your_openai_key
GOOGLE_CREDENTIALS_PATH=credentials.json
```

Place your `credentials.json` (Google service account key) in the `backend/` folder.

### 4. Start the FastAPI Backend
```bash
uvicorn main:app --reload --port 8000
```

### 5. Run the Streamlit Frontend
In another terminal:
```bash
cd frontend
streamlit run streamlit_app.py
```

The app will be live at: `http://localhost:8501`

---

## 🏗️ Deployment (Render.com - Free Tier Friendly)

### ✅ Backend (FastAPI)

1. Push your backend folder to a GitHub repo.
2. Create a new Web Service on [Render](https://render.com/).
3. Set the repo, and fill in:
    - **Build Command**: `pip install -r backend/requirements.txt`
    - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port 8000`
    - **Environment Variables**:
        - `OPENAI_API_KEY`: your OpenAI key
        - `GOOGLE_CREDENTIALS_PATH`: `credentials.json`
4. Upload your `credentials.json` using Render’s **Secret Files**.
5. Set the path `/etc/secrets/credentials.json` and match it in your `.env` file.

> 🔁 You may need to update your code to use the correct relative path for deployment:
```python
os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")
```

---

### ✅ Frontend (Streamlit)

You can:
- Deploy on [Streamlit Community Cloud](https://streamlit.io/cloud)
- Or create another web service on Render

Make sure to set `API_URL` in `streamlit_app.py`:
```python
API_URL = "https://your-backend-service-name.onrender.com/chat"
```

---

## 🧪 Example Prompts
- "Book a meeting with Ravi on Friday at 4pm for 30 minutes"
- "Cancel project demo with Sarah"
- "Move team sync to Tuesday at 3pm"

---

## 📎 Screenshots

### Booking an Event
![Screenshot 1](screenshots/book_event.png)

### Rescheduling
![Screenshot 2](screenshots/reschedule.png)

---

## 📦 Backend Dependencies
```
langgraph==0.5.1
langchain==0.2.11
langchain-openai==0.1.13
fastapi
uvicorn
python-dotenv
pydantic
requests
google-api-python-client
google-auth
google-auth-oauthlib
google-auth-httplib2
dateparser
```
Install with:
```bash
pip install -r requirements.txt
```

---

## 📚 References
- [LangChain Docs](https://docs.langchain.com)
- [Google Calendar API](https://developers.google.com/calendar)
- [Render Docs](https://render.com/docs)
- [Streamlit](https://docs.streamlit.io/)
