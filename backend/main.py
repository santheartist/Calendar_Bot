from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from agent import get_agent
from calendar_utils import get_available_slots
from typing import Dict, Any, List, Optional # Import Optional for clarity

# Import BaseMessage for type checking agent output
from langchain_core.messages import BaseMessage

app = FastAPI()

# Initialize the agent factory.
# get_agent() returns the RunnableWithMessageHistory instance directly.
# This instance manages session history internally based on the session_id passed to .invoke().
agent_runnable = get_agent()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Consider restricting this in production (e.g., ["http://localhost:8501", "https://your-streamlit-app.streamlit.app"])
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatInput(BaseModel):
    """Defines the expected input structure for the /chat endpoint."""
    message: str
    history: List[Dict[str, str]] = [] # Frontend might send this for display purposes
    config: Dict[str, Dict[str, str]] = {"configurable": {"session_id": "default"}}

class ChatResponseMetadata(BaseModel):
    session_id: str
    intermediate_steps: List[Any] # Can be more specific if you know the structure of steps
    status: str

class ChatResponse(BaseModel):
    """Defines the expected output structure for the /chat endpoint."""
    message: str
    role: str
    metadata: ChatResponseMetadata

@app.post("/chat", response_model=ChatResponse) # Add response_model for auto-documentation
async def chat(req: ChatInput):
    """
    Handles chat interactions with the LangGraph agent.
    Receives user messages and returns agent responses.
    """
    user_input = req.message
    # Safely get session_id, defaulting to "default"
    session_id = req.config.get("configurable", {}).get("session_id", "default")

    # The config dictionary is crucial for RunnableWithMessageHistory to manage session-specific history.
    config_for_agent = {"configurable": {"session_id": session_id}}

    try:
        # Invoke the agent executor for the specific session using the pre-initialized runnable.
        result = await agent_runnable.ainvoke( # Using agent_runnable directly
            {"input": user_input},
            config=config_for_agent
        )

        output_text = ""
        response_intermediate_steps = []

        # Handle different possible return types from LangChain runnable invoke:
        if isinstance(result, dict):
            # This is the most common and expected output from AgentExecutor (a dict containing 'output')
            output_content = result.get("output")
            response_intermediate_steps = result.get("intermediate_steps", [])

            # If the 'output' within the dict is a BaseMessage, extract its content
            if isinstance(output_content, BaseMessage):
                output_text = output_content.content
            else:
                # Otherwise, assume output_content is already a string or convertible
                output_text = str(output_content) if output_content is not None else ""
        elif isinstance(result, BaseMessage):
            # If the top-level result is a BaseMessage directly (less common for AgentExecutor)
            output_text = result.content
            response_intermediate_steps = []
        else:
            # Fallback for any other unexpected type, convert to string
            output_text = str(result)
            response_intermediate_steps = []

        # Determine status based on whether output_text was generated
        status = "success" if output_text else "error"
        
        return ChatResponse(
            message=output_text,
            role="assistant",
            metadata=ChatResponseMetadata(
                session_id=session_id,
                intermediate_steps=response_intermediate_steps,
                status=status
            )
        )

    except Exception as e:
        import traceback
        print(f"[ERROR] /chat failed for session {session_id}: {e}")
        traceback.print_exc() # Print full traceback for debugging
        # Return a 500 Internal Server Error with the exception type and message for better debugging
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {type(e).__name__}: {e}")


@app.get("/events")
async def list_events():
    """
    Retrieves and lists upcoming calendar events.
    """
    try:
        # get_available_slots() already handles the Google Calendar API call.
        # Assuming get_available_slots is synchronous. If it's async, add `await`.
        events = get_available_slots()
        return {"events": events}
    except Exception as e:
        print(f"[ERROR] /events failed: {e}")
        # Return a 500 Internal Server Error for calendar retrieval issues
        raise HTTPException(status_code=500, detail=f"Internal Server Error: {type(e).__name__}: {e}")
