from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import get_agent
from calendar_utils import get_available_slots

app = FastAPI()
agent = get_agent()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    message: str
    history: list[dict] = []

@app.post("/chat")
def chat(req: dict):
    # Support both formats
    if "message" in req:
        user_input = req["message"]
        history = req.get("history", [])
        config = {"configurable": {"session_id": "default"}}
    else:
        user_input = req["input"]
        config = req.get("config", {"configurable": {"session_id": "default"}})

    try:
        result = agent_executor.invoke(
            {"input": user_input},
            config=config
        )
        return {"output": result}
    except Exception as e:
        print("[ERROR] /chat failed:", e)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events")
def list_events():
    try:
        return {"events": get_available_slots()}
    except Exception as e:
        print(f"[ERROR] /events failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
