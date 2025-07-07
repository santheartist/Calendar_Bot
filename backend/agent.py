from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory, ChatMessageHistory # Added ChatMessageHistory
from langchain.pydantic_v1 import BaseModel
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import dateparser
import os
from dotenv import load_dotenv
from calendar_utils import (
    create_event,
    reschedule_event,
    cancel_event,
    get_available_slots,
    get_filtered_slots,
)

# ⬇️ Agent core setup
from langchain.agents.openai_functions_agent.agent_token_buffer_memory import AgentTokenBufferMemory
from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent
from langchain.agents import AgentExecutor
from langchain_core.runnables.history import RunnableWithMessageHistory
# from langchain_community.chat_message_histories import StreamlitChatMessageHistory # Removed Streamlit-specific history

load_dotenv()

# 📌 Schemas for tool inputs
class AppointmentInput(BaseModel):
    title: str
    date: str
    time: str
    duration: int

class RescheduleInput(BaseModel):
    title: str
    new_date: str
    new_time: str
    duration: int

class CancelInput(BaseModel):
    title: str

class SlotQueryInput(BaseModel):
    query: str

# ✅ Book Appointment Tool Function
def book_appointment(title: str, date: str, time: str, duration: int) -> str:
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        settings = {
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": now,
        }
        parsed = dateparser.parse(f"{date} {time}", settings=settings)
        if not parsed:
            return "❌ Could not parse date/time."
        # Ensure the parsed date is in the future relative to now, handling year wrap-around
        if parsed < now:
            # If parsed date is in the past, try to move it to the current year
            parsed_this_year = parsed.replace(year=now.year)
            if parsed_this_year < now:
                # If still in the past, move it to the next year
                parsed = parsed.replace(year=now.year + 1)
            else:
                parsed = parsed_this_year
        
        end = parsed + timedelta(minutes=duration)
        return create_event(
            summary=title,
            start_iso=parsed.isoformat(),
            end_iso=end.isoformat(),
            timezone="Asia/Kolkata"
        )
    except Exception as e:
        return f"❌ Error booking appointment: {e}"

# 🔁 Reschedule Appointment Tool Function
def reschedule(title: str, new_date: str, new_time: str, duration: int) -> str:
    try:
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        settings = {
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": now,
        }
        parsed = dateparser.parse(f"{new_date} {new_time}", settings=settings)
        if not parsed:
            return "❌ Could not parse new date/time."
        # Ensure the parsed date is in the future relative to now
        if parsed < now:
            parsed_this_year = parsed.replace(year=now.year)
            if parsed_this_year < now:
                parsed = parsed.replace(year=now.year + 1)
            else:
                parsed = parsed_this_year

        end = parsed + timedelta(minutes=duration)
        return reschedule_event(title, parsed.isoformat(), end.isoformat())
    except Exception as e:
        return f"❌ Error rescheduling event: {e}"

# ❌ Cancel Appointment Tool Function
def cancel(title: str) -> str:
    try:
        return cancel_event(title)
    except Exception as e:
        return f"❌ Error while cancelling event: {e}"

# 📅 List All Upcoming Events Tool Function
def list_available_slots() -> str:
    try:
        events = get_available_slots()
        if not events:
            return "🎉 You have no scheduled events — your calendar is wide open today!"
        response = "📅 Here are your upcoming events:\n"
        for ev in events:
            # Ensure timezone awareness when formatting
            start_dt = datetime.fromisoformat(ev["start"]).astimezone(ZoneInfo("Asia/Kolkata"))
            end_dt = datetime.fromisoformat(ev["end"]).astimezone(ZoneInfo("Asia/Kolkata"))
            start_formatted = start_dt.strftime("%b %d %I:%M %p")
            end_formatted = end_dt.strftime("%I:%M %p")
            response += f"• {ev['summary']}: {start_formatted} → {end_formatted}\n"
        return response.strip()
    except Exception as e:
        return f"❌ Could not fetch calendar slots: {e}"

# 🔍 Natural Language Slot Query Tool Function
def check_slots(query: str) -> str:
    try:
        slots = get_filtered_slots(query)
        if not slots:
            return "❌ No matching events or slots found."
        # Formatted output for better readability
        return "🗓️ Here are the matching events:\n" + "\n".join([f"• {s['summary']} ({s['start']} → {s['end']})" for s in slots])
    except Exception as e:
        return f"❌ Error checking slots: {e}"

# 🛠️ Tool Wrappers using StructuredTool for better schema adherence
calendar_tool = StructuredTool.from_function(
    func=book_appointment,
    name="book_appointment_tool",
    description="Book a meeting in Google Calendar using title, date, time, and duration. Assumes Asia/Kolkata timezone.",
    args_schema=AppointmentInput
)

reschedule_tool = StructuredTool.from_function(
    func=reschedule,
    name="reschedule_event_tool",
    description="Reschedule a Google Calendar event by title. Provide new date, time, and duration.",
    args_schema=RescheduleInput
)

cancel_tool = StructuredTool.from_function(
    func=cancel,
    name="cancel_event_tool",
    description="Cancel a Google Calendar event by title.",
    args_schema=CancelInput
)

list_slots_tool = StructuredTool.from_function(
    func=list_available_slots,
    name="list_available_slots_tool",
    description="Use this to list all upcoming calendar events.",
)

filter_slots_tool = StructuredTool.from_function(
    func=check_slots,
    name="check_availability_tool",
    description="Check Google Calendar for available slots using a natural language query like 'slots today', 'meetings this week', or 'free after 2pm'.",
    args_schema=SlotQueryInput
)

# List of all tools available to the agent
all_tools = [
    calendar_tool,
    reschedule_tool,
    cancel_tool,
    list_slots_tool,
    filter_slots_tool
]

# 🤖 Language model
llm = ChatOpenAI(model="gpt-4", temperature=0)

# 🧠 Session store for message history.
# For a FastAPI backend, StreamlitChatMessageHistory is not suitable as it relies on Streamlit's session state.
# We'll use a simple in-memory dictionary to store ChatMessageHistory instances per session ID.
# For production, consider a persistent store like Redis or a database.
_session_history: dict[str, ChatMessageHistory] = {}

def get_session_history(session_id: str) -> ChatMessageHistory:
    """Retrieves or creates a ChatMessageHistory for a given session ID."""
    if session_id not in _session_history:
        _session_history[session_id] = ChatMessageHistory()
    return _session_history[session_id]

# 🧩 Use OpenAI agent with retrying parser for better multi-turn slot filling
# The agent is defined outside the factory, as it's the core logic.
agent = OpenAIFunctionsAgent.from_llm_and_tools(
    llm=llm,
    tools=all_tools,
)

# 🔁 Full agent executor with memory + verbose logging
# Note: The memory here is a placeholder; RunnableWithMessageHistory will manage the actual per-session memory.
agent_executor = AgentExecutor(
    agent=agent,
    tools=all_tools,
    # Use AgentTokenBufferMemory for agent's internal thought process,
    # but the overall session history is handled by RunnableWithMessageHistory
    memory=AgentTokenBufferMemory(memory_key="chat_history", llm=llm, return_messages=True),
    verbose=True,
    handle_parsing_errors=True, # Important for robustness
)

# 🔁 Wrap with message history support using the custom get_session_history factory
# This creates a factory that RunnableWithMessageHistory can use to get the correct history for each session.
def get_agent_with_history_factory():
    return RunnableWithMessageHistory(
        agent_executor,
        get_session_history, # Use our custom session history getter
        input_messages_key="input", # Key for new user input
        history_messages_key="chat_history", # Key where the agent expects history in the state
    )
