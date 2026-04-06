"""
calendar_eink.py
Generates an 800x480 greyscale BMP weekly calendar for e-ink displays,
pulling events from Google Calendar.

Requirements:
    pip install Pillow google-auth-oauthlib google-auth-httplib2 google-api-python-client

First-time setup:
    1. Place credentials.json (downloaded from Google Cloud Console) next to this script.
    2. Run the script — a browser window will open asking you to log in and grant access.
    3. A token.json file is saved automatically; future runs need no browser.

To auto-update on Windows, add a Task Scheduler job pointing to this script.
"""

import datetime
import os
import pickle
import requests

from PIL import Image, ImageDraw, ImageFont
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

from config import choose_network, EINK_FOLDER, EINK_UPLOAD


# ---------------------------------------------------------------------------
# CONFIG — edit these to customise the output
# ---------------------------------------------------------------------------

WIDTH, HEIGHT   = 800, 480
OUTPUT_PATH     = f"output/weekly_calendar_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.bmp"   # saved next to this script
CREDENTIALS     = "credentials.json"           # OAuth credentials from Google
TOKEN           = "token.json"                 # saved automatically after first login

# Which calendars to show. "primary" is your main calendar.
# Add more calendar IDs (find them in Google Calendar settings) to show multiple.
CALENDAR_IDS    = ["primary"]

HOUR_START      = 9     # first hour shown (24h)
HOUR_END        = 20    # last hour shown (exclusive)

WEEKEND_FILL    = 230   # 0=black, 255=white; 230 = light grey for Sat/Sun
TODAY_FILL      = 80    # dark grey highlight for today's column header
HEADER_FILL     = 0     # black header bar
DASH_FILL       = 160   # colour of the half-hour dashed lines
EVENT_FILL      = 40    # dark grey for event blocks
EVENT_TEXT_FILL = 255   # white text inside event blocks
EVENT_PADDING   = 3     # px padding inside each event box

# Read-only scope — the script never modifies your calendar
SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]


# ---------------------------------------------------------------------------
# FONT LOADER — tries several common font paths, falls back to PIL default
# ---------------------------------------------------------------------------

def load_font(size, bold=True):
    bold_paths = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    ]
    regular_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSans.ttf",
    ]
    for path in (bold_paths if bold else regular_paths):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


# ---------------------------------------------------------------------------
# GOOGLE CALENDAR AUTH & FETCH
# ---------------------------------------------------------------------------

def get_google_service():
    """Authenticate and return a Google Calendar API service object."""
    creds = None
    if os.path.exists(TOKEN):
        with open(TOKEN, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN, "wb") as f:
            pickle.dump(creds, f)

    return build("calendar", "v3", credentials=creds)


def fetch_events(service, week_start, week_end):
    """
    Fetch all events across CALENDAR_IDS for the given week.
    Returns a list of dicts: {title, start_dt, end_dt, all_day}
    """
    import zoneinfo
    tz       = zoneinfo.ZoneInfo("America/Toronto")
    time_min = datetime.datetime.combine(week_start, datetime.time.min, tzinfo=tz).isoformat()
    time_max = datetime.datetime.combine(week_end, datetime.time.max, tzinfo=tz).isoformat()

    events = []
    for cal_id in CALENDAR_IDS:
        result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,       # expand recurring events
            orderBy="startTime",
        ).execute()

        for item in result.get("items", []):
            title = item.get("summary", "(no title)")
            start = item["start"]
            end   = item["end"]

            # All-day events have a "date" key; timed events have "dateTime"
            if "dateTime" in start:
                start_dt = datetime.datetime.fromisoformat(start["dateTime"])
                end_dt   = datetime.datetime.fromisoformat(end["dateTime"])
                all_day  = False
            else:
                start_dt = datetime.datetime.fromisoformat(start["date"])
                end_dt   = datetime.datetime.fromisoformat(end["date"])
                all_day  = True

            events.append({
                "title":    title,
                "start_dt": start_dt,
                "end_dt":   end_dt,
                "all_day":  all_day,
            })

    return events


# ---------------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------------

def centered_text(draw, text, font, col_x, y, col_w, fill=0):
    """Draw text horizontally centred within a column."""
    bb     = draw.textbbox((0, 0), text, font=font)
    text_w = bb[2] - bb[0]
    draw.text((col_x + (col_w - text_w) // 2, y), text, font=font, fill=fill)


def draw_event_box(draw, font, x0, y0, x1, y1, title):
    """Draw a filled event rectangle with a clipped label."""
    draw.rectangle([x0, y0, x1, y1], fill=EVENT_FILL)
    tx    = x0 + EVENT_PADDING
    ty    = y0 + EVENT_PADDING
    max_w = x1 - x0 - EVENT_PADDING * 2
    # Truncate title with ".." if it doesn't fit
    label = title
    while label:
        bb = draw.textbbox((0, 0), label, font=font)
        if (bb[2] - bb[0]) <= max_w:
            break
        label = label[:-1]
    if label != title:
        label = label[:-2] + ".."
    draw.text((tx, ty), label, font=font, fill=EVENT_TEXT_FILL)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def generate_calendar(eink_host=None):
    # --- Network ---
    if eink_host is None:
        eink_host = choose_network()

    # --- Date logic ---
    today      = datetime.date.today()
    week_start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)  # Sunday
    week_end   = week_start + datetime.timedelta(days=6)                      # Saturday
    days       = [week_start + datetime.timedelta(days=i) for i in range(7)]
    month_name = today.strftime("%B %Y")

    # --- Google Calendar ---
    print("Connecting to Google Calendar...")
    service = get_google_service()
    events  = fetch_events(service, week_start, week_end)
    print(f"Fetched {len(events)} event(s).")

    # --- Fonts ---
    font_day   = load_font(13, bold=True)
    font_date  = load_font(28, bold=True)
    font_small = load_font(11, bold=False)
    font_event = load_font(10, bold=False)

    # --- Layout constants ---
    COL_COUNT = 7
    COL_W     = WIDTH // COL_COUNT
    HEADER_H  = 0

    # Size the day-name/date row dynamically so numbers are never clipped
    _tmp   = Image.new("L", (1, 1))
    _d     = ImageDraw.Draw(_tmp)
    date_h = _d.textbbox((0, 0), "30",  font=font_date)[3] - _d.textbbox((0, 0), "30",  font=font_date)[1]
    day_h  = _d.textbbox((0, 0), "Sun", font=font_day)[3]  - _d.textbbox((0, 0), "Sun", font=font_day)[1]
    DAY_ROW_H = 6 + day_h + 4 + date_h + 8

    BODY_TOP   = HEADER_H + DAY_ROW_H
    BODY_H     = HEIGHT - BODY_TOP
    HOUR_COUNT = HOUR_END - HOUR_START
    ROW_H      = BODY_H / HOUR_COUNT

    WEEKEND_INDICES = {0, 6}   # Sunday=0, Saturday=6

    # --- Canvas ---
    img  = Image.new("L", (WIDTH, HEIGHT), 255)
    draw = ImageDraw.Draw(img)

    # Weekend column backgrounds (drawn first, behind everything else)
    for i in range(COL_COUNT):
        if i in WEEKEND_INDICES:
            draw.rectangle(
                [i * COL_W, HEADER_H, (i + 1) * COL_W - 1, HEIGHT - 1],
                fill=WEEKEND_FILL,
            )

    # Day name + date number row
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for i, (name, d) in enumerate(zip(day_names, days)):
        x0       = i * COL_W
        is_today = (d == today)
        if is_today:
            draw.rectangle(
                [x0, HEADER_H, x0 + COL_W - 1, HEADER_H + DAY_ROW_H - 1],
                fill=TODAY_FILL,
            )
        fill   = 255 if is_today else 0
        y_name = HEADER_H + 6
        centered_text(draw, name,       font_day,  x0, y_name,             COL_W, fill=fill)
        centered_text(draw, str(d.day), font_date, x0, y_name + day_h + 4, COL_W, fill=fill)

    # Divider line under day row
    draw.line([0, BODY_TOP, WIDTH - 1, BODY_TOP], fill=0, width=2)

    # Horizontal hour lines
    for h in range(HOUR_COUNT + 1):
        y = int(BODY_TOP + h * ROW_H)
        draw.line([0, y, WIDTH - 1, y], fill=0, width=1)

    # Half-hour dashed lines
    for h in range(HOUR_COUNT):
        y = int(BODY_TOP + (h + 0.5) * ROW_H)
        for x in range(0, WIDTH, 6):
            draw.line([x, y, x + 3, y], fill=DASH_FILL, width=1)

    # Vertical column dividers
    for i in range(1, COL_COUNT):
        draw.line([i * COL_W, HEADER_H, i * COL_W, HEIGHT - 1], fill=0, width=1)

    # Hour labels
    for h in range(HOUR_COUNT):
        hour  = HOUR_START + h
        label = f"{hour:02d}:00"
        y     = int(BODY_TOP + h * ROW_H) + 2
        draw.text((3, y), label, font=font_small, fill=0)

    # --- Draw events ---
    for event in events:
        if event["all_day"]:
            continue   # all-day events have no time slot to place them in

        start_dt = event["start_dt"]
        end_dt   = event["end_dt"]

        # Strip timezone info for simple local comparison
        if start_dt.tzinfo is not None:
            start_dt = start_dt.replace(tzinfo=None)
        if end_dt.tzinfo is not None:
            end_dt = end_dt.replace(tzinfo=None)

        event_date = start_dt.date()

        # Which column?
        try:
            day_idx = days.index(event_date)
        except ValueError:
            continue   # event not in this week

        # Clamp to visible hour range
        start_hour = start_dt.hour + start_dt.minute / 60
        end_hour   = end_dt.hour   + end_dt.minute   / 60
        start_hour = max(start_hour, HOUR_START)
        end_hour   = min(end_hour,   HOUR_END)
        if end_hour <= start_hour:
            continue

        x0 = day_idx * COL_W + EVENT_PADDING
        x1 = (day_idx + 1) * COL_W - EVENT_PADDING
        y0 = int(BODY_TOP + (start_hour - HOUR_START) * ROW_H) + EVENT_PADDING
        y1 = int(BODY_TOP + (end_hour   - HOUR_START) * ROW_H) - EVENT_PADDING

        if y1 - y0 < 4:
            continue   # too small to draw meaningfully

        draw_event_box(draw, font_event, x0, y0, x1, y1, event["title"])

    # --- Save ---
    img = img.rotate(90, expand=True)
    os.makedirs("output", exist_ok=True)
    img.save(OUTPUT_PATH, format="BMP")
    print(f"Saved: {os.path.abspath(OUTPUT_PATH)}")

    # --- Upload to e-ink device ---
    if EINK_UPLOAD:
        upload_to_eink(OUTPUT_PATH, eink_host)


def upload_to_eink(filepath, eink_host):
    import json
    """Upload the BMP to the CrossPoint e-ink device via HTTP."""
    filename = os.path.basename(filepath)
    FILE_PREFIX = "weekly_calendar_"

    # Delete any existing files with this prefix
    print(f"Clearing old {FILE_PREFIX}* files from {EINK_FOLDER} ...")
    try:
        existing = requests.get(f"{eink_host}/api/files?path={EINK_FOLDER}", timeout=10)
        if existing.status_code == 200:
            for f in existing.json():
                if f["name"].startswith(FILE_PREFIX):
                    path = f"{EINK_FOLDER}/{f['name']}"
                    requests.post(f"{eink_host}/delete",
                                  data={"paths": json.dumps([path])},
                                  timeout=10)
                    print(f"Deleted {path}")
    except Exception as e:
        print(f"Could not clear old files (continuing anyway): {e}")

    url = f"{eink_host}/upload?path={EINK_FOLDER}"
    print(f"Uploading to {url} ...")
    try:
        with open(filepath, "rb") as f:
            response = requests.post(
                url,
                files={"file": (filename, f, "image/bmp")},
                timeout=30,
            )
        if response.status_code == 200:
            print(f"Uploaded successfully to {EINK_FOLDER}/{filename}")
        else:
            print(f"Upload failed: HTTP {response.status_code} — {response.text}")
    except requests.exceptions.ConnectionError:
        print("Could not connect to the e-ink device.")
        print(f"Make sure your laptop is on the right network and {eink_host} is correct.")
    except Exception as e:
        print(f"Upload error: {e}")


if __name__ == "__main__":
    generate_calendar()
