from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import get_agent_with_history_factory # Updated import
from calendar_utils import get_available_slots
from typing import Dict, Any, List

app = FastAPI()

# Initialize the agent factory. The actual agent executor for each session will be created on demand.
agent_history_factory = get_agent_with_history_factory()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Consider restricting this in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    """Defines the expected input structure for the /chat endpoint."""
    message: str
    # The history field is not directly used by the agent_executor.invoke,
    # as history is managed by RunnableWithMessageHistory.
    # It might be used by the frontend for display, but not for agent logic.
    history: List[Dict[str, str]] = [] # Keeping it if frontend sends it

    # CORRECTED: Simplified config structure.
    # Now, config["configurable"]["session_id"] is expected to be a string.
    config: Dict[str, Dict[str, str]] = {"configurable": {"session_id": "default"}}

@app.post("/chat")
async def chat(req: ChatInput): # Use ChatInput for proper validation
    """
    Handles chat interactions with the LangGraph agent.
    Receives user messages and returns agent responses.
    """
    # Extract user input and session_id from the validated request body
    user_input = req.message
    session_id = req.config.get("configurable", {}).get("session_id", "default")

    # The config dictionary is crucial for RunnableWithMessageHistory to manage session-specific history.
    config_for_agent = {"configurable": {"session_id": session_id}}

    try:
        # Invoke the agent executor for the specific session.
        # The agent_history_factory is now called with the session_id to get the correct history manager.
        result = await agent_history_factory.invoke(
            {"input": user_input},
            config=config_for_agent
        )

        # Defensive check: result might be string or dict
        output_text = ""
        intermediate_steps = []

        if isinstance(result, dict):
            # LangGraph results usually have 'output' and 'intermediate_steps' keys
            output_text = result.get("output", "")
            # Ensure intermediate_steps is a list, even if it's not present
            intermediate_steps = result.get("intermediate_steps", [])
        else:
            # Fallback if the result is not a dictionary (e.g., a simple string response)
            output_text = str(result)
            intermediate_steps = []

        return {
            "message": output_text,
            "role": "assistant",
            "metadata": {
                "session_id": session_id,
                "intermediate_steps": intermediate_steps,
                "status": "success" if output_text else "error"
            }
        }

    except Exception as e:
        print(f"[ERROR] /chat failed for session {session_id}: {e}")
        # Return a 500 Internal Server Error with the exception details
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/events")
async def list_events():
    """
    Retrieves and lists upcoming calendar events.
    """
    try:
        # get_available_slots() already handles the Google Calendar API call.
        events = get_available_slots()
        return {"events": events}
    except Exception as e:
        print(f"[ERROR] /events failed: {e}")
        # Return a 500 Internal Server Error for calendar retrieval issues
        raise HTTPException(status_code=500, detail=str(e))

