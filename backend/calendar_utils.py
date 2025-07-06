import os
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from zoneinfo import ZoneInfo
from dateutil.parser import isoparse
from dotenv import load_dotenv

load_dotenv()

SCOPES = ["https://www.googleapis.com/auth/calendar"]
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_CREDENTIALS_PATH", "backend/credentials.json")
CALENDAR_ID = os.getenv("CALENDAR_ID")

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
            maxResults=10,
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

def has_conflict(start_iso, end_iso):
    kolkata = ZoneInfo("Asia/Kolkata")
    s0 = isoparse(start_iso).astimezone(kolkata)
    e0 = isoparse(end_iso).astimezone(kolkata)

    for ev in get_available_slots():
        try:
            s1 = isoparse(ev["start"]).astimezone(kolkata)
            e1 = isoparse(ev["end"]).astimezone(kolkata)
        except Exception:
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
