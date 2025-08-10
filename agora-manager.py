import base64
import hmac
import json
import os
import random
import subprocess
import time
import webbrowser
from base64 import b64encode
from hashlib import sha256
from struct import pack
from dotenv import load_dotenv  # pip install python-dotenv

import requests

try:
    from rich.console import Console
    from rich.prompt import Prompt
    console = Console()
except ImportError:
    console = None
    Prompt = input

class AgoraAPI:
    """Modular class for Agora operations (extendable for Flask endpoints/UI)."""
    def __init__(self, customer_key: str, customer_secret: str, region: str = "na"):
        self.region = region
        auth_str = f"{customer_key}:{customer_secret}"
        self.auth_header = {"Authorization": f"Basic {base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')}",
                            "Content-Type": "application/json"}

    def list_projects(self) -> list[dict]:
        """List active App IDs/projects only (status==1)."""
        url = f"https://api.agora.io/dev/v1/projects"
        response = requests.get(url, headers=self.auth_header)
        response.raise_for_status()
        projects = response.json().get("projects", [])
        return [proj for proj in projects if proj.get("status") == 1]  # Filter active only

    def get_channel_details(self, app_id: str, channel_name: str) -> dict:
        """Get details for a specific channel (users/hosts)."""
        url = f"https://api.agora.io/dev/v1/channel/user/{app_id}/{channel_name}"
        response = requests.get(url, headers=self.auth_header)
        response.raise_for_status()
        data = response.json().get("data", {})
        if data.get("mode") == 2:  # Live mode
            return {
                "hostCount": len(data.get("broadcasters", [])),
                "userCount": data.get("audience_total", 0)  # Or len(audience) if partial
            }
        else:
            return {"hostCount": 0, "userCount": data.get("total", 0)}

    def get_active_channels(self, app_id: str) -> list[dict]:
        """Get active channels for App ID, with stream status (users/hosts)."""
        url = f"https://api.agora.io/dev/v1/channel/{app_id}"
        response = requests.get(url, headers=self.auth_header)
        response.raise_for_status()
        channels = response.json().get("data", {}).get("channels", [])
        active_channels = []
        for ch in channels:
            details = self.get_channel_details(app_id, ch["channel_name"])
            host_count = details["hostCount"]
            user_count = details["userCount"]
            if user_count > 0 or host_count > 0:
                ch["userCount"] = user_count
                ch["hostCount"] = host_count
                active_channels.append(ch)
        return active_channels

    def generate_stream_key(self, app_id: str, channel_name: str, uid: str, expires_after: int = 3600) -> str:
        """Generate stream key for push."""
        url = f"https://api.agora.io/{self.region}/v1/projects/{app_id}/rtls/ingress/streamkeys"
        body = {"settings": {"channel": channel_name, "uid": uid, "expiresAfter": expires_after}}
        response = requests.post(url, json=body, headers=self.auth_header)
        response.raise_for_status()
        return response.json()["data"]["streamKey"]

    def generate_rtc_token(self, app_id: str, app_cert: str, channel_name: str, uid: int = 0, role: int = 2, expires_after: int = 3600) -> str:
        """Generate RTC token (local gen; needs App Cert)."""
        app_cert_bytes = bytes.fromhex(app_cert)
        uid_str = str(uid)
        current_time = int(time.time())
        expire_time = current_time + expires_after
        privileges = {1: expire_time}  # kJoinChannel
        if role == 1:  # Host
            privileges.update({2: expire_time, 3: expire_time, 4: expire_time})
        messages_packed = pack('>H', len(privileges))
        for k in sorted(privileges):
            messages_packed += pack('>H', k) + pack('>I', privileges[k])
        salt = random.randint(1, 99999999)
        packed = pack('>I', salt) + pack('>I', current_time) + pack('>I', expire_time) + messages_packed
        sign_content = app_id.encode('utf-8') + channel_name.encode('utf-8') + uid_str.encode('utf-8') + packed
        signature = hmac.new(app_cert_bytes, sign_content, sha256).digest()
        version = "006"
        signature_b64 = b64encode(signature).decode('utf-8').rstrip('=')
        packed_b64 = b64encode(packed).decode('utf-8').rstrip('=')
        return f"{version}{app_id}{signature_b64}{packed_b64}"

    # Placeholder for create/delete (no API; use Console)
    def create_project(self, name: str):
        print("Create project not supported via API; use Agora Console.")

    def delete_project(self, app_id: str):
        print("Delete project not supported via API; use Agora Console.")

def load_env():
    """Modular env loader: Load .env if exists, set os.environ."""
    if os.path.exists('.env'):
        load_dotenv('.env')
        print("Loaded .env file.")
    else:
        print(".env not found; using prompts.")

def open_console(page: str = ""):
    """Modular: Open Agora Console in browser (extendable for specific pages)."""
    base_url = "https://console.agora.io"
    if page:
        base_url += f"/{page}"
    webbrowser.open(base_url)
    print(f"Opened Console: {base_url}")

def show_menu():
    """Modular menu (easy to port to Flask routes)."""
    if console:
        console.print("[bold]Agora Manager Menu:[/bold]")
    else:
        print("Agora Manager Menu:")
    options = [
        "1: List App IDs and active streams",
        "2: Delete App ID (Console only)",
        "3: Add new App ID and generate key/token",
        "4: Open stream viewer in browser",
        "5: Open Agora Console",
        "0: Exit"
    ]
    for opt in options:
        print(opt)
    return Prompt.ask("Choose option")

def main():
    """Main CLI loop (load env, prompt fallback, menu reactive)."""
    load_env()
    customer_key = os.getenv("AGORA_CUSTOMER_KEY") or Prompt.ask("Enter Customer Key")
    customer_secret = os.getenv("AGORA_CUSTOMER_SECRET") or Prompt.ask("Enter Customer Secret", password=True)
    api = AgoraAPI(customer_key, customer_secret)

    while True:
        choice = show_menu()
        if choice == "1":
            projects = api.list_projects()
            if not projects:
                print("No active projects found.")
            for proj in projects:
                app_id = proj.get("vendor_key")
                print(f"App ID: {app_id} (Name: {proj.get('name')}, Status: Active)")
                active_channels = api.get_active_channels(app_id)
                if active_channels:
                    print("Active Streams:")
                    for ch in active_channels:
                        print(f" - Channel: {ch['channel_name']}, Users: {ch['userCount']}, Hosts: {ch['hostCount']}, Streaming: Yes")
                else:
                    print(" No active streams.")
        elif choice == "2":
            app_id = Prompt.ask("Enter App ID to delete")
            open_console("projects")  # Open projects page
            print("Delete in Console, then press Enter when done.")
            input()
        elif choice == "3":
            print("Create new project in Console: Set region/data center, enable Media Gateway, get App ID/Cert.")
            open_console("projects/create")  # Open create page if exists, else projects
            input("Press Enter after creating and enabling Media Gateway...")
            app_id = Prompt.ask("Enter new App ID")
            app_cert = os.getenv("AGORA_APP_CERT") or Prompt.ask("Enter App Cert (hex)")
            channel_name = Prompt.ask("Enter Channel Name")
            uid = Prompt.ask("Enter UID", default="1")
            stream_key = api.generate_stream_key(app_id, channel_name, uid)
            token = api.generate_rtc_token(app_id, app_cert, channel_name)
            print(f"App ID: {app_id}\nStream Key: {stream_key}\nToken: {token}")
        elif choice == "4":
            # Run viewer.py in background, open browser
            viewer_path = "viewer.py"  # Assume in same dir
            subprocess.Popen(["streamlit", "run", viewer_path, "--server.headless=true"])
            time.sleep(3)  # Wait for start
            webbrowser.open("http://localhost:8501")
            print("Viewer opened in browser (background process).")
        elif choice == "5":
            open_console()
        elif choice == "0":
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()