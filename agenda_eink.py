"""
agenda_eink.py
Generates an 800x480 greyscale BMP daily agenda for e-ink displays,
pulling today's events from Google Calendar.

The image is rotated 90° giving an effective portrait canvas of 480x800,
which gives plenty of vertical space for a full day view.

Requirements:
    pip install Pillow requests google-auth-oauthlib google-auth-httplib2 google-api-python-client
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
# CONFIG
# ---------------------------------------------------------------------------

WIDTH, HEIGHT   = 800, 480          # physical BMP dimensions (landscape)
OUTPUT_PATH     = f"output/agenda_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.bmp"
FILE_PREFIX     = "agenda_"

CREDENTIALS     = "credentials.json"
TOKEN           = "token.json"
CALENDAR_IDS    = ["primary"]
SCOPES          = ["https://www.googleapis.com/auth/calendar.readonly"]

HOUR_START      = 7     # first hour shown
HOUR_END        = 22    # last hour shown (exclusive)

# After 90° rotation the canvas is effectively 480 wide × 800 tall
CANVAS_W        = HEIGHT   # 480
CANVAS_H        = WIDTH    # 800

# Greyscale palette
BG_FILL         = 255
HEADER_FILL     = 0
HOUR_LINE_FILL  = 20
HALF_LINE_FILL  = 40
EVENT_FILL      = 40
EVENT_TXT_FILL  = 255
ALL_DAY_FILL    = 140
ALL_DAY_TXT     = 255
TEXT_FILL       = 0
SUBTEXT_FILL    = 200
TIME_COL_FILL   = 60   # slightly off-white gutter for time labels

# ---------------------------------------------------------------------------
# FONT LOADER
# ---------------------------------------------------------------------------

def load_font(size, bold=True):
    bold_paths = [
        r"C:\Windows\Fonts\arialbd.ttf",
        r"C:\Windows\Fonts\calibrib.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ]
    regular_paths = [
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans.ttf",
    ]
    for path in (bold_paths if bold else regular_paths):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()

# ---------------------------------------------------------------------------
# GOOGLE CALENDAR
# ---------------------------------------------------------------------------

def get_google_service():
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


def fetch_today_events(service, today):
    import zoneinfo
    tz       = zoneinfo.ZoneInfo("America/Toronto")
    time_min = datetime.datetime.combine(today, datetime.time.min, tzinfo=tz).isoformat()
    time_max = datetime.datetime.combine(today, datetime.time.max, tzinfo=tz).isoformat()
    events = []
    for cal_id in CALENDAR_IDS:
        result = service.events().list(
            calendarId=cal_id,
            timeMin=time_min,
            timeMax=time_max,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        for item in result.get("items", []):
            title = item.get("summary", "(no title)")
            start = item["start"]
            end   = item["end"]
            if "dateTime" in start:
                start_dt = datetime.datetime.fromisoformat(start["dateTime"]).replace(tzinfo=None)
                end_dt   = datetime.datetime.fromisoformat(end["dateTime"]).replace(tzinfo=None)
                all_day  = False
            else:
                start_dt = datetime.datetime.fromisoformat(start["date"])
                end_dt   = datetime.datetime.fromisoformat(end["date"])
                all_day  = True
            events.append({"title": title, "start_dt": start_dt, "end_dt": end_dt, "all_day": all_day})
    return events

# ---------------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------------

def cx_text(draw, text, font, x, y, w, fill=0):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text((x + (w - tw) // 2, y), text, font=font, fill=fill)


def draw_event(draw, font_title, font_time, x0, y0, x1, y1, title, time_str):
    """Draw a filled event block with title and time."""
    draw.rectangle([x0, y0, x1, y1], fill=EVENT_FILL)
    pad = 5
    # Time string on first line
    if time_str:
        bb = draw.textbbox((0, 0), time_str, font=font_time)
        th = bb[3] - bb[1]
        if y1 - y0 > th + pad * 2:
            draw.text((x0 + pad, y0 + pad), time_str, font=font_time, fill=EVENT_TXT_FILL)
            ty = y0 + pad + th + 2
        else:
            ty = y0 + pad
    else:
        ty = y0 + pad
    # Title — truncate to fit width and height
    max_w = x1 - x0 - pad * 2
    label = title
    while label:
        bb = draw.textbbox((0, 0), label, font=font_title)
        if (bb[2] - bb[0]) <= max_w:
            break
        label = label[:-1]
    if label != title:
        label = label[:-2] + ".."
    if ty + 4 < y1:
        draw.text((x0 + pad, ty), label, font=font_title, fill=EVENT_TXT_FILL)

# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def generate_agenda(eink_host=None):
    if eink_host is None:
        eink_host = choose_network()

    today = datetime.date.today()

    print("Connecting to Google Calendar...")
    service = get_google_service()
    events  = fetch_today_events(service, today)
    print(f"Fetched {len(events)} event(s) for today.")

    # Separate all-day and timed events
    all_day_events = [e for e in events if e["all_day"]]
    timed_events   = [e for e in events if not e["all_day"]]

    # --- Fonts ---
    font_header     = load_font(28, bold=True)
    font_subheader  = load_font(17, bold=False)
    font_time_label = load_font(16, bold=False)
    font_event_time = load_font(12, bold=False)
    font_event_title= load_font(15, bold=True)
    font_allday     = load_font(14, bold=False)
    font_no_events  = load_font(18, bold=False)

    # --- Layout (working in portrait: 480 wide x 800 tall) ---
    W, H        = CANVAS_W, CANVAS_H
    HEADER_H    = 90
    ALL_DAY_H   = 30 * len(all_day_events) if all_day_events else 0
    TIME_COL_W  = 58    # left gutter for hour labels
    EVENT_PAD   = 2     # gap between event blocks and grid lines
    BODY_TOP    = HEADER_H + ALL_DAY_H
    BODY_H      = H - BODY_TOP
    HOUR_COUNT  = HOUR_END - HOUR_START
    ROW_H       = BODY_H / HOUR_COUNT

    img  = Image.new("L", (W, H), BG_FILL)
    draw = ImageDraw.Draw(img)

    # --- Header ---
    draw.rectangle([0, 0, W - 1, HEADER_H - 1], fill=HEADER_FILL)
    day_str  = today.strftime("%A")
    date_str = f"{today.strftime('%B')} {today.day}, {today.year}"
    cx_text(draw, day_str,  font_header,    0, 12, W, fill=255)
    cx_text(draw, date_str, font_subheader, 0, 52, W, fill=200)

    # --- All-day events strip ---
    if all_day_events:
        ay = HEADER_H
        for ev in all_day_events:
            draw.rectangle([0, ay, W - 1, ay + 28], fill=ALL_DAY_FILL)
            bb = draw.textbbox((0, 0), ev["title"], font=font_allday)
            tw = bb[2] - bb[0]
            draw.text(((W - tw) // 2, ay + 6), ev["title"], font=font_allday, fill=ALL_DAY_TXT)
            ay += 30
        draw.line([0, BODY_TOP, W - 1, BODY_TOP], fill=TEXT_FILL, width=2)

    # --- Time column background ---
    draw.rectangle([0, BODY_TOP, TIME_COL_W - 1, H - 1], fill=TIME_COL_FILL)
    draw.line([TIME_COL_W, BODY_TOP, TIME_COL_W, H - 1], fill=HOUR_LINE_FILL, width=1)

    # --- Hour grid lines + labels ---
    for h in range(HOUR_COUNT + 1):
        y = int(BODY_TOP + h * ROW_H)
        draw.line([TIME_COL_W, y, W - 1, y], fill=HOUR_LINE_FILL, width=1)
        if h < HOUR_COUNT:
            hour  = HOUR_START + h
            label = f"{hour:02d}:00"
            bb    = draw.textbbox((0, 0), label, font=font_time_label)
            th    = bb[3] - bb[1]
            draw.text((10, y + 4), label, font=font_time_label, fill=SUBTEXT_FILL)

    # Half-hour dashed lines
    for h in range(HOUR_COUNT):
        y = int(BODY_TOP + (h + 0.5) * ROW_H)
        for x in range(TIME_COL_W, W, 8):
            draw.line([x, y, x + 4, y], fill=HALF_LINE_FILL, width=1)
        

    # --- Timed events ---
    if not timed_events:
        # No events message
        cx_text(draw, "No events today", font_no_events,
                TIME_COL_W, BODY_TOP + BODY_H // 2 - 20,
                W - TIME_COL_W, fill=SUBTEXT_FILL)
    else:
        for ev in timed_events:
            start_h = ev["start_dt"].hour + ev["start_dt"].minute / 60
            end_h   = ev["end_dt"].hour   + ev["end_dt"].minute   / 60
            start_h = max(start_h, HOUR_START)
            end_h   = min(end_h,   HOUR_END)
            if end_h <= start_h:
                continue

            y0 = int(BODY_TOP + (start_h - HOUR_START) * ROW_H) + EVENT_PAD
            y1 = int(BODY_TOP + (end_h   - HOUR_START) * ROW_H) - EVENT_PAD
            x0 = TIME_COL_W + EVENT_PAD
            x1 = W - EVENT_PAD

            if y1 - y0 < 6:
                continue

            time_str = (f"{ev['start_dt'].strftime('%H:%M')}–"
                        f"{ev['end_dt'].strftime('%H:%M')}")
            draw_event(draw, font_event_title, font_event_time,
                       x0, y0, x1, y1, ev["title"], time_str)

    # --- save ---
    os.makedirs("output", exist_ok=True)
    img.save(OUTPUT_PATH, format="BMP")
    print(f"Saved: {os.path.abspath(OUTPUT_PATH)}")

    if EINK_UPLOAD:
        upload_to_eink(OUTPUT_PATH, eink_host)


def upload_to_eink(filepath, eink_host):
    import json as _json
    filename = os.path.basename(filepath)

    print(f"Clearing old {FILE_PREFIX}* files from {EINK_FOLDER} ...")
    try:
        existing = requests.get(f"{eink_host}/api/files?path={EINK_FOLDER}", timeout=10)
        if existing.status_code == 200:
            for f in existing.json():
                if f["name"].startswith(FILE_PREFIX):
                    path = f"{EINK_FOLDER}/{f['name']}"
                    requests.post(f"{eink_host}/delete",
                                  data={"paths": _json.dumps([path])},
                                  timeout=10)
                    print(f"Deleted {path}")
    except Exception as e:
        print(f"Could not clear old files (continuing anyway): {e}")

    url = f"{eink_host}/upload?path={EINK_FOLDER}"
    print(f"Uploading to {url} ...")
    try:
        with open(filepath, "rb") as f:
            response = requests.post(url, files={"file": (filename, f, "image/bmp")}, timeout=30)
        if response.status_code == 200:
            print(f"Uploaded successfully → {EINK_FOLDER}/{filename}")
        else:
            print(f"Upload failed: HTTP {response.status_code} — {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"Could not connect. Check {eink_host}.")
    except Exception as e:
        print(f"Upload error: {e}")


if __name__ == "__main__":
    generate_agenda()
