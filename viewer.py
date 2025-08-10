import re
import requests
import streamlit as st

# Modular helpers (unchanged)
def validate_app_id(app_id: str) -> bool:
    return bool(re.match(r'^[0-9a-fA-F]{32}$', app_id))

def validate_token(token: str) -> bool:
    return len(token) > 50 and re.match(r'^[A-Za-z0-9+/=]+$', token) is not None

def debug_app_id(app_id: str) -> str:
    try:
        url = f"https://api.agora.io/dev/v1/project/{app_id}"
        response = requests.get(url)
        if response.status_code == 200:
            return "App ID is valid and active."
        elif response.status_code == 404:
            return "App ID not found or invalid (check Console)."
        elif response.status_code == 401:
            return "Project exists but may not be enabled for RTC/Web."
        else:
            return f"Error {response.status_code}: {response.text} (try waiting 15 mins if new project)."
    except Exception as e:
        return f"Debug failed: {str(e)} (network issue?)"

# Modular viewer HTML (fixed JS embedding in f-string by escaping braces)
def agora_viewer_html(app_id: str, channel_name: str, token: str, container_id: str = "video") -> str:
    return f"""
    <html>
    <head>
        <script src="https://download.agora.io/sdk/release/AgoraRTC_N.js"></script>
        <style> #{container_id} {{ width: 100%; height: 500px; background: black; }} #stats-log {{ color: green; font-family: monospace; }} </style>
    </head>
    <body>
        <div id="{container_id}"></div>
        <div id="error-log" style="color: red;"></div>
        <div id="stats-log"></div>
        <script>
            let client;  // Global for stats access
            let subscribedUsers = [];  // Track for multi-user stats
            async function startViewer() {{
                try {{
                    client = AgoraRTC.createClient({{ mode: 'live', codec: 'vp8' }});
                    await client.join('{app_id}', '{channel_name}', '{token}', null);
                    await client.setClientRole('audience');
                    client.enableDualStream();

                    client.on('user-published', async (user, mediaType) => {{
                        await client.subscribe(user, mediaType);
                        if (mediaType === 'video') {{
                            subscribedUsers.push(user.uid);
                            await client.setRemoteVideoStreamType(user.uid, 1);
                            const options = {{ playoutDelayHint: 100 }};
                            user.videoTrack.play('{container_id}', options);
                        }} else if (mediaType === 'audio') {{
                            user.audioTrack.play();
                        }}
                        initStats();  // Start stats after first subscribe
                    }});

                    client.on('user-unpublished', (user, mediaType) => {{
                        console.log('User unpublished:', user.uid, mediaType);
                        subscribedUsers = subscribedUsers.filter(uid => uid !== user.uid);
                    }});
                }} catch (err) {{
                    document.getElementById('error-log').innerText = 'Error: ' + err.message;
                    console.error('Viewer error:', err);
                }}
            }}

            function initStats() {{
                if (!client) return;
                setInterval(() => {{
                    let statsText = 'Stream Stats:\\n';
                    const networkQuality = client.getRemoteNetworkQuality();
                    const videoStats = client.getRemoteVideoStats();
                    subscribedUsers.forEach(uid => {{
                        const vStats = videoStats[uid] || {{}};
                        const nQuality = networkQuality[uid] || {{}};
                        statsText += `UID ${{uid}}:\\n`;
                        statsText += `  Resolution: ${{vStats.receiveResolutionWidth || 'N/A'}}x${{vStats.receiveResolutionHeight || 'N/A'}}\\n`;
                        statsText += `  Data Rate: ${{vStats.receiveBitrate || 'N/A'}} kbps\\n`;
                        statsText += `  Packet Loss: ${{vStats.packetLossRate || 'N/A'}}%\\n`;
                        statsText += `  Dropped Frames: ${{vStats.totalFrozenTime || 'N/A'}}s frozen, ${{vStats.freezeRate || 'N/A'}}% freeze rate\\n`;
                        statsText += `  Latency: ${{vStats.endToEndDelay || 'N/A'}}ms, Jitter: ${{vStats.jitter || 'N/A'}}ms\\n`;
                        statsText += `  Network Quality: Uplink ${{nQuality.uplinkNetworkQuality || 'N/A'}}, Downlink ${{nQuality.downlinkNetworkQuality || 'N/A'}}\\n`;
                    }});
                    document.getElementById('stats-log').innerText = statsText;
                    console.log(statsText);
                }}, 5000);  // Update every 5s for reactivity
            }}
            startViewer();
        </script>
    </body>
    </html>
    """

# Reactive UI (unchanged)
st.title("Agora Stream Viewer")
app_id = st.text_input("App ID", value="")
channel_name = st.text_input("Channel Name", value="clubCast1")
token = st.text_input("RTC Token", type="password")

if app_id and not validate_app_id(app_id):
    st.error("Invalid App ID format: 32 hex chars. Copy exactly from Console.")
if token and not validate_token(token):
    st.error("Invalid Token format: Regenerate via script or Console.")

st.subheader("Debug Tools")
if st.button("Test App ID Validity"):
    if validate_app_id(app_id):
        result = debug_app_id(app_id)
        st.info(result)
    else:
        st.error("Fix App ID format first.")

if st.button("Start Viewing", disabled=not (app_id and validate_app_id(app_id) and channel_name and token)):
    html_code = agora_viewer_html(app_id, channel_name, token)
    st.components.v1.html(html_code, height=600)
elif not (app_id and channel_name and token):
    st.error("Enter all fields.")