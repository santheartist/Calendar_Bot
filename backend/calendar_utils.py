import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse
from dotenv import load_dotenv
import base64

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]

# Decode credentials and write to temp file
decoded_creds = base64.b64decode(os.environ["GOOGLE_CREDENTIALS_BASE64"])
with open("decoded_credentials.json", "wb") as f:
    f.write(decoded_creds)

SERVICE_ACCOUNT_FILE = "decoded_credentials.json"
CALENDAR_ID = os.getenv("CALENDAR_ID", "primary")

credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_FILE, scopes=SCOPES
)
service = build("calendar", "v3", credentials=credentials)

def get_available_slots():
    now = datetime.datetime.utcnow().isoformat() + "Z"
    events = (
        service.events()
        .list(
            calendarId=CALENDAR_ID,
            timeMin=now,
            maxResults=50,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
        .get("items", [])
    )
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "No Title"),
            "start": e["start"].get("dateTime"),
            "end": e["end"].get("dateTime"),
        }
        for e in events
        if "dateTime" in e["start"]
    ]

def get_free_slots():
    kolkata = ZoneInfo("Asia/Kolkata")
    now = datetime.datetime.now(kolkata)
    start_of_day = now.replace(hour=9, minute=0, second=0, microsecond=0)
    end_of_day = now.replace(hour=18, minute=0, second=0, microsecond=0)

    events = get_available_slots()
    busy = []
    for e in events:
        try:
            s = isoparse(e["start"]).astimezone(kolkata)
            e_ = isoparse(e["end"]).astimezone(kolkata)
            if s.date() == now.date():
                busy.append((s, e_))
        except:
            continue

    busy.sort()
    free = []
    cursor = start_of_day
    for s, e in busy:
        if s > cursor:
            free.append((cursor, s))
        cursor = max(cursor, e)
    if cursor < end_of_day:
        free.append((cursor, end_of_day))

    return [{"start": s.isoformat(), "end": e.isoformat()} for s, e in free]

def get_filtered_slots(natural_query: str) -> list:
    now = datetime.datetime.now(ZoneInfo("Asia/Kolkata"))
    base = {"PREFER_DATES_FROM": "future", "TIMEZONE": "Asia/Kolkata", "RELATIVE_BASE": now}

    if "today" in natural_query:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + datetime.timedelta(days=1)
    elif "tomorrow" in natural_query:
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) + datetime.timedelta(days=1)
        end = start + datetime.timedelta(days=1)
    elif "week" in natural_query:
        start = now
        end = now + datetime.timedelta(days=7)
    else:
        import dateparser
        parsed = dateparser.parse(natural_query, settings=base)
        if parsed:
            start = parsed
            end = parsed + datetime.timedelta(days=1)
        else:
            start = now
            end = now + datetime.timedelta(days=2)

    all_events = get_available_slots()
    slots = []
    for e in all_events:
        try:
            s = isoparse(e["start"]).astimezone(ZoneInfo("Asia/Kolkata"))
            e_ = isoparse(e["end"]).astimezone(ZoneInfo("Asia/Kolkata"))
            if start <= s <= end:
                slots.append({
                    "summary": e.get("summary", "No Title"),
                    "start": s.strftime("%b %d, %I:%M %p"),
                    "end": e_.strftime("%I:%M %p")
                })
        except:
            continue
    return slots

def has_conflict(start_iso, end_iso):
    kolkata = ZoneInfo("Asia/Kolkata")
    s0 = isoparse(start_iso).astimezone(kolkata)
    e0 = isoparse(end_iso).astimezone(kolkata)

    for ev in get_available_slots():
        try:
            s1 = isoparse(ev["start"]).astimezone(kolkata)
            e1 = isoparse(ev["end"]).astimezone(kolkata)
        except:
            continue
        if s0 < e1 and e0 > s1:
            return True
    return False

def create_event(summary, start_iso, end_iso, timezone="Asia/Kolkata"):
    if has_conflict(start_iso, end_iso):
        return "⚠️ Cannot book: conflicts detected."
    ev = {
        "summary": summary,
        "start": {"dateTime": start_iso, "timeZone": timezone},
        "end": {"dateTime": end_iso, "timeZone": timezone},
    }
    return (
        service.events()
        .insert(calendarId=CALENDAR_ID, body=ev)
        .execute()
        .get("htmlLink")
    )

def cancel_event(title):
    events = get_available_slots()
    for ev in events:
        if title.lower() in ev["summary"].lower():
            service.events().delete(calendarId=CALENDAR_ID, eventId=ev["id"]).execute()
            return f"🗑️ Event '{ev['summary']}' cancelled."
    return "❌ No matching event found to cancel."

def reschedule_event(title, new_start_iso, new_end_iso, timezone="Asia/Kolkata"):
    events = get_available_slots()
    for ev in events:
        if title.lower() in ev["summary"].lower():
            updated_event = {
                "start": {"dateTime": new_start_iso, "timeZone": timezone},
                "end": {"dateTime": new_end_iso, "timeZone": timezone},
            }
            result = (
                service.events()
                .patch(calendarId=CALENDAR_ID, eventId=ev["id"], body=updated_event)
                .execute()
            )
            return f"✅ Rescheduled: {result.get('htmlLink')}"
    return "❌ No matching event found to reschedule."
