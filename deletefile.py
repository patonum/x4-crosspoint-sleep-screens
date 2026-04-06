"""
deletefile.py
Browse folders and delete files on the CrossPoint e-ink device.
Supports navigating into subfolders.

Requirements:
    pip install requests
"""

import json
import requests
from config import choose_network

FOLDER_PROFILES = {
    "1": ("Sleep calendar", "/sleep_calendar"),
    "2": ("Fiction",        "/Fiction"),
    "3": ("Nonfiction",     "/Nonfiction"),
}


def choose_start_folder():
    print("Select starting folder:")
    for key, (name, path) in FOLDER_PROFILES.items():
        print(f"  {key}) {name} ({path})")
    choice = input("Enter number: ").strip()
    if choice in FOLDER_PROFILES:
        name, path = FOLDER_PROFILES[choice]
        print()
        return path
    else:
        print("Invalid choice, exiting.")
        exit(1)


def list_folder(eink_host, folder):
    """Returns (folders, files) lists for the given path."""
    try:
        response = requests.get(f"{eink_host}/api/files?path={folder}", timeout=10)
        if response.status_code != 200:
            print(f"Failed to list folder: {response.status_code} — {response.text}")
            return [], []
        items   = response.json()
        folders = [f for f in items if f.get("isDirectory")]
        files   = [f for f in items if not f.get("isDirectory")]
        return folders, files
    except Exception as e:
        print(f"Error fetching folder contents: {e}")
        return [], []


def browse_and_delete(eink_host, current_path, parent_path=None):
    """
    Recursively browse folders. Returns when the user quits or goes back
    to the parent.
    """
    while True:
        folders, files = list_folder(eink_host, current_path)

        print(f"\nCurrent folder: {current_path}")
        print("-" * 62)

        options = {}
        idx = 1

        # List subfolders first
        if folders:
            print("  Folders:")
            for f in folders:
                print(f"    {idx}) 📁 {f['name']}/")
                options[str(idx)] = ("folder", f)
                idx += 1

        # List files
        if files:
            print("  Files:")
            for f in files:
                size = f"{f.get('size', 0) / 1024:.1f} KB"
                print(f"    {idx}) 📄 {f['name']}  ({size})")
                options[str(idx)] = ("file", f)
                idx += 1

        if not folders and not files:
            print("  (empty)")

        # Navigation options
        print()
        if parent_path is not None:
            print("  b) ← Back")
        print("  d) Delete files here")
        print("  q) Quit")

        choice = input("\nEnter number to open, or a command: ").strip().lower()

        if choice == "q":
            print("Bye!")
            exit(0)
        elif choice == "b" and parent_path is not None:
            return
        elif choice == "d":
            if not files:
                print("No files in this folder to delete.")
            else:
                delete_from_folder(eink_host, current_path, files)
        elif choice in options:
            kind, item = options[choice]
            if kind == "folder":
                subfolder = f"{current_path}/{item['name']}"
                browse_and_delete(eink_host, subfolder, parent_path=current_path)
            else:
                print(f"  (That's a file — use 'd' to delete files in this folder)")
        else:
            print("Invalid input, try again.")


def delete_from_folder(eink_host, folder, files):
    """Show files and prompt for deletion."""
    print(f"\nFiles in {folder}:")
    print(f"{'#':<4} {'Name':<45} {'Size (KB)':>10}")
    print("-" * 62)
    for i, f in enumerate(files, 1):
        size = f"{f.get('size', 0) / 1024:.1f}"
        print(f"{i:<4} {f['name']:<45} {size:>10}")

    print("\nEnter numbers to delete (e.g. 1,3), 'all', or 'c' to cancel:")
    raw = input("> ").strip().lower()

    if raw == "c" or raw == "":
        print("Cancelled.")
        return
    elif raw == "all":
        targets = files
    else:
        try:
            indices = [int(x.strip()) - 1 for x in raw.split(",")]
            targets = [files[i] for i in indices if 0 <= i < len(files)]
        except (ValueError, IndexError):
            print("Invalid input — no files deleted.")
            return

    if not targets:
        print("No valid files selected.")
        return

    # Confirm
    print(f"\nAbout to delete {len(targets)} file(s):")
    for f in targets:
        print(f"  - {f['name']}")
    confirm = input("\nAre you sure? (y/n): ").strip().lower()
    if confirm != "y":
        print("Cancelled.")
        return

    # Delete
    for f in targets:
        path = f"{folder}/{f['name']}"
        try:
            r = requests.post(
                f"{eink_host}/delete",
                data={"paths": json.dumps([path])},
                timeout=10,
            )
            if r.status_code == 200:
                print(f"✓ Deleted: {f['name']}")
            else:
                print(f"✗ Failed to delete {f['name']}: {r.status_code} — {r.text}")
        except Exception as e:
            print(f"Error deleting {f['name']}: {e}")


def main():
    eink_host    = choose_network()
    start_folder = choose_start_folder()
    browse_and_delete(eink_host, start_folder)


if __name__ == "__main__":
    main()
