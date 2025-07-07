from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel
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
from langchain.agents import AgentExecutor
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# NEW IMPORTS FOR REACT AGENT
from langchain.agents import create_react_agent
from langchain import hub
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage

load_dotenv()

# 📌 Schemas (Keep these at the top, they are simple data structures)
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

# ✅ Book Appointment - MOVE ALL YOUR FUNCTION DEFINITIONS UP HERE
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
        if parsed.year < now.year or parsed < now:
            parsed = parsed.replace(year=now.year)
            if parsed < now:
                parsed = parsed.replace(year=now.year + 1)
        end = parsed + timedelta(minutes=duration)
        # Ensure create_event from calendar_utils returns non-empty string
        event_link = create_event(
            summary=title,
            start_iso=parsed.isoformat(),
            end_iso=end.isoformat(),
            timezone="Asia/Kolkata"
        )
        return event_link if event_link else "❌ Failed to create event and retrieve link."
    except Exception as e:
        return f"❌ Error: {e}"

# 🔁 Reschedule Appointment
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
        if parsed.year < now.year or parsed < now:
            parsed = parsed.replace(year=now.year)
            if parsed < now:
                parsed = parsed.replace(year=now.year + 1)
        end = parsed + timedelta(minutes=duration)
        # Ensure reschedule_event from calendar_utils returns non-empty string
        reschedule_result = reschedule_event(title, parsed.isoformat(), end.isoformat())
        return reschedule_result if reschedule_result else "❌ Failed to reschedule event."
    except Exception as e:
        return f"❌ Error: {e}"

# ❌ Cancel Appointment
def cancel(title: str) -> str:
    try:
        # Ensure cancel_event from calendar_utils returns non-empty string
        cancel_result = cancel_event(title)
        return cancel_result if cancel_result else "❌ Failed to cancel event."
    except Exception as e:
        return f"❌ Error while cancelling event: {e}"

# 📅 List All Upcoming Events
def list_available_slots() -> str:
    try:
        events = get_available_slots()
        if not events:
            return "🎉 You have no scheduled events — your calendar is wide open today!"
        response = "📅 Here are your upcoming events:\n"
        for ev in events:
            start = datetime.fromisoformat(ev["start"]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%b %d %I:%M %p")
            end = datetime.fromisoformat(ev["end"]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
            response += f"• {ev['summary']}: {start} → {end}\n"
        return response.strip() if response.strip() else "❌ No events found or error formatting list."
    except Exception as e:
        return f"❌ Could not fetch calendar slots: {e}"

# 🔍 Natural Language Slot Query
def check_slots(query: str) -> str:
    slots = get_filtered_slots(query)
    if not slots:
        return "❌ No matching events or slots found."
    return "\n".join([f"🗓️ {s['summary']} ({s['start']} → {s['end']})" for s in slots])


# 🛠️ Tool Wrappers - NOW THESE COME AFTER THE FUNCTION DEFINITIONS
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

# 🤖 Language model
llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash", temperature=0)

# 🧠 Memory for the ReAct Agent
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)

# 🧩 Define the tools
tools = [
    calendar_tool,
    reschedule_tool,
    cancel_tool,
    list_slots_tool,
    filter_slots_tool
]

# Create a prompt for the ReAct agent
prompt = hub.pull("hwchase17/react-chat")

# 🧩 Create the ReAct agent
agent = create_react_agent(llm, tools, prompt)

# 🔁 Full agent executor with memory + verbose logging
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
)

# 🔁 Wrap with message history support
agent_with_history = RunnableWithMessageHistory(
    agent_executor,
    lambda session_id: StreamlitChatMessageHistory(key=session_id),
    input_messages_key="input",
    history_messages_key="chat_history",
)

# 🔌 Public getter
def get_agent():
    return agent_with_history
