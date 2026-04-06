"""
config.py
Shared configuration for all e-ink display scripts.
Edit this file to update network profiles and device settings in one place.
"""

# ---------------------------------------------------------------------------
# NETWORK PROFILES — add or edit as needed
# ---------------------------------------------------------------------------

NETWORK_PROFILES = {
    "1": ("Home",                      "http://10.88.111.23"),
    "2": ("Phone hotspot",             "http://172.20.10.10"),
    "3": ("X4 hotspot (no calendar)",  "http://192.168.4.1"),
}

# ---------------------------------------------------------------------------
# DEVICE SETTINGS — shared across all scripts
# ---------------------------------------------------------------------------

EINK_FOLDER  = "/sleep_calendar"
EINK_UPLOAD  = True


# ---------------------------------------------------------------------------
# NETWORK CHOOSER — called once by the launcher, or directly by each script
# ---------------------------------------------------------------------------

def choose_network():
    print("Select network:")
    for key, (name, host) in NETWORK_PROFILES.items():
        print(f"  {key}) {name} ({host})")
    choice = input("Enter number: ").strip()
    if choice in NETWORK_PROFILES:
        name, host = NETWORK_PROFILES[choice]
        print(f"Using {name}: {host}\n")
        return host
    else:
        print("Invalid choice, exiting.")
        exit(1)
