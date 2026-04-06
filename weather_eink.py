"""
weather_eink.py
Generates an 800x480 greyscale BMP 4-day weather forecast for e-ink displays,
pulling data from Open-Meteo (no API key required).

Requirements:
    pip install Pillow requests

"""

import datetime
import json
import os
import requests

from PIL import Image, ImageDraw, ImageFont

from config import choose_network, EINK_FOLDER, EINK_UPLOAD

# ---------------------------------------------------------------------------
# CONFIG — edit these to customise the output
# ---------------------------------------------------------------------------

WIDTH, HEIGHT   = 800, 480
OUTPUT_PATH     = f"output/weather_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.bmp"

LATITUDE        = 11.1111      
LONGITUDE       = 11.1111
TIMEZONE        = "America/New_York"
FORECAST_DAYS   = 4

# CrossPoint e-ink device upload settings

FILE_PREFIX     = "weather_"               # only files with this prefix are deleted on upload

# Greyscale palette
BG_FILL         = 255   # white background
HEADER_FILL     = 0     # black header
CARD_FILL       = 255   # very light grey card background
CARD_TODAY_FILL = 255   # slightly darker for today
DIVIDER_FILL    = 20   # grey dividers
ICON_FILL       = 0     # black icons
TEXT_FILL       = 0     # black text
SUBTEXT_FILL    = 20   # mid-grey for secondary text


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
# OPEN-METEO FETCH
# ---------------------------------------------------------------------------

# WMO weather code -> (label, condition_key)
# condition_key drives which icon to draw
WMO_CODES = {
    0:  ("Clear",          "sun"),
    1:  ("Mostly Clear",   "sun"),
    2:  ("Partly Cloudy",  "partly_cloudy"),
    3:  ("Overcast",       "cloud"),
    45: ("Foggy",          "cloud"),
    48: ("Icy Fog",        "cloud"),
    51: ("Light Drizzle",  "rain"),
    53: ("Drizzle",        "rain"),
    55: ("Heavy Drizzle",  "rain"),
    61: ("Light Rain",     "rain"),
    63: ("Rain",           "rain"),
    65: ("Heavy Rain",     "rain"),
    71: ("Light Snow",     "snow"),
    73: ("Snow",           "snow"),
    75: ("Heavy Snow",     "snow"),
    77: ("Snow Grains",    "snow"),
    80: ("Light Showers",  "rain"),
    81: ("Showers",        "rain"),
    82: ("Heavy Showers",  "rain"),
    85: ("Snow Showers",   "snow"),
    86: ("Heavy Snow Sh.", "snow"),
    95: ("Thunderstorm",   "thunder"),
    96: ("Thunder + Hail", "thunder"),
    99: ("Thunder + Hail", "thunder"),
}

def fetch_weather():
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={LATITUDE}&longitude={LONGITUDE}"
        f"&daily=temperature_2m_max,temperature_2m_min"
        f",apparent_temperature_max,apparent_temperature_min"
        f",precipitation_sum,weathercode"
        f"&timezone={TIMEZONE}&forecast_days={FORECAST_DAYS}"
    )
    print("Fetching weather from Open-Meteo...")
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()["daily"]

    days = []
    for i in range(FORECAST_DAYS):
        code = data["weathercode"][i]
        label, condition = WMO_CODES.get(code, ("Unknown", "cloud"))
        days.append({
            "date":         datetime.date.fromisoformat(data["time"][i]),
            "temp_max":     round(data["temperature_2m_max"][i]),
            "temp_min":     round(data["temperature_2m_min"][i]),
            "feels_max":    round(data["apparent_temperature_max"][i]),
            "feels_min":    round(data["apparent_temperature_min"][i]),
            "precip":       round(data["precipitation_sum"][i], 1),
            "condition":    label,
            "icon":         condition,
        })
    print(f"Fetched {len(days)} days of forecast.")
    return days


# ---------------------------------------------------------------------------
# WEATHER ICON DRAWING
# ---------------------------------------------------------------------------

def draw_sun(draw, cx, cy, r, fill):
    """Simple sun: filled circle + radiating lines."""
    draw.ellipse([cx-r, cy-r, cx+r, cy+r], fill=fill)
    ray = r + 8
    for angle_deg in range(0, 360, 45):
        import math
        a = math.radians(angle_deg)
        x1 = int(cx + (r + 4) * math.cos(a))
        y1 = int(cy + (r + 4) * math.sin(a))
        x2 = int(cx + ray * math.cos(a))
        y2 = int(cy + ray * math.sin(a))
        draw.line([x1, y1, x2, y2], fill=fill, width=2)


def draw_cloud(draw, cx, cy, fill):
    """Simple cloud: overlapping ellipses."""
    draw.ellipse([cx-28, cy-10, cx+28, cy+20], fill=fill)
    draw.ellipse([cx-18, cy-22, cx+8,  cy+4],  fill=fill)
    draw.ellipse([cx+2,  cy-18, cx+26, cy+6],  fill=fill)


def draw_rain(draw, cx, cy, fill):
    """Cloud with rain drops below."""
    draw_cloud(draw, cx, cy - 8, fill)
    for dx in [-14, 0, 14]:
        draw.line([cx+dx, cy+16, cx+dx-4, cy+30], fill=fill, width=2)


def draw_snow(draw, cx, cy, fill):
    """Cloud with snowflake dots below."""
    draw_cloud(draw, cx, cy - 8, fill)
    for dx in [-14, 0, 14]:
        r = 3
        sx, sy = cx+dx, cy+22
        draw.ellipse([sx-r, sy-r, sx+r, sy+r], fill=fill)


def draw_thunder(draw, cx, cy, fill):
    """Cloud with a lightning bolt below."""
    draw_cloud(draw, cx, cy - 8, fill)
    pts = [
        (cx+4,  cy+12),
        (cx-4,  cy+24),
        (cx+2,  cy+24),
        (cx-6,  cy+38),
        (cx+10, cy+22),
        (cx+2,  cy+22),
    ]
    draw.polygon(pts, fill=fill)


def draw_partly_cloudy(draw, cx, cy, fill):
    """Small sun peeking behind a cloud."""
    draw_sun(draw, cx+10, cy-6, 12, fill)
    # Draw cloud slightly lighter to partially obscure sun
    draw_cloud(draw, cx-4, cy+4, fill=180)
    draw_cloud(draw, cx-4, cy+4, fill=None)
    # Re-draw cloud outline
    draw.ellipse([cx-32, cy-6,  cx+24, cy+24], outline=fill, width=2)
    draw.ellipse([cx-22, cy-18, cx+4,  cy+8],  outline=fill, width=2)
    draw.ellipse([cx-2,  cy-14, cx+22, cy+10], outline=fill, width=2)


def draw_icon(draw, icon_key, cx, cy, fill):
    dispatch = {
        "sun":           draw_sun,
        "cloud":         draw_cloud,
        "rain":          draw_rain,
        "snow":          draw_snow,
        "thunder":       draw_thunder,
        "partly_cloudy": draw_partly_cloudy,
    }
    fn = dispatch.get(icon_key, draw_cloud)
    if icon_key == "sun":
        fn(draw, cx, cy, 18, fill)
    elif icon_key == "partly_cloudy":
        fn(draw, cx, cy, fill)
    else:
        fn(draw, cx, cy, fill)


# ---------------------------------------------------------------------------
# DRAWING HELPERS
# ---------------------------------------------------------------------------

def cx_text(draw, text, font, x, y, w, fill=0):
    bb = draw.textbbox((0, 0), text, font=font)
    tw = bb[2] - bb[0]
    draw.text((x + (w - tw) // 2, y), text, font=font, fill=fill)


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def generate_weather(eink_host=None):
    # --- Network ---
    if eink_host is None:
        eink_host = choose_network()

    days = fetch_weather()
    today = datetime.date.today()

    # --- Fonts ---
    font_header  = load_font(22, bold=False)
    font_day     = load_font(24, bold=True)
    font_date    = load_font(20, bold=False)
    font_cond    = load_font(20, bold=False)
    font_temp    = load_font(40, bold=True)
    font_small   = load_font(20, bold=False)
    font_label   = load_font(20, bold=False)

    # --- Layout ---
    HEADER_H  = 48
    CARD_PAD  = 8
    COL_W     = WIDTH // FORECAST_DAYS
    BODY_TOP  = HEADER_H
    BODY_H    = HEIGHT - BODY_TOP  # 432px

    img  = Image.new("L", (WIDTH, HEIGHT), BG_FILL)
    draw = ImageDraw.Draw(img)

    # Header
    draw.rectangle([0, 0, WIDTH-1, HEADER_H-1], fill=HEADER_FILL)
    header_text = f"Toronto Forecast — {today.strftime('%A, %B')} {today.day}"
    draw.text((14, 13), header_text, font=font_header, fill=255)

    # Cards
    for i, day in enumerate(days):
        x0 = i * COL_W
        x1 = x0 + COL_W - 1
        y0 = BODY_TOP
        y1 = HEIGHT - 1

        is_today = (day["date"] == today)
        card_bg  = CARD_TODAY_FILL if is_today else CARD_FILL
        draw.rectangle([x0, y0, x1, y1], fill=card_bg)

        # Vertical dividers
        if i > 0:
            draw.line([x0, y0, x0, y1], fill=DIVIDER_FILL, width=1)

        y = y0 + 22

        # Day name
        day_name = "Today" if is_today else day["date"].strftime("%A")
        cx_text(draw, day_name, font_day, x0, y, COL_W, fill=TEXT_FILL)
        y += 34

        # Date
        date_str = f"{day['date'].strftime('%b')} {day['date'].day}"
        cx_text(draw, date_str, font_date, x0, y, COL_W, fill=SUBTEXT_FILL)
        y += 30

        # Divider
        draw.line([x0+12, y+4, x1-12, y+4], fill=DIVIDER_FILL, width=1)
        y += 22

        # Weather icon
        icon_cx = x0 + COL_W // 2
        draw_icon(draw, day["icon"], icon_cx, y + 42, fill=ICON_FILL)
        y += 100

        # Condition label
        cx_text(draw, day["condition"], font_cond, x0, y, COL_W, fill=SUBTEXT_FILL)
        y += 32

        # Divider
        draw.line([x0+12, y+4, x1-12, y+4], fill=DIVIDER_FILL, width=1)
        y += 22

        # High / Low temps
        temp_str = f"{day['temp_max']}° / {day['temp_min']}°"
        cx_text(draw, temp_str, font_temp, x0, y, COL_W, fill=TEXT_FILL)
        y += 58

        # Feels like
        feels_str = f"Feels {day['feels_max']}° / {day['feels_min']}°"
        cx_text(draw, feels_str, font_small, x0, y, COL_W, fill=SUBTEXT_FILL)
        y += 30

        # Precipitation
        precip_str = f"Precip: {day['precip']} mm"
        cx_text(draw, precip_str, font_small, x0, y, COL_W, fill=SUBTEXT_FILL)

    # Bottom border
    draw.line([0, HEIGHT-1, WIDTH-1, HEIGHT-1], fill=DIVIDER_FILL, width=1)

    # --- Save ---
    img = img.rotate(90, expand=True)
    os.makedirs("output", exist_ok=True)
    img.save(OUTPUT_PATH, format="BMP")
    print(f"Saved: {os.path.abspath(OUTPUT_PATH)}")

    # --- Upload ---
    if EINK_UPLOAD:
        upload_to_eink(OUTPUT_PATH, eink_host)


def upload_to_eink(filepath, eink_host):
    """Upload the BMP to the CrossPoint e-ink device via HTTP."""
    filename = os.path.basename(filepath)

    # Delete any existing files with our prefix
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

    # Upload new file
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
            print(f"Uploaded successfully → {EINK_FOLDER}/{filename}")
        else:
            print(f"Upload failed: HTTP {response.status_code} — {response.text}")
    except requests.exceptions.ConnectionError:
        print("Could not connect to the e-ink device.")
        print(f"Make sure your laptop is on the right network and {eink_host} is correct.")
    except Exception as e:
        print(f"Upload error: {e}")


if __name__ == "__main__":
    generate_weather()
