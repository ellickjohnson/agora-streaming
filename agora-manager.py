import base64
import hmac
import json
import os
import random
import struct
import subprocess
import time
import webbrowser
from base64 import b64encode
from hashlib import sha256
from dotenv import load_dotenv  # pip install python-dotenv

import requests

try:
    from rich.console import Console
    from rich.prompt import Prompt
    console = Console()
except ImportError:
    console = None
    Prompt = input

kJoinChannel = 1
kPublishAudioStream = 2
kPublishVideoStream = 3
kPublishDataStream = 4
kAdministrateChannel = 101

class Service:
    TYPE = 0

    def __init__(self):
        self.privileges = {}

    def add_privilege(self, privilege, expire):
        self.privileges[privilege] = expire

    def pack(self):
        packed_privileges = b''
        for privilege, expire in sorted(self.privileges.items()):
            packed_privileges += struct.pack('>H', privilege) + struct.pack('>I', expire)
        return struct.pack('>H', self.TYPE) + struct.pack('>H', len(self.privileges)) + packed_privileges

class AccessToken:
    def __init__(self, app_id="", app_certificate="", issue_ts=0, expire_time=900):
        self.app_id = app_id
        self.app_certificate = app_certificate
        self.issue_ts = issue_ts if issue_ts else int(time.time())
        self.expire_time = expire_time
        self.salt = random.randint(1, 99999999)
        self.services = {}

    def add_service(self, service):
        self.services[service.TYPE] = service

    def build(self):
        packed_services = b''
        for _, service in self.services.items():
            packed_services += service.pack()

        packed = struct.pack('>I', self.salt) + struct.pack('>I', self.issue_ts) + struct.pack('>I', self.expire_time) + struct.pack('>H', len(self.services)) + packed_services

        sign_content = self.app_id.encode('utf-8') + packed
        signature = hmac.new(self.app_certificate.encode('utf-8'), sign_content, sha256).digest()
        signature_b64 = base64.b64encode(signature).decode('utf-8')

        content_b64 = base64.b64encode(packed).decode('utf-8')

        return "007" + self.app_id + signature_b64 + content_b64

class ServiceRtc(Service):
    TYPE = 1

    def __init__(self, channel_name="", uid=""):
        super().__init__()
        self.channel_name = channel_name
        self.uid = str(uid) if uid else ""

    def pack(self):
        return super().pack() + struct.pack('>H', len(self.channel_name)) + self.channel_name.encode('utf-8') + struct.pack('>H', len(self.uid)) + self.uid.encode('utf-8')

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

    def get_channels(self, app_id: str) -> list[dict]:
        """Get channels for App ID (API returns only online/active ones), with stream status (users/hosts)."""
        url = f"https://api.agora.io/dev/v1/channel/{app_id}"
        response = requests.get(url, headers=self.auth_header)
        response.raise_for_status()
        channels = response.json().get("data", {}).get("channels", [])
        for ch in channels:
            details = self.get_channel_details(app_id, ch["channel_name"])
            ch["userCount"] = details["userCount"]
            ch["hostCount"] = details["hostCount"]
            ch["active"] = (ch["userCount"] > 0 or ch["hostCount"] > 0)
        return channels

    def generate_stream_key(self, app_id: str, channel_name: str, uid: str, expires_after: int = 3600) -> str:
        """Generate stream key for push."""
        url = f"https://api.agora.io/{self.region}/v1/projects/{app_id}/rtls/ingress/streamkeys"
        body = {"settings": {"channel": channel_name, "uid": uid, "expiresAfter": expires_after}}
        response = requests.post(url, json=body, headers=self.auth_header)
        response.raise_for_status()
        return response.json()["data"]["streamKey"]

    def generate_rtc_token(self, app_id: str, app_cert: str, channel_name: str, uid: int = 0, role: int = 2, expires_after: int = 3600) -> str:
        """Generate RTC token using official Agora logic (needs App Cert)."""
        token = AccessToken(app_id, app_cert, expire_time=expires_after)
        rtc_service = ServiceRtc(channel_name, uid)
        rtc_service.add_privilege(kJoinChannel, expires_after)
        if role == 1:  # Host/Publisher
            rtc_service.add_privilege(kPublishAudioStream, expires_after)
            rtc_service.add_privilege(kPublishVideoStream, expires_after)
            rtc_service.add_privilege(kPublishDataStream, expires_after)
        token.add_service(rtc_service)
        return token.build()

    def create_project(self, name: str, enable_sign_key: bool = False) -> dict:
        """Create a new project via API."""
        url = "https://api.agora.io/dev/v1/project"
        body = {"name": name, "enable_sign_key": enable_sign_key}
        response = requests.post(url, json=body, headers=self.auth_header)
        response.raise_for_status()
        return response.json()

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
        "1: List App IDs and channels (with activity status)",
        "2: Delete App ID (Console only)",
        "3: Create new App ID",
        "4: Open stream viewer in browser",
        "5: Open Agora Console",
        "6: Generate Stream Key for App ID",
        "7: Generate RTC Token for App ID",
        "0: Exit"
    ]
    for opt in options:
        print(opt)
    return Prompt.ask("Choose option")

def get_valid_int(prompt_msg: str, min_val: int, max_val: int) -> int:
    """Common function to get validated integer input within range."""
    while True:
        try:
            value = int(Prompt.ask(prompt_msg))
            if min_val <= value <= max_val:
                return value
            else:
                print(f"Invalid: Must be between {min_val} and {max_val}.")
        except ValueError:
            print("Invalid: Enter a number.")

def update_env_file(key: str, value: str):
    """Update or append to .env file."""
    env_path = '.env'
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            lines = f.readlines()
        updated = False
        for i, line in enumerate(lines):
            if line.startswith(f"{key}="):
                lines[i] = f"{key}={value}\n"
                updated = True
                break
        if not updated:
            lines.append(f"{key}={value}\n")
        with open(env_path, 'w') as f:
            f.writelines(lines)
        print(f"Updated {key} in .env.")
    else:
        with open(env_path, 'w') as f:
            f.write(f"{key}={value}\n")
        print(f"Created .env and added {key}.")

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
                print(f"App ID: {app_id} (Project ID: {proj.get('id')}, Name: {proj.get('name')}, Status: Active)")
                channels = api.get_channels(app_id)
                if channels:
                    print("  Channels (only active/online channels are listed by Agora API):")
                    for ch in channels:
                        active_status = "Yes" if ch["active"] else "No"
                        print(f"    - Channel: {ch['channel_name']}, Active: {active_status}, Users: {ch['userCount']}, Hosts: {ch['hostCount']}")
                else:
                    print("  No active channels.")
        elif choice == "2":
            app_id = Prompt.ask("Enter App ID to delete")
            open_console("projects")  # Open projects page
            print("Delete in Console, then press Enter when done.")
            input()
        elif choice == "3":
            print("Creating new project via API.")
            project_name = Prompt.ask("Enter Project Name")
            enable_cert = Prompt.ask("Enable Primary App Certificate? (y/n, recommended for tokens)", default="y").lower() == "y"
            try:
                new_project_resp = api.create_project(project_name, enable_cert)
                project_data = new_project_resp.get("project", {})
                app_id = project_data.get("vendor_key")
                app_cert = project_data.get("sign_key", "")
                if not app_id:
                    print(f"Failed to extract App ID from response: {new_project_resp}")
                    continue
                print(f"New project created! App ID: {app_id}")
                if enable_cert:
                    if app_cert:
                        print(f"App Cert: {app_cert}")
                        save_cert = Prompt.ask("Save this App Cert to .env as AGORA_APP_CERT? (y/n, overwrites if exists)", default="y").lower() == "y"
                        if save_cert:
                            update_env_file("AGORA_APP_CERT", app_cert)
                    else:
                        print("App Cert requested but not returned. Response:", new_project_resp)
                else:
                    print("App Cert not enabled.")
                print("Note: New projects may take ~15 minutes to activate fully.")
                print(f"Opening Console to enable Media Gateway (required for stream keys). In Console: My Projects > Edit '{project_name}' (App ID: {app_id}) > Enable Media Gateway > Save.")
                open_console("projects")
                input("Press Enter after enabling Media Gateway and waiting if needed...")
            except requests.exceptions.HTTPError as e:
                print(f"Error creating project: {e.response.status_code} - {e.response.text}")
        elif choice == "4":
            # Run viewer.py in background, open browser
            viewer_path = "viewer.py"  # Assume in same dir
            subprocess.Popen(["streamlit", "run", viewer_path, "--server.headless=true"])
            time.sleep(3)  # Wait for start
            webbrowser.open("http://localhost:8501")
            print("Viewer opened in browser (background process).")
        elif choice == "5":
            projects = api.list_projects()
            if not projects:
                print("No active projects found.")
                continue
            print("Select Project to open Media Gateway page:")
            for i, proj in enumerate(projects, 1):
                print(f"{i}: App ID {proj['vendor_key']} (Project ID: {proj.get('id')}, Name: {proj['name']})")
            select_idx = get_valid_int("Enter number", 1, len(projects)) - 1
            selected_proj = projects[select_idx]
            project_id = selected_proj.get('id')
            if not project_id:
                print("No project ID found for selected project.")
                continue
            media_gateway_url = f"project-management/{project_id}/media-gateway"
            open_console(media_gateway_url)
        elif choice == "6":
            projects = api.list_projects()
            if not projects:
                print("No active projects found. Create one first.")
                continue
            print("Select App ID:")
            for i, proj in enumerate(projects, 1):
                print(f"{i}: {proj['vendor_key']} (Name: {proj['name']})")
            select_app_idx = get_valid_int("Enter number", 1, len(projects)) - 1
            app_id = projects[select_app_idx]['vendor_key']
            channel_name = Prompt.ask("Enter Channel Name")
            uid = Prompt.ask("Enter UID", default="0")
            expires = int(Prompt.ask("Enter expires (seconds)", default="3600"))
            try:
                stream_key = api.generate_stream_key(app_id, channel_name, uid, expires)
                print(f"Stream Key for App ID {app_id}, Channel {channel_name}, UID {uid}: {stream_key}")
            except requests.exceptions.HTTPError as e:
                print(f"Error generating stream key: {e.response.status_code} - {e.response.text}")
        elif choice == "7":
            projects = api.list_projects()
            if not projects:
                print("No active projects found. Create one first.")
                continue
            print("Select App ID:")
            for i, proj in enumerate(projects, 1):
                print(f"{i}: {proj['vendor_key']} (Name: {proj['name']})")
            select_app_idx = get_valid_int("Enter number", 1, len(projects)) - 1
            app_id = projects[select_app_idx]['vendor_key']
            channel_name = Prompt.ask("Enter Channel Name")
            app_cert = os.getenv("AGORA_APP_CERT") or Prompt.ask("Enter App Cert (hex, from Console or creation)")
            if not app_cert:
                print("App Cert required for RTC token. Skipping.")
                continue
            uid = int(Prompt.ask("Enter UID", default="0"))
            role = int(Prompt.ask("Enter Role (1=host, 2=audience)", default="2"))
            expires = int(Prompt.ask("Enter expires (seconds)", default="3600"))
            try:
                token = api.generate_rtc_token(app_id, app_cert, channel_name, uid, role, expires)
                print(f"RTC Token for App ID {app_id}, Channel {channel_name}: {token}")
            except Exception as e:
                print(f"Error generating RTC token: {str(e)}")
        elif choice == "0":
            break
        else:
            print("Invalid choice.")

if __name__ == "__main__":
    main()