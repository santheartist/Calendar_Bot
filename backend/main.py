from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import get_agent
from calendar_utils import get_available_slots

app = FastAPI()
agent_executor = get_agent()

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
    if "message" in req:
        user_input = req["message"]
        session_id = "default"
    else:
        user_input = req["input"]
        session_id = req.get("config", {}).get("configurable", {}).get("session_id", "default")

    config = {"configurable": {"session_id": session_id}}

    try:
        result = agent_executor.invoke(
            {"input": user_input},
            config=config
        )

        # Safely extract output and intermediate_steps
        if isinstance(result, dict):
            output_text = result.get("output", "")
            steps = result.get("intermediate_steps", [])
        else:
            output_text = str(result)
            steps = []

        return {
            "message": output_text,
            "role": "assistant",
            "metadata": {
                "session_id": session_id,
                "intermediate_steps": steps,
                "status": "success" if output_text else "error"
            }
        }
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
