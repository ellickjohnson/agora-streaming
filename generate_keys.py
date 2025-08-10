import argparse
import base64
import hmac
import hashlib
import struct
import time
import requests

class AgoraAPI:
    """Modular class for Agora API ops (streaming keys + RTC tokens).
    Extend with more methods (e.g., channel management) for reactive apps.
    """
    def __init__(self, customer_key: str, customer_secret: str, app_id: str, region: str):
        self.app_id = app_id
        self.region = region
        auth_str = f"{customer_key}:{customer_secret}"
        self.auth_header = {"Authorization": f"Basic {base64.b64encode(auth_str.encode('utf-8')).decode('utf-8')}",
                            "Content-Type": "application/json"}

    def generate_stream_key(self, channel_name: str, uid: str, expires_after: int) -> str:
        """Generate streaming key (existing method renamed for modularity)."""
        url = f"https://api.agora.io/{self.region}/v1/projects/{self.app_id}/rtls/ingress/streamkeys"
        body = {
            "settings": {
                "channel": channel_name,
                "uid": uid,
                "expiresAfter": expires_after
            }
        }
        response = requests.post(url, json=body, headers=self.auth_header)
        if response.status_code != 200:
            print(f"API Error: {response.status_code} - {response.text}")
            response.raise_for_status()
        json_resp = response.json()
        if json_resp.get("status") != "success":
            raise ValueError(f"API failed: {json_resp}")
        return json_resp["data"]["streamKey"]

    def generate_rtc_token(self, channel_name: str, uid: int, role: int = 2, expires_after: int = 3600) -> str:
        """Generate RTC token for joining channel.
        Args:
            channel_name: Channel to join.
            uid: User ID (0 for auto-assign).
            role: 1=host, 2=audience (default for viewer).
            expires_after: Validity in seconds.
        Returns:
            Base64-encoded token.
        """
        expires_at = int(time.time()) + expires_after
        # Pack version and app ID
        token = b'\x00\x02'  # Version 2
        token += struct.pack('>I', len(self.app_id)) + self.app_id.encode('utf-8')
        # Pack channel
        token += struct.pack('>I', len(channel_name)) + channel_name.encode('utf-8')
        # Pack UID as string
        token += struct.pack('>I', len(str(uid))) + str(uid).encode('utf-8')
        # Pack expiration and role
        token += struct.pack('>I', expires_at)
        token += struct.pack('>B', role)
        # HMAC with app cert (fetch from Console if needed; assume you have it as hex)
        app_cert = bytes.fromhex("f76e8ace079b47deb51d9703a1ca925a")  # Replace with your Primary Certificate
        signature = hmac.new(app_cert, token, hashlib.sha256).digest()
        # Final token: base64(signature + token)
        return base64.b64encode(signature + token).decode('utf-8')

    def generate_batch_stream_keys(self, channel_name: str, uids: list[str], expires_after: int) -> dict[str, str]:
        """Batch stream keys (existing)."""
        return {uid: self.generate_stream_key(channel_name, uid, expires_after) for uid in uids}

# CLI (updated for new commands)
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Agora API: Stream keys & RTC tokens.")
    parser.add_argument("--customer_key", required=True, help="Agora Customer Key")
    parser.add_argument("--customer_secret", required=True, help="Agora Customer Secret")
    parser.add_argument("--app_id", required=True, help="Agora App ID")
    parser.add_argument("--region", required=True, help="Region code (e.g., na)")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subparser for stream key
    stream_parser = subparsers.add_parser("stream_key")
    stream_parser.add_argument("--channel_name", required=True)
    stream_parser.add_argument("--uid", default="0")
    stream_parser.add_argument("--expires", type=int, default=3600)
    stream_parser.add_argument("--batch_uids", nargs="+", default=None)

    # Subparser for RTC token
    rtc_parser = subparsers.add_parser("rtc_token")
    rtc_parser.add_argument("--channel_name", required=True)
    rtc_parser.add_argument("--uid", type=int, default=0)
    rtc_parser.add_argument("--role", type=int, default=2, help="1=host, 2=audience")
    rtc_parser.add_argument("--expires", type=int, default=3600)

    args = parser.parse_args()
    api = AgoraAPI(args.customer_key, args.customer_secret, args.app_id, args.region)

    if args.command == "stream_key":
        if args.batch_uids:
            keys = api.generate_batch_stream_keys(args.channel_name, args.batch_uids, args.expires)
            for uid, key in keys.items():
                print(f"UID {uid}: {key}")
        else:
            key = api.generate_stream_key(args.channel_name, args.uid, args.expires)
            print(f"Streaming Key: {key}")
    elif args.command == "rtc_token":
        token = api.generate_rtc_token(args.channel_name, args.uid, args.role, args.expires)
        print(f"RTC Token: {token}")