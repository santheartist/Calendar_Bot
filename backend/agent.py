from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel
from calendar_utils import create_event, reschedule_event, cancel_event
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import dateparser
from dotenv import load_dotenv
import os
from calendar_utils import get_available_slots
load_dotenv()

# 📌 Schemas
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

# ✅ Book Appointment
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
        return create_event(
            summary=title,
            start_iso=parsed.isoformat(),
            end_iso=end.isoformat(),
            timezone="Asia/Kolkata"
        )
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
        return reschedule_event(title, parsed.isoformat(), end.isoformat())
    except Exception as e:
        return f"❌ Error: {e}"

# ❌ Cancel Appointment
def cancel(title: str) -> str:
    try:
        return cancel_event(title)
    except Exception as e:
        return f"❌ Error while cancelling event: {e}"

# 🛠️ Tool Wrappers
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

# 🤖 Agent Setup with memory
llm = ChatOpenAI(model="gpt-4", temperature=0)

memory = ConversationBufferMemory(
    memory_key="chat_history",
    return_messages=True
)

agent_executor = initialize_agent(
    tools=[calendar_tool, reschedule_tool, cancel_tool],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    memory=memory,
    verbose=True,
    handle_parsing_errors=True,
)
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

slots_tool = StructuredTool.from_function(
    func=list_available_slots,
    name="list_available_slots_tool",
    description="Use this to list today's upcoming calendar events.",
)
def get_agent():
    return agent_executor
