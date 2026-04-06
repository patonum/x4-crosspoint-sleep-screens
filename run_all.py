"""
run_all.py
Runs the calendar and weather scripts together, asking for the network once.

Usage:
    python run_all.py
"""

import sys
from config import choose_network

# ---------------------------------------------------------------------------
# SCRIPT REGISTRY — add new scripts here
# ---------------------------------------------------------------------------
 
SCRIPTS = {
    "1": ("Calendar",      "calendar_eink",  "generate_calendar"),
    "2": ("Weather",       "weather_eink",   "generate_weather"),
    "3": ("Habit Tracker", "habit_eink",     "generate_habits"),
    "4": ("Daily Agenda",  "agenda_eink",    "generate_agenda"),
}
 
 
def choose_scripts():
    print("\nWhich scripts would you like to run?")
    for key, (name, _, _) in SCRIPTS.items():
        print(f"  {key}) {name}")
    print(f"  a) All")
    print(f"  q) Quit")
 
    raw = input("\nEnter numbers separated by commas (e.g. 1,2) or 'a' for all: ").strip().lower()
 
    if raw == "q":
        print("Bye!")
        sys.exit(0)
    elif raw == "a":
        return list(SCRIPTS.keys())
    else:
        chosen = [x.strip() for x in raw.split(",") if x.strip() in SCRIPTS]
        if not chosen:
            print("No valid choices — exiting.")
            sys.exit(1)
        return chosen


def main():
    print("=" * 40)
    print("  E-Ink Display Updater")
    print("=" * 40)
 
    chosen  = choose_scripts()
    # Only ask for network if at least one script uploads to the device
    eink_host = choose_network()
 
    for key in chosen:
        name, module_name, fn_name = SCRIPTS[key]
        print(f"\n{'=' * 40}")
        print(f"  {name}")
        print("=" * 40)
        module = __import__(module_name)
        fn     = getattr(module, fn_name)
        fn(eink_host=eink_host)
 
    print(f"\n{'=' * 40}")
    print("  All done!")
    print("=" * 40)
 
 
if __name__ == "__main__":
    main()
