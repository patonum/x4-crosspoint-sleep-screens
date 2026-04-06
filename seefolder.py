import requests
from config import choose_network, EINK_FOLDER
 
FOLDER_PROFILES = {
    "1": ("Sleep calendar", EINK_FOLDER),
    "2": ("Fiction",        "/Fiction"),
    "3": ("Nonfiction",     "/Nonfiction"),
}


def choose_folder():
    print("Select folder:")
    for key, (name, path) in FOLDER_PROFILES.items():
        print(f"  {key}) {name} ({path})")
    choice = input("Enter number: ").strip()
    if choice in FOLDER_PROFILES:
        name, path = FOLDER_PROFILES[choice]
        print(f"Using {name}: {path}\n")
        return path
    else:
        print("Invalid choice, exiting.")
        exit(1)


def view_folder(host = None):
    folder = choose_folder()
    if host is None:
        host = choose_network()
    
    try:
        url = f"{host}/api/files?path={folder}" #define url to look at
        response = requests.get(url)
        
        if response.status_code == 200:
            files = response.json()
            if not files:
                print("Folder is empty.")
                return
            print(f"{'Name':<40} {'Type':<8} {'Size (KB)':>10}")
            print("-" * 62)
            for f in files:
                name = f.get("name", "?")
                kind = "Folder" if f.get("isDirectory") else f["name"].split(".")[-1].upper()
                size = f"{f.get('size', 0) / 1024:.1f}" if not f.get("isDirectory") else "-"
                print(f"{name:<40} {kind:<8} {size:>10}")
        else:
            print(f"Failed: {response.status_code} — {response.text}")
    except Exception as e:
        print(f"Error: {e}")
    

view_folder()


