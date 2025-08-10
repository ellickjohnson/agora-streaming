# Agora Tools

This repository contains three Python scripts for managing and interacting with [Agora.io](https://www.agora.io/) services, focusing on real-time communication (RTC) and live streaming. These tools help with generating keys/tokens, viewing streams, and managing projects/channels.

- **viewer.py**: A Streamlit-based web app for viewing live Agora streams in a browser.
- **generate_keys.py**: A CLI script for generating streaming keys and RTC tokens using Agora's API.
- **agora-manager.py**: An interactive CLI manager for listing Agora projects, monitoring active channels, generating keys/tokens, and more.

These scripts assume you have an Agora account with a Customer Key, Customer Secret, and at least one active project (App ID). Enable the "Media Gateway" feature in your Agora Console for streaming functionalities.

## Requirements

### Python Version
- Python 3.8+ (tested on 3.12)

### Dependencies
Install the required packages using pip:

```bash
pip install requests streamlit python-dotenv rich agora-token-builder
```

- `requests`: For API calls (used in all scripts).
- `streamlit`: For the web UI in `viewer.py`.
- `python-dotenv`: For loading environment variables from `.env` files (used in `agora-manager.py`).
- `rich`: For enhanced console output in `agora-manager.py` (optional; falls back to plain input if not installed).

No additional installations are needed beyond these. Built-in modules like `re`, `base64`, `hmac`, `hashlib`, `struct`, `time`, `os`, `random`, `subprocess`, `webbrowser`, and `json` are used.

### Environment Variables
Create a `.env` file in the root directory for sensitive credentials (loaded automatically by `agora-manager.py`). Example:

```
AGORA_CUSTOMER_KEY=your_customer_key_here
AGORA_CUSTOMER_SECRET=your_customer_secret_here
AGORA_APP_CERT=your_app_certificate_hex_here  # Optional: Hex string from Agora Console (Primary Certificate)
```

- If `.env` is not present, scripts will prompt for inputs where needed.
- **How to get Agora Customer Key and Secret**: Follow the instructions in the [Agora Docs](https://docs.agora.io/en/signaling/rest-api/restful-authentication) to generate them in the Agora Console under Developer Toolkit > RESTful API.
- **Security Note**: Never commit `.env` to version control. Use environment variables in production.

## viewer.py

### Description
A simple Streamlit app that embeds an HTML/JS viewer for Agora live streams. It validates inputs, provides debug tools for App ID, and displays the stream with real-time stats (e.g., resolution, bitrate, latency).

### Usage
1. Run the app:
   ```bash
   streamlit run viewer.py
   ```
2. Open the provided URL (e.g., http://localhost:8501) in your browser.
3. Enter:
   - App ID: Your 32-character hex Agora App ID.
   - Channel Name: The channel to join (e.g., "clubCast1").
   - RTC Token: A valid token for the channel (generate using `generate_keys.py` or Agora Console).
4. Click "Start Viewing" to load the stream.
5. Use "Test App ID Validity" for debugging.

**Notes**:
- The viewer uses Agora's Web SDK (loaded via CDN).
- Supports multi-user streams with stats updated every 5 seconds.
- No `.env` required; all inputs are via the UI.

## generate_keys.py

### Description
A CLI tool for generating Agora streaming keys (for pushing streams) and RTC tokens (for joining channels). It uses a modular `AgoraAPI` class that can be imported/extended in other scripts.

**Warning**: The App Certificate is hardcoded in the script as a hex string (`f76e8ace079b47deb51d9703a1ca925a`). Replace this with your actual Primary Certificate from the Agora Console before use.

### Usage
Run with Python and provide arguments via CLI. Examples:

1. Generate a single streaming key:
   ```bash
   python generate_keys.py --customer_key YOUR_KEY --customer_secret YOUR_SECRET --app_id YOUR_APP_ID --region na stream_key --channel_name clubCast1 --uid 0 --expires 3600
   ```
   - Outputs: `Streaming Key: <key>`

2. Generate batch streaming keys for multiple UIDs:
   ```bash
   python generate_keys.py --customer_key YOUR_KEY --customer_secret YOUR_SECRET --app_id YOUR_APP_ID --region na stream_key --channel_name clubCast1 --batch_uids uid1 uid2 uid3 --expires 3600
   ```
   - Outputs: Keys for each UID.

3. Generate an RTC token:
   ```bash
   python generate_keys.py --customer_key YOUR_KEY --customer_secret YOUR_SECRET --app_id YOUR_APP_ID --region na rtc_token --channel_name clubCast1 --uid 0 --role 2 --expires 3600
   ```
   - Outputs: `RTC Token: <token>`
   - `--role`: 1 for host (publisher), 2 for audience (default).

**Arguments**:
- `--customer_key`, `--customer_secret`, `--app_id`, `--region`: Required for all commands.
- Subcommands: `stream_key` or `rtc_token`.
- No `.env` support; pass via CLI for security.

## agora-manager.py

### Description
An interactive CLI tool for managing Agora projects. Features include listing active App IDs and streams, generating keys/tokens, monitoring channel details (users/hosts), and opening the Agora Console in a browser. Uses a modular `AgoraAPI` class.

### Usage
1. Run the script:
   ```bash
   python agora-manager.py
   ```
2. It loads `.env` if present; otherwise, prompts for Customer Key/Secret.
3. Menu options:
   - 1: List App IDs and active streams (with user/host counts).
   - 2: Delete App ID (opens Console; manual action required).
   - 3: Add new App ID (opens Console for creation, then generates key/token).
   - 4: Open stream viewer (runs `viewer.py` in background and opens browser).
   - 5: Open Agora Console.
   - 0: Exit.

**Notes**:
- Requires `.env` for non-interactive use (or prompts).
- For option 3, you'll need the App Certificate (from `.env` or prompt).
- Uses `rich` for colored prompts if installed.
- Opens browser for Console interactions (requires `webbrowser` support).

## Troubleshooting
- **API Errors**: Check Agora Console for project status (active, RTC-enabled). Wait 15 mins after creating new projects.
- **Invalid Tokens/Keys**: Regenerate via script or Console. Ensure App Cert is correct.
- **No Streams Visible**: Ensure a host is publishing to the channel (use Agora's sample apps or FFmpeg for testing).
- **Network Issues**: Scripts use HTTPS; check your firewall/proxy.

For more details, refer to [Agora Documentation](https://docs.agora.io/). If extending to a web app (e.g., Flask), import the `AgoraAPI` classes. Contributions welcome!
