from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel
from calendar_utils import (
    create_event, reschedule_event, cancel_event,
    get_available_slots, get_filtered_slots
)
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import dateparser
from dotenv import load_dotenv
import os

load_dotenv()

# 1️⃣ — SCHEMAS
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


# 2️⃣ — BOOK
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
        if parsed < now:
            parsed = parsed.replace(year=now.year + 1)
        end = parsed + timedelta(minutes=duration)
        return create_event(
            summary=title,
            start_iso=parsed.isoformat(),
            end_iso=end.isoformat(),
            timezone="Asia/Kolkata"
        )
    except Exception as e:
        return f"❌ Error: {e}"


# 3️⃣ — RESCHEDULE
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
        if parsed < now:
            parsed = parsed.replace(year=now.year + 1)
        end = parsed + timedelta(minutes=duration)
        return reschedule_event(title, parsed.isoformat(), end.isoformat())
    except Exception as e:
        return f"❌ Error: {e}"


# 4️⃣ — CANCEL
def cancel(title: str) -> str:
    try:
        return cancel_event(title)
    except Exception as e:
        return f"❌ Error while cancelling event: {e}"


# 5️⃣ — SLOTS (List all)
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
        return response.strip()
    except Exception as e:
        return f"❌ Could not fetch calendar slots: {e}"


# 6️⃣ — FILTERED SLOTS
def check_slots(query: str) -> str:
    slots = get_filtered_slots(query)
    if not slots:
        return "❌ No matching events or slots found."
    return "\n".join([f"🗓️ {s['summary']} ({s['start']} → {s['end']})" for s in slots])


# 7️⃣ — TOOLS
calendar_tool = StructuredTool.from_function(
    func=book_appointment,
    name="book_appointment_tool",
    description="Book a meeting in Google Calendar. Requires title, date (e.g. 'tomorrow'), time (e.g. '3pm'), and duration in minutes.",
    args_schema=AppointmentInput
)

reschedule_tool = StructuredTool.from_function(
    func=reschedule,
    name="reschedule_event_tool",
    description="Reschedule a Google Calendar event. Requires title, new date, time, and duration.",
    args_schema=RescheduleInput
)

cancel_tool = StructuredTool.from_function(
    func=cancel,
    name="cancel_event_tool",
    description="Cancel a calendar event by its title.",
    args_schema=CancelInput
)

list_slots_tool = StructuredTool.from_function(
    func=list_available_slots,
    name="list_available_slots_tool",
    description="Get a list of all upcoming scheduled events in your calendar."
)

filter_slots_tool = StructuredTool.from_function(
    func=check_slots,
    name="check_availability_tool",
    description="Use natural language to check availability. E.g., 'slots today', 'after 3pm tomorrow', 'this week'.",
    args_schema=SlotQueryInput
)

# 8️⃣ — AGENT WITH MEMORY
llm = ChatOpenAI(model="gpt-4", temperature=0)

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

agent_executor = initialize_agent(
    tools=[
        calendar_tool,
        reschedule_tool,
        cancel_tool,
        list_slots_tool,
        filter_slots_tool
    ],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    handle_parsing_errors=True,
    memory=memory
)

def get_agent():
    return agent_executor
