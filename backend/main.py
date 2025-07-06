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

@app.post("/chat")
def chat_endpoint(input: ChatInput):
    try:
        result = agent.invoke({"input": input.message})
        return {"response": result["output"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/events")
def list_events():
    try:
        return {"events": get_available_slots()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
