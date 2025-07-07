from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import StructuredTool, Tool # Import Tool explicitly
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel, ValidationError # Import ValidationError
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
import re
# ⬇️ Agent core setup
from langchain.agents import AgentExecutor
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# NEW IMPORTS FOR REACT AGENT
from langchain.agents import create_react_agent
from langchain import hub
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage
import json # Ensure this is imported

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

# <--- NEW SCHEMA FOR FREE SLOTS TOOL INPUT ---
class FreeSlotsInput(BaseModel):
    date: str
    start_time: Optional[str] = "09:00 AM" # Optional, default
    end_time: Optional[str] = "05:00 PM"   # Optional, default
    min_duration: Optional[int] = 30       # Optional, default
    
# --- Helper for parsing the LLM's 'key: "value", ...' string output ---
def parse_llm_tool_input_string(input_str: str) -> dict:
    """Parses a string like 'key: "value", key2: value2' into a dictionary,
    robustly handling outer quotes and ensuring clean keys/values."""
    parsed_dict = {}
    
    # 1. First, strip any leading/trailing quotes (single or double) from the entire string
    # This addresses cases where LLM wraps the whole Action Input in quotes
    input_str = input_str.strip()
    if (input_str.startswith("'") and input_str.endswith("'")) or \
       (input_str.startswith('"') and input_str.endswith('"')):
        input_str = input_str[1:-1]
    
    # 2. Use regex to split based on comma, but not if the comma is inside quotes.
    # This is a common pattern for splitting comma-separated key-value pairs
    # while respecting quoted strings.
    # Pattern: Matches one or more characters that are not a comma,
    # or a sequence enclosed in double quotes (which can contain commas),
    # or a sequence enclosed in single quotes (which can contain commas).
    # Then it splits by comma followed by optional spaces.
    parts = re.findall(r'([^,]+(?:,"[^"]*"|,\'[^\']*\')?)*', input_str)
    
    # Clean up empty strings from re.findall if any
    parts = [p.strip() for p in parts if p.strip()]

    for part in parts:
        # Each part should now be 'key: value'
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip()
            value = value.strip()

            # Remove surrounding quotes from the value itself if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]
            
            # Remove any leading/trailing quotes from the key as well (like if LLM outputs 'title': "...")
            if key.startswith("'") and key.endswith("'"):
                key = key[1:-1]
            elif key.startswith('"') and key.endswith('"'):
                key = key[1:-1]

            # Attempt to convert duration to int specifically
            if key == "duration":
                try:
                    parsed_dict[key] = int(value)
                except ValueError:
                    # If conversion fails, keep as string and let Pydantic handle the error
                    parsed_dict[key] = value
            else:
                parsed_dict[key] = value
    return parsed_dict


# ✅ Book Appointment
def book_appointment(tool_input: str) -> str:
    try:
        parsed_args = parse_llm_tool_input_string(tool_input)
        
        # Validate with Pydantic BaseModel to ensure all fields are present and correct types
        validated_input = AppointmentInput(**parsed_args)

        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        settings = {
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": now,
        }
        parsed = dateparser.parse(f"{validated_input.date} {validated_input.time}", settings=settings)
        if not parsed:
            return "❌ Could not parse date/time. Please specify a clearer date and time."
        
        # Adjust year if the parsed date is in the past, assuming future intent
        if parsed < now and parsed.year == now.year:
            parsed = parsed.replace(year=now.year + 1)
        elif parsed < now and parsed.year < now.year: # If it's in a past year
            parsed = parsed.replace(year=now.year) # Try current year first
            if parsed < now: # If still in past, try next year
                parsed = parsed.replace(year=now.year + 1)


        end = parsed + timedelta(minutes=validated_input.duration)
        
        event_link = create_event(
            summary=validated_input.title,
            start_iso=parsed.isoformat(),
            end_iso=end.isoformat(),
            timezone="Asia/Kolkata"
        )
        return event_link if event_link else "❌ Failed to create event and retrieve link."
    except ValidationError as e:
        # Pydantic validation errors are caught specifically here
        return f"❌ Missing or invalid arguments for booking. Please provide title, date, time, and duration clearly. Details: {e}"
    except Exception as e:
        return f"❌ Error during booking: {e}"

# 🔁 Reschedule Appointment
def reschedule(tool_input: str) -> str:
    try:
        parsed_args = parse_llm_tool_input_string(tool_input)
        validated_input = RescheduleInput(**parsed_args)
        
        now = datetime.now(ZoneInfo("Asia/Kolkata"))
        settings = {
            "PREFER_DATES_FROM": "future",
            "TIMEZONE": "Asia/Kolkata",
            "RETURN_AS_TIMEZONE_AWARE": True,
            "RELATIVE_BASE": now,
        }
        parsed = dateparser.parse(f"{validated_input.new_date} {validated_input.new_time}", settings=settings)
        if not parsed:
            return "❌ Could not parse new date/time. Please specify a clearer date and time."
        
        if parsed < now and parsed.year == now.year:
            parsed = parsed.replace(year=now.year + 1)
        elif parsed < now and parsed.year < now.year:
            parsed = parsed.replace(year=now.year)
            if parsed < now:
                parsed = parsed.replace(year=now.year + 1)

        end = parsed + timedelta(minutes=validated_input.duration)
        reschedule_result = reschedule_event(validated_input.title, parsed.isoformat(), end.isoformat())
        return reschedule_result if reschedule_result else "❌ Failed to reschedule event."
    except ValidationError as e:
        return f"❌ Missing or invalid arguments for rescheduling. Please provide title, new date, new time, and duration clearly. Details: {e}"
    except Exception as e:
        return f"❌ Error during rescheduling: {e}"

# ❌ Cancel Appointment
def cancel(tool_input: str) -> str:
    try:
        parsed_args = parse_llm_tool_input_string(tool_input)
        validated_input = CancelInput(**parsed_args)
        
        cancel_result = cancel_event(validated_input.title)
        return cancel_result if cancel_result else "❌ Failed to cancel event."
    except ValidationError as e:
        return f"❌ Missing or invalid argument for cancelling. Please provide the event title clearly. Details: {e}"
    except Exception as e:
        return f"❌ Error while cancelling event: {e}"

# 📅 List All Upcoming Events (no input needed for this one)
def list_available_slots() -> str:
    try:
        events = get_available_slots()
        if not events:
            return "🎉 You have no scheduled events — your calendar is wide open today!"
        response = "📅 Here are your upcoming events:\n"
        for ev in events:
            # Current time is Monday, July 7, 2025 at 3:54:33 PM IST.
            # Formatting event times for display, ensuring correct timezone handling
            start_dt = datetime.fromisoformat(ev["start"]).astimezone(ZoneInfo("Asia/Kolkata"))
            end_dt = datetime.fromisoformat(ev["end"]).astimezone(ZoneInfo("Asia/Kolkata"))
            
            start_str = start_dt.strftime("%b %d, %Y %I:%M %p") # Include year for clarity
            end_str = end_dt.strftime("%I:%M %p")
            
            response += f"• {ev['summary']}: {start_str} → {end_str}\n"
        return response.strip() if response.strip() else "❌ No events found or error formatting list."
    except Exception as e:
        return f"❌ Could not fetch calendar slots: {e}"

# 🔍 Natural Language Slot Query
def check_slots(tool_input: str) -> str:
    try:
        parsed_args = parse_llm_tool_input_string(tool_input)
        validated_input = SlotQueryInput(**parsed_args)
        
        slots = get_filtered_slots(validated_input.query)
        if not slots:
            return "❌ No matching events or slots found for your query."
        return "\n".join([f"🗓️ {s['summary']} ({s['start']} → {s['end']})" for s in slots])
    except ValidationError as e:
        return f"❌ Missing or invalid argument for checking slots. Please provide a clear query. Details: {e}"
    except Exception as e:
        return f"❌ Error during slot check: {e}"
        
# --- NEW FUNCTION FOR FREE SLOTS TOOL ---
def get_free_slots_tool_func(tool_input: str) -> str:
    try:
        parsed_args = parse_llm_tool_input_string(tool_input)
        # Use default values if not provided in parsed_args
        validated_input = FreeSlotsInput(
            date=parsed_args.get("date"),
            start_time=parsed_args.get("start_time", "09:00 AM"),
            end_time=parsed_args.get("end_time", "05:00 PM"),
            min_duration=parsed_args.get("min_duration", 30)
        )
        
        # Convert duration string to int if it came as a string from parsing
        if isinstance(validated_input.min_duration, str):
            try:
                validated_input.min_duration = int(validated_input.min_duration)
            except ValueError:
                return "❌ Error: Minimum duration must be a valid number of minutes."

        free_slots = calculate_free_slots(
            date_str=validated_input.date,
            start_time_str=validated_input.start_time,
            end_time_str=validated_input.end_time,
            min_duration_minutes=validated_input.min_duration
        )
        if "error" in free_slots[0] if free_slots else []:
             return f"❌ Error calculating free slots: {free_slots[0]['error']}"

        if not free_slots:
            return "🎉 No free slots found for the requested time period on that date."
        
        response_str = f"✅ Here are your free slots on {validated_input.date}:\n"
        for slot in free_slots:
            response_str += f"- From {slot['start']} to {slot['end']} ({slot['duration']})\n"
        return response_str
    except ValidationError as e:
        return f"❌ Missing or invalid arguments for finding free slots. Please provide a date. Optionally, you can specify start_time, end_time, and min_duration (in minutes). Details: {e}"
    except Exception as e:
        return f"❌ An unexpected error occurred while finding free slots: {e}"

# --- NEW TOOL WRAPPER ---
free_slots_tool = Tool(
    func=get_free_slots_tool_func,
    name="get_free_slots_tool",
    description="Calculate and list free time slots in the calendar for a given date, considering a working day (default 9 AM to 5 PM) and minimum duration (default 30 minutes). Input should be a string in 'key: \"value\", ...' format, e.g., 'date: \"tomorrow\"' or 'date: \"July 9th\", start_time: \"10am\", end_time: \"6pm\", min_duration: 60'.",
)


# 🛠️ Tool Wrappers - Using `Tool` for functions that parse string input
# and `StructuredTool` for functions that directly expect keyword arguments (like list_available_slots)

calendar_tool = Tool(
    name="book_appointment_tool",
    func=book_appointment,
    description="Book a meeting in Google Calendar using title, date, time, and duration. Input should be a string in 'key: \"value\", key2: value2' format, e.g., 'title: \"Meeting with Alice\", date: \"tomorrow\", time: \"10:00\", duration: 30'. Assumes Asia/Kolkata timezone.",
)

reschedule_tool = Tool(
    func=reschedule,
    name="reschedule_event_tool",
    description="Reschedule a Google Calendar event by title. Provide new date, time, and duration. Input should be a string in 'key: \"value\", key2: value2' format, e.g., 'title: \"Standup\", new_date: \"Friday\", new_time: \"3pm\", duration: 30'.",
)

cancel_tool = Tool(
    func=cancel,
    name="cancel_event_tool",
    description="Cancel a Google Calendar event by title. Input should be a string in 'key: \"value\"' format, e.g., 'title: \"My Meeting\"'.",
)

# This tool doesn't take specific input from the LLM, so StructuredTool is fine here.
list_slots_tool = StructuredTool.from_function(
    func=list_available_slots,
    name="list_available_slots_tool",
    description="Use this to list all upcoming calendar events.",
)

filter_slots_tool = Tool(
    func=check_slots,
    name="check_availability_tool",
    description="Check Google Calendar for *specific events* matching a natural language query like 'meetings this week' or 'events after 2pm'. Input should be a string in 'key: \"value\"' format, e.g., 'query: \"meetings this week\"'. Use 'get_free_slots_tool' for finding free time.",
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
    filter_slots_tool,
    free_slots_tool,
]

# Create a prompt for the ReAct agent
# Ensure the prompt is loaded correctly; hub.pull can be a network call.
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
    max_iterations=25,  # Increased from default (often 15). Adjust as needed.
    max_execution_time=90,
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
