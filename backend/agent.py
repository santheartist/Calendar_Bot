from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.tools import StructuredTool
from langchain.memory import ConversationBufferMemory
from pydantic import BaseModel # <<< Already changed this in previous step
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
# from langchain.agents.openai_functions_agent.agent_token_buffer_memory import AgentTokenBufferMemory # REMOVE
# from langchain.agents.openai_functions_agent.base import OpenAIFunctionsAgent # REMOVE
from langchain.agents import AgentExecutor
from langchain_core.runnables.history import RunnableWithMessageHistory
from langchain_community.chat_message_histories import StreamlitChatMessageHistory

# NEW IMPORTS FOR REACT AGENT
from langchain.agents import create_react_agent
from langchain import hub
from langchain_core.prompts import PromptTemplate
from langchain_core.messages import SystemMessage, AIMessage, HumanMessage # Needed for message types in history

load_dotenv()

# ... (rest of your Schemas and Tool functions remain the same) ...

# 🛠️ Tool Wrappers (These remain the same)
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

# 🧠 Memory for the ReAct Agent (ConversationBufferMemory is simpler for ReAct)
# AgentTokenBufferMemory is often more coupled with OpenAI's function calling.
# Let's switch to a standard ConversationBufferMemory for ReAct.
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
# You can pull a prompt from LangChain Hub or define your own.
# A standard ReAct prompt includes:
# 1. System message/instructions for the AI
# 2. Tools description
# 3. Conversation history
# 4. User input
# 5. Scratchpad for thoughts/actions/observations

# Using a standard ReAct prompt from LangChain Hub
# Alternatively, you can define it like this:
# prompt_template = """Answer the following questions as best you can. You have access to the following tools:

# {tools}

# Use the following format:

# Question: the input question you must answer
# Thought: you should always think about what to do
# Action: the action to take, should be one of [{tool_names}]
# Action Input: the input to the action
# Observation: the result of the action
# ... (this Thought/Action/Action Input/Observation can repeat N times)
# Thought: I now know the final answer
# Final Answer: the final answer to the original input question

# Begin!

# {chat_history}
# Question: {input}
# Thought:{agent_scratchpad}
# """
# prompt = PromptTemplate.from_template(prompt_template)


# Using a more robust prompt from LangChain Hub
prompt = hub.pull("hwchase17/react-chat")
# Ensure the prompt uses the correct input variables
# The ReAct chat prompt from hub usually expects 'input', 'chat_history', 'agent_scratchpad', 'tools', 'tool_names'

# 🧩 Create the ReAct agent
agent = create_react_agent(llm, tools, prompt)

# 🔁 Full agent executor with memory + verbose logging
agent_executor = AgentExecutor(
    agent=agent,
    tools=tools, # Tools defined above
    memory=memory, # Standard memory
    verbose=True,
    handle_parsing_errors=True, # Keep this
)

# 🔁 Wrap with message history support
# Note: RunnableWithMessageHistory needs to correctly integrate with the new memory.
# StreamlitChatMessageHistory still provides the history.
# For ReAct, the history is usually just a list of messages.
# The `AgentExecutor` itself will manage the history from `memory`.
# `RunnableWithMessageHistory` will ensure `memory` is populated from `StreamlitChatMessageHistory`.
agent_with_history = RunnableWithMessageHistory(
    agent_executor,
    lambda session_id: StreamlitChatMessageHistory(key=session_id),
    input_messages_key="input",
    history_messages_key="chat_history", # Ensure this matches memory_key
)

# 🔌 Public getter
def get_agent():
    return agent_with_history
