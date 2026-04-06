"""
checkin.py
Interactive daily habit check-in. Run this each evening to mark off
completed habits, then run run_all.py to push the updated display.

Usage:
    python checkin.py
"""

import json
import datetime
import os

HABITS_FILE = "habits.json"


def load_habits():
    if not os.path.exists(HABITS_FILE):
        print(f"No {HABITS_FILE} found — creating a default one.")
        data = {"habits": ["Exercise", "Read", "Meditate", "Drink water"], "completed": {}}
        save_habits(data)
        return data
    with open(HABITS_FILE, "r") as f:
        return json.load(f)


def save_habits(data):
    with open(HABITS_FILE, "w") as f:
        json.dump(data, f, indent=4)


def checkin():
    data    = load_habits()
    habits  = data["habits"]
    today   = str(datetime.date.today())
    already = data["completed"].get(today, [])

    print("\n" + "=" * 40)
    print(f"  Habit Check-in — {datetime.date.today().strftime('%A, %B %d')}")
    print("=" * 40)

    if not habits:
        print("No habits found. Add some to habits.json first.")
        return

    print("\nWhich habits did you complete today?")
    print("(Press Enter with no input to keep existing, or enter numbers separated by commas)\n")

    for i, habit in enumerate(habits, 1):
        done = "✓" if habit in already else " "
        print(f"  {i}) [{done}] {habit}")

    print("\nEnter numbers (e.g. 1,3,4), 'all', or press Enter to keep as-is:")
    raw = input("> ").strip()

    if raw == "":
        print("No changes made.")
    elif raw.lower() == "all":
        data["completed"][today] = habits[:]
        save_habits(data)
        print(f"Marked all {len(habits)} habits as complete!")
    else:
        try:
            indices  = [int(x.strip()) - 1 for x in raw.split(",")]
            selected = [habits[i] for i in indices if 0 <= i < len(habits)]
            data["completed"][today] = selected
            save_habits(data)
            if selected:
                print(f"\nSaved for today: {', '.join(selected)}")
            else:
                print("No valid habits selected — saved empty for today.")
        except (ValueError, IndexError):
            print("Invalid input — no changes made.")

    # Show a summary of the week
    print("\n--- This week ---")
    today_dt   = datetime.date.today()
    week_start = today_dt - datetime.timedelta(days=(today_dt.weekday() + 1) % 7)
    for i in range(7):
        day     = week_start + datetime.timedelta(days=i)
        day_str = str(day)
        done    = data["completed"].get(day_str, [])
        total   = len(habits)
        label   = day.strftime("%a %b %d")
        bar     = "✓" * len(done) + "·" * (total - len(done))
        marker  = " ← today" if day == today_dt else ""
        print(f"  {label}  [{bar}] {len(done)}/{total}{marker}")

    print()


if __name__ == "__main__":
    checkin()
