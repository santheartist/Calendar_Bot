from langchain.agents import initialize_agent, AgentType
from langchain_openai import ChatOpenAI
from langchain.tools import StructuredTool
from pydantic import BaseModel
from calendar_utils import create_event, reschedule_event, cancel_event
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
    duration: int  # in minutes

class RescheduleInput(BaseModel):
    title: str
    new_date: str
    new_time: str
    duration: int  # in minutes

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
        start_dt = dateparser.parse(f"{date} {time}", settings=settings)
        if not start_dt:
            return "❌ Could not understand the date and time provided."
        if start_dt < now:
            start_dt = start_dt.replace(year=now.year + 1)

        end_dt = start_dt + timedelta(minutes=duration)
        return create_event(
            summary=title,
            start_iso=start_dt.isoformat(),
            end_iso=end_dt.isoformat(),
            timezone="Asia/Kolkata"
        )
    except Exception as e:
        return f"❌ Error while booking appointment: {e}"

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
        start_dt = dateparser.parse(f"{new_date} {new_time}", settings=settings)
        if not start_dt:
            return "❌ Could not parse the new date and time."
        if start_dt < now:
            start_dt = start_dt.replace(year=now.year + 1)

        end_dt = start_dt + timedelta(minutes=duration)
        return reschedule_event(
            title=title,
            new_start_iso=start_dt.isoformat(),
            new_end_iso=end_dt.isoformat(),
            timezone="Asia/Kolkata"
        )
    except Exception as e:
        return f"❌ Error while rescheduling: {e}"

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

# 🤖 Agent Setup
llm = ChatOpenAI(model="gpt-4", temperature=0)

agent_executor = initialize_agent(
    tools=[calendar_tool, reschedule_tool, cancel_tool],
    llm=llm,
    agent=AgentType.OPENAI_FUNCTIONS,
    verbose=True,
    handle_parsing_errors=True,
)

def get_agent():
    return agent_executor
