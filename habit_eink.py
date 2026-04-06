"""
habit_eink.py
Generates an 800x480 greyscale BMP weekly habit tracker for e-ink displays.
Reads habit data from habits.json (managed by checkin.py).

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
# CONFIG
# ---------------------------------------------------------------------------

WIDTH, HEIGHT = 800, 480
OUTPUT_PATH   = f"output/habits_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.bmp"
HABITS_FILE   = "habits.json"
FILE_PREFIX = "habits_"

# Greyscale palette
BG_FILL         = 255
HEADER_FILL     = 0
ROW_ALT_FILL    = 245   # alternating row background
DONE_FILL       = 40    # dark filled checkbox
EMPTY_FILL      = 255   # white empty checkbox
BORDER_FILL     = 0     # checkbox border
TEXT_FILL       = 0
SUBTEXT_FILL    = 0
TODAY_COL_FILL  = 200   # highlight for today's column
DIVIDER_FILL    = 180


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
# MAIN
# ---------------------------------------------------------------------------

def generate_habits(eink_host=None):
    # --- Network ---
    if eink_host is None:
        eink_host = choose_network()

    # --- Load habits ---
    if not os.path.exists(HABITS_FILE):
        print(f"No {HABITS_FILE} found — run checkin.py first.")
        return
    with open(HABITS_FILE, "r") as f:
        data = json.load(f)

    habits    = data.get("habits", [])
    completed = data.get("completed", {})

    if not habits:
        print("No habits found in habits.json.")
        return

    # --- Date logic (week starts Sunday) ---
    today      = datetime.date.today()
    week_start = today - datetime.timedelta(days=(today.weekday() + 1) % 7)
    days       = [week_start + datetime.timedelta(days=i) for i in range(7)]

    # --- Fonts ---
    font_header  = load_font(22, bold=False)
    font_day     = load_font(14, bold=True)
    font_date    = load_font(12, bold=False)
    font_habit   = load_font(16, bold=False)
    font_count   = load_font(12, bold=False)

    # --- Layout ---
    HEADER_H    = 48
    LABEL_W     = 220     # width of the habit name column
    COL_W       = (WIDTH - LABEL_W) // 7
    BODY_TOP    = HEADER_H
    DAY_ROW_H   = 44      # height of the day header row
    GRID_TOP    = BODY_TOP + DAY_ROW_H
    ROW_H       = (HEIGHT - GRID_TOP) // max(len(habits), 1)
    BOX_SIZE    = min(ROW_H - 10, COL_W - 10, 32)

    img  = Image.new("L", (WIDTH, HEIGHT), BG_FILL)
    draw = ImageDraw.Draw(img)

    # --- Header ---
    draw.rectangle([0, 0, WIDTH - 1, HEADER_H - 1], fill=HEADER_FILL)
    draw.text((14, 13), f"Habit Tracker — {today.strftime('%B %Y')}", font=font_header, fill=255)

    # --- Day columns header ---
    day_names = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"]
    for i, (name, day) in enumerate(zip(day_names, days)):
        x0      = LABEL_W + i * COL_W
        x1      = x0 + COL_W - 1
        is_today = (day == today)
        if is_today:
            draw.rectangle([x0, BODY_TOP, x1, GRID_TOP - 1], fill=TODAY_COL_FILL)
        # Day name
        bb = draw.textbbox((0, 0), name, font=font_day)
        tw = bb[2] - bb[0]
        draw.text((x0 + (COL_W - tw) // 2, BODY_TOP + 6), name, font=font_day, fill=TEXT_FILL)
        # Date number
        date_str = str(day.day)
        bb2 = draw.textbbox((0, 0), date_str, font=font_date)
        tw2 = bb2[2] - bb2[0]
        draw.text((x0 + (COL_W - tw2) // 2, BODY_TOP + 24), date_str, font=font_date, fill=SUBTEXT_FILL)

    # Divider under day header
    draw.line([0, GRID_TOP, WIDTH - 1, GRID_TOP], fill=BORDER_FILL, width=2)

    # Vertical divider after label column
    draw.line([LABEL_W, BODY_TOP, LABEL_W, HEIGHT - 1], fill=DIVIDER_FILL, width=1)

    # --- Habit rows ---
    for row, habit in enumerate(habits):
        y0 = GRID_TOP + row * ROW_H
        y1 = y0 + ROW_H - 1

        # Alternating row background
        if row % 2 == 1:
            draw.rectangle([0, y0, WIDTH - 1, y1], fill=ROW_ALT_FILL)

        # Re-draw today column highlight over row background
        today_x0 = LABEL_W + days.index(today) * COL_W if today in days else None
        if today_x0 is not None:
            draw.rectangle([today_x0, y0, today_x0 + COL_W - 1, y1], fill=TODAY_COL_FILL)

        # Habit name
        bb = draw.textbbox((0, 0), habit, font=font_habit)
        th = bb[3] - bb[1]
        draw.text((14, y0 + (ROW_H - th) // 2), habit, font=font_habit, fill=TEXT_FILL)

        # Row divider
        draw.line([0, y1, WIDTH - 1, y1], fill=DIVIDER_FILL, width=1)

        # Checkboxes for each day
        for col, day in enumerate(days):
            cx = LABEL_W + col * COL_W + COL_W // 2
            cy = y0 + ROW_H // 2
            bx0 = cx - BOX_SIZE // 2
            by0 = cy - BOX_SIZE // 2
            bx1 = bx0 + BOX_SIZE
            by1 = by0 + BOX_SIZE

            day_done = completed.get(str(day), [])
            is_done  = habit in day_done

            if is_done:
                # Filled dark box with white tick
                draw.rectangle([bx0, by0, bx1, by1], fill=DONE_FILL)
                # Draw a tick mark
                mx, my = cx, cy
                draw.line([bx0+5, my, mx-2, by1-5], fill=255, width=3)
                draw.line([mx-2,  by1-5, bx1-4, by0+5], fill=255, width=3)
            else:
                # Empty box with border
                draw.rectangle([bx0, by0, bx1, by1], fill=EMPTY_FILL)
                draw.rectangle([bx0, by0, bx1, by1], outline=BORDER_FILL, width=2)

    # --- Vertical day dividers ---
    for i in range(1, 7):
        x = LABEL_W + i * COL_W
        draw.line([x, BODY_TOP, x, HEIGHT - 1], fill=DIVIDER_FILL, width=1)

    # --- Weekly completion count per habit (right-aligned in label col) ---
    for row, habit in enumerate(habits):
        y0    = GRID_TOP + row * ROW_H
        count = sum(1 for day in days if habit in completed.get(str(day), []))
        label = f"{count}/7"
        bb    = draw.textbbox((0, 0), label, font=font_count)
        tw    = bb[2] - bb[0]
        th    = bb[3] - bb[1]
        draw.text((LABEL_W - tw - 10, y0 + (ROW_H - th) // 2), label, font=font_count, fill=SUBTEXT_FILL)

    # --- Rotate and save ---
    img = img.rotate(90, expand=True)
    os.makedirs("output", exist_ok=True)
    img.save(OUTPUT_PATH, format="BMP")
    print(f"Saved: {os.path.abspath(OUTPUT_PATH)}")

    if EINK_UPLOAD:
        upload_to_eink(OUTPUT_PATH, eink_host)


def upload_to_eink(filepath, eink_host):
    """Upload the BMP to the CrossPoint e-ink device via HTTP."""
    filename = os.path.basename(filepath)

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
            print(f"Uploaded successfully → {EINK_FOLDER}/{filename}")
        else:
            print(f"Upload failed: HTTP {response.status_code} — {response.text}")
    except requests.exceptions.ConnectionError:
        print(f"Could not connect to the e-ink device. Check {eink_host}.")
    except Exception as e:
        print(f"Upload error: {e}")


if __name__ == "__main__":
    generate_habits()
