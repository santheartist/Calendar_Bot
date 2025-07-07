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

# --- Helper for parsing the LLM's 'key: "value", ...' string output ---
def parse_llm_tool_input_string(input_str: str) -> dict:
    """Parses a string like 'key: "value", key2: value2' into a dictionary."""
    parsed_dict = {}
    # Use regex to handle quoted strings and different value types more robustly
    parts = input_str.split(',')
    for part in parts:
        if ':' in part:
            key, value = part.split(':', 1)
            key = key.strip()
            value = value.strip()
            # Remove surrounding quotes if present
            if value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif value.startswith("'") and value.endswith("'"):
                value = value[1:-1]

            # Attempt to convert to int if it looks like a number
            if key == "duration":
                try:
                    parsed_dict[key] = int(value)
                except ValueError:
                    # Keep as string if conversion fails, Pydantic will catch if type is wrong
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
    description="Check Google Calendar for available slots using a natural language query. Input should be a string in 'key: \"value\"' format, e.g., 'query: \"meetings this week\"'.",
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
