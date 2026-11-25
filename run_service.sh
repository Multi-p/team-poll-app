#!/bin/bash
APP_DIR="/home/rajesh/team-poll-app"
SERVER_PORT=8095
LINKS_FILE="$APP_DIR/active_links.txt"
TUNNEL_LOG="/tmp/team_poll_tunnel.log"
CLOUDFLARED="/home/rajesh/.local/bin/cloudflared"

cleanup() {
    echo "Stopping team-poll services..."
    kill $(jobs -p) 2>/dev/null || true
    exit 0
}
trap cleanup SIGINT SIGTERM SIGHUP

# Start Python server
python3 "$APP_DIR/server.py" "$SERVER_PORT" &
SERVER_PID=$!

sleep 1

# Start Cloudflare Tunnel
rm -f "$TUNNEL_LOG" "$LINKS_FILE"
"$CLOUDFLARED" tunnel --url "http://127.0.0.1:$SERVER_PORT" > "$TUNNEL_LOG" 2>&1 &
TUNNEL_PID=$!

LOCAL_IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$LOCAL_IP" ] && LOCAL_IP="127.0.0.1"

# Extract URL
for i in {1..30}; do
    sleep 1
    PUBLIC_URL=$(grep -oE "https://[a-zA-Z0-9\-]+\.trycloudflare\.com" "$TUNNEL_LOG" 2>/dev/null | grep -v "api.trycloudflare.com" | head -n 1)
    if [ -n "$PUBLIC_URL" ]; then
        cat << EOF > "$LINKS_FILE"
PUBLIC_APP_URL="$PUBLIC_URL"
LOCAL_APP_URL="http://$LOCAL_IP:$SERVER_PORT"
EOF
        echo "Active URLs updated: $PUBLIC_URL"
        break
    fi
done

wait
