#!/bin/bash

# Prompt for the video device, default to /dev/video0
read -p "Enter the video device (default: /dev/video0): " video_device
video_device=${video_device:-/dev/video0}

# Prompt for the stream key
read -p "Enter the stream key: " stream_key

# Construct the RTMP URL
rtmp_url="rtmp://rtls-ingress-prod-na.agoramdn.com/live/$stream_key"

# Run the ffmpeg command
ffmpeg -f v4l2 -framerate 30 -video_size 1280x720 -i "$video_device" \
 -pix_fmt yuv420p -c:v libx264 -preset ultrafast -profile:v baseline -g 60 -threads 6 -b:v 2500k \
 -f flv "$rtmp_url"
