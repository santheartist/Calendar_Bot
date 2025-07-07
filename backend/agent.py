from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel
from calendar_utils import create_event, reschedule_event, cancel_event, get_available_slots, get_filtered_slots, get_free_slots
from datetime import timedelta, datetime
from zoneinfo import ZoneInfo
import dateparser
from dotenv import load_dotenv
import os

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

class SlotQueryInput(BaseModel):
    query: str

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

# 📅 List All Free Time Slots
def list_available_slots() -> str:
    try:
        slots = get_free_slots()
        if not slots:
            return "😕 No free slots available today."
        response = "🕐 Here are your available slots for today:\n"
        for slot in slots:
            start = datetime.fromisoformat(slot["start"]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
            end = datetime.fromisoformat(slot["end"]).astimezone(ZoneInfo("Asia/Kolkata")).strftime("%I:%M %p")
            response += f"• {start} → {end}\n"
        return response.strip()
    except Exception as e:
        return f"❌ Could not fetch available slots: {e}"

# 🔍 Natural Language Slot Query Tool
def check_slots(query: str) -> str:
    slots = get_filtered_slots(query)
    if not slots:
        return "❌ No matching events or slots found."
    return "\n".join([f"🗓️ {s['summary']} ({s['start']} → {s['end']})" for s in slots])

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

list_slots_tool = StructuredTool.from_function(
    func=list_available_slots,
    name="list_available_slots_tool",
    description="Use this to list free time slots today.",
)

filter_slots_tool = StructuredTool.from_function(
    func=check_slots,
    name="check_availability_tool",
    description="Check Google Calendar for available slots using a natural language query like 'slots today', 'meetings this week', or 'free after 2pm'.",
    args_schema=SlotQueryInput
)

# 🤖 Agent Setup with memory
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
