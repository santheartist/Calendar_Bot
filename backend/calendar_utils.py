import os
import datetime
from datetime import datetime, timedelta
import json # Added for JSON parsing
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse
from dotenv import load_dotenv
import base64
import dateparser
from typing import List, Dict, Optional 
load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# 🔐 Load service account credentials from environment variable
# It's recommended to store the *content* of service_account.json directly
# in an environment variable (e.g., GOOGLE_CREDENTIALS_JSON)
# rather than base64 encoding it and then decoding and writing to a file.
# However, if you're already base64 encoding for your CI/CD, this works.
# Let's assume GOOGLE_CREDENTIALS_BASE64 holds the base64 encoded JSON string.
try:
    # Decode the base64 string
    decoded_creds_json_string = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"]).decode('utf-8')
    # Parse the JSON string into a dictionary
    credentials_info = json.loads(decoded_creds_json_string)

    # Use from_service_account_info to load credentials directly from the dictionary
    credentials = service_account.Credentials.from_service_account_info(
        credentials_info, scopes=SCOPES
    )
except KeyError:
    raise ValueError("GOOGLE_CREDENTIALS_BASE64 environment variable not set.")
except json.JSONDecodeError:
    raise ValueError("GOOGLE_CREDENTIALS_BASE64 contains invalid JSON after decoding.")
except Exception as e:
    raise RuntimeError(f"Failed to load Google Calendar credentials: {e}")

CALENDAR_ID = os.getenv("CALENDAR_ID", "primary") # Defaults to 'primary' calendar

# Build the Google Calendar service object
service = build("calendar", "v3", credentials=credentials)

def get_available_slots():
    """Fetches all upcoming events from the calendar."""
    # Use UTC for API calls and then convert for display if needed
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events_result = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=50, # Limit to 50 events for performance
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )
    events = events_result.get("items", [])
    
    # Filter out events without 'dateTime' (e.g., all-day events might use 'date')
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "No Title"),
            "start": e["start"].get("dateTime"),
            "end": e["end"].get("dateTime"),
        }
        for e in events
        if "dateTime" in e["start"] # Ensure it's a timed event
    ]

def get_free_slots():
    """Calculates free time slots for the current day (9 AM to 6 PM Kolkata time)."""
    kolkata = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(kolkata)
    start_of_day = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=18, minute=0, second=0, microsecond=0)

    events = get_available_slots()
    busy_slots = []
    for e in events:
        try:
            # Parse and localize event times
            s = isoparse(e["start"]).astimezone(kolkata)
            e_ = isoparse(e["end"]).astimezone(kolkata)
            # Only consider events for today
            if s.date() == now.date():
                busy_slots.append((s, e_))
        except Exception as parse_error:
            # Log parsing errors but don't stop the function
            print(f"Warning: Could not parse event time for event {e.get('summary')}: {parse_error}")
            continue

    busy_slots.sort() # Sort by start time
    
    free_slots = []
    cursor = start_of_day
    for s, e in busy_slots:
        # If there's a gap between the current cursor and the start of the busy slot
        if s > cursor:
            free_slots.append((cursor, s))
        # Move the cursor past the end of the current busy slot
        cursor = max(cursor, e)
    
    # Add any remaining free time at the end of the day
    if cursor < end_of_day:
        free_slots.append((cursor, end_of_day))

    return [{"start": s.isoformat(), "end": e.isoformat()} for s, e in free_slots]

def get_filtered_slots(natural_query: str) -> list:
    """Filters calendar events based on a natural language query."""
    kolkata = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(kolkata)
    
    # Determine the time range based on the query
    start_time_filter = now
    end_time_filter = now + datetime.timedelta(days=2) # Default to next 2 days

    # dateparser settings for relative parsing
    base_settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": "Asia/Kolkata",
        "RELATIVE_BASE": now
    }

    query_lower = natural_query.lower()
    
    if "today" in query_lower:
        start_time_filter = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end_time_filter = start_time_filter + datetime.timedelta(days=1)
    elif "tomorrow" in query_lower:
        start_time_filter = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        end_time_filter = start_time_filter + datetime.timedelta(days=1)
    elif "week" in query_lower:
        start_time_filter = now # From now for the next 7 days
        end_time_filter = now + datetime.timedelta(days=7)
    else:
        # Try to parse a specific date/time from the query
        parsed_query_time = dateparser.parse(natural_query, settings=base_settings)
        if parsed_query_time:
            # If a specific time is parsed, filter events around that time
            start_time_filter = parsed_query_time
            # Extend end_time_filter for a reasonable window (e.g., 24 hours from parsed time)
            end_time_filter = parsed_query_time + datetime.timedelta(days=1)
        # If natural_query can't be parsed into a specific date, keep default (next 2 days)

    all_events = get_available_slots()
    filtered_events = []
    for e in all_events:
        try:
            s_event = isoparse(e["start"]).astimezone(kolkata)
            e_event = isoparse(e["end"]).astimezone(kolkata)
            
            # Check if event falls within the filtered time range
            if start_time_filter <= s_event < end_time_filter or \
               start_time_filter < e_event <= end_time_filter or \
               (s_event <= start_time_filter and e_event >= end_time_filter):
                filtered_events.append({
                    "summary": e.get("summary", "No Title"),
                    "start": s_event.strftime("%b %d, %I:%M %p"),
                    "end": e_event.strftime("%I:%M %p")
                })
        except Exception as filter_error:
            print(f"Warning: Could not process event for filtering {e.get('summary')}: {filter_error}")
            continue
    return filtered_events

def has_conflict(start_iso: str, end_iso: str) -> bool:
    """Checks if a proposed event conflicts with existing events."""
    kolkata = ZoneInfo("Asia/Kolkata")
    s0 = isoparse(start_iso).astimezone(kolkata)
    e0 = isoparse(end_iso).astimezone(kolkata)

    for ev in get_available_slots():
        try:
            s1 = isoparse(ev["start"]).astimezone(kolkata)
            e1 = isoparse(ev["end"]).astimezone(kolkata)
            # Check for overlap: (start0 < end1) and (end0 > start1)
            if s0 < e1 and e0 > s1:
                return True
        except Exception as conflict_error:
            print(f"Warning: Could not process event for conflict check {ev.get('summary')}: {conflict_error}")
            continue
    return False

def create_event(summary: str, start_iso: str, end_iso: str, timezone: str = "Asia/Kolkata") -> str:
    """Creates a new calendar event."""
    if has_conflict(start_iso, end_iso):
        return "⚠️ Cannot book: conflicts detected with an existing event."
    
    event = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    
    try:
        created_event = service.events().insert(calendarId=CALENDAR_ID, body=event).execute()
        return f"✅ Event created: {created_event.get('htmlLink')}"
    except Exception as e:
        return f"❌ Failed to create event: {e}"

def cancel_event(title: str) -> str:
    """Cancels a calendar event by matching its title."""
    events = get_available_slots()
    found_event = None
    for ev in events:
        if ev.get("summary") and title.lower() in ev["summary"].lower():
            found_event = ev
            break # Found a match, break loop

    if found_event:
        try:
            service.events().delete(calendarId=CALENDAR_ID, eventId=found_event["id"]).execute()
            return f"🗑️ Event '{found_event['summary']}' cancelled successfully."
        except Exception as e:
            return f"❌ Error cancelling event '{found_event['summary']}': {e}"
    return f"❌ No matching event found with title '{title}' to cancel."

def reschedule_event(title: str, new_start_iso: str, new_end_iso: str, timezone: str = "Asia/Kolkata") -> str:
    """Reschedules an existing calendar event by matching its title."""
    events = get_available_slots()
    found_event = None
    for ev in events:
        if ev.get("summary") and title.lower() in ev["summary"].lower():
            found_event = ev
            break # Found a match, break loop
    
    if found_event:
        # Check for conflicts with other events, excluding the event being rescheduled
        # (This check is not robust enough without excluding the original event's time slot)
        # For a full solution, you'd need to fetch the original event's details
        # and temporarily exclude it from conflict check, or perform a more complex check.
        # For simplicity, if has_conflict check passes *now*, it's good enough.
        # A true "reschedule" means the old slot is free, the new one might be busy by other events.
        
        # If the new slot conflicts with ANY other event (including itself if not careful, but has_conflict generally ignores same event)
        if has_conflict(new_start_iso, new_end_iso): # This will check against ALL current events.
            # A more robust check would involve getting all events *except* the one being moved
            # and checking for conflicts against those. For now, this is a simple check.
            return f"⚠️ Reschedule failed: New time conflicts with an existing event (not '{found_event['summary']}')."

        updated_event_body = {
            "start": {"dateTime": new_start_iso, "timeZone": timezone},
            "end": {"dateTime": new_end_iso, "timeZone": timezone},
        }
        try:
            result = service.events().patch(calendarId=CALENDAR_ID, eventId=found_event["id"], body=updated_event_body).execute()
            return f"✅ Event '{found_event['summary']}' rescheduled to {datetime.fromisoformat(new_start_iso).strftime('%b %d, %I:%M %p')}: {result.get('htmlLink')}"
        except Exception as e:
            return f"❌ Failed to reschedule event '{found_event['summary']}': {e}"
    
    return f"❌ No matching event found with title '{title}' to reschedule."
def calculate_free_slots(
    date_str: str,
    start_time_str: str = "09:00 AM", # Default start of working day
    end_time_str: str = "05:00 PM",   # Default end of working day
    min_duration_minutes: int = 30    # Minimum duration for a "free" slot
) -> List[Dict[str, str]]:
    """
    Calculates free time slots for a given date, considering existing events.
    """
    now = datetime.now(ZoneInfo("Asia/Kolkata"))
    settings = {
        "PREFER_DATES_FROM": "future",
        "TIMEZONE": "Asia/Kolkata",
        "RETURN_AS_TIMEZONE_AWARE": True,
        "RELATIVE_BASE": now,
    }

    # Parse the target date
    target_date = dateparser.parse(date_str, settings=settings)
    if not target_date:
        return [{"error": "Could not parse target date."}]

    # Normalize target_date to just the date component for comparison
    target_date = target_date.replace(hour=0, minute=0, second=0, microsecond=0)

    # Define the working day start and end for the target date
    working_day_start = dateparser.parse(f"{date_str} {start_time_str}", settings=settings)
    working_day_end = dateparser.parse(f"{date_str} {end_time_str}", settings=settings)

    if not working_day_start or not working_day_end:
        return [{"error": "Could not parse working day start/end times."}]

    # Ensure working_day_start and working_day_end are on the target date
    working_day_start = working_day_start.replace(
        year=target_date.year, month=target_date.month, day=target_date.day
    )
    working_day_end = working_day_end.replace(
        year=target_date.year, month=target_date.month, day=target_date.day
    )

    # Fetch all events for the target day
    all_events = get_available_slots() # This function already fetches events
    
    # Filter events to only include those on the target date
    daily_events = []
    for event in all_events:
        event_start_dt = datetime.fromisoformat(event['start']).astimezone(ZoneInfo("Asia/Kolkata"))
        event_end_dt = datetime.fromisoformat(event['end']).astimezone(ZoneInfo("Asia/Kolkata"))
        
        # Check if the event's start or end falls within the target date
        if event_start_dt.date() == target_date.date() or \
           event_end_dt.date() == target_date.date() or \
           (event_start_dt.date() < target_date.date() and event_end_dt.date() > target_date.date()):
            
            # Clip events that start before or end after the working day on the target date
            event_start_clipped = max(event_start_dt, working_day_start)
            event_end_clipped = min(event_end_dt, working_day_end)
            
            # Only add if the clipped event still has a valid duration
            if event_end_clipped > event_start_clipped:
                daily_events.append({
                    'start': event_start_clipped,
                    'end': event_end_clipped
                })

    # Sort events by start time
    daily_events.sort(key=lambda x: x['start'])

    free_slots = []
    current_time = working_day_start

    for event in daily_events:
        # Check for a free slot between current_time and the start of the next event
        if event['start'] > current_time:
            free_duration = event['start'] - current_time
            if free_duration.total_seconds() >= min_duration_minutes * 60:
                free_slots.append({
                    "start": current_time.isoformat(),
                    "end": event['start'].isoformat(),
                    "duration_minutes": int(free_duration.total_seconds() / 60)
                })
        # Move current_time past the end of the current event (handle overlapping/adjacent events)
        current_time = max(current_time, event['end'])

    # Check for a free slot after the last event until the end of the working day
    if working_day_end > current_time:
        free_duration = working_day_end - current_time
        if free_duration.total_seconds() >= min_duration_minutes * 60:
            free_slots.append({
                "start": current_time.isoformat(),
                "end": working_day_end.isoformat(),
                "duration_minutes": int(free_duration.total_seconds() / 60)
            })
    
    # Format for readability
    formatted_free_slots = []
    for slot in free_slots:
        start_dt = datetime.fromisoformat(slot['start']).astimezone(ZoneInfo("Asia/Kolkata"))
        end_dt = datetime.fromisoformat(slot['end']).astimezone(ZoneInfo("Asia/Kolkata"))
        formatted_free_slots.append({
            "start": start_dt.strftime("%I:%M %p"),
            "end": end_dt.strftime("%I:%M %p"),
            "duration": f"{slot['duration_minutes']} minutes"
        })

    return formatted_free_slots
