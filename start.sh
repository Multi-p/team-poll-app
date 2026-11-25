#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINKS_FILE="$APP_DIR/active_links.txt"

echo "Starting Dynamic Team Poll App via systemd service..."
systemctl --user daemon-reload
systemctl --user restart team-poll.service
systemctl --user enable team-poll.service 2>/dev/null || true

echo "Waiting for Cloudflare tunnel connection..."
for i in {1..20}; do
    sleep 1
    if [ -f "$LINKS_FILE" ]; then
        if grep -q "PUBLIC_APP_URL" "$LINKS_FILE"; then
            break
        fi
    fi
done

echo ""
echo "========================================================="
echo "🎉 DYNAMIC TEAM POLL APP IS LIVE & RUNNING!"
echo "========================================================="
if [ -f "$LINKS_FILE" ]; then
    source "$LINKS_FILE"
    echo "🌐 PUBLIC DASHBOARD (Create & manage any polls):"
    echo "  👉 $PUBLIC_APP_URL"
    echo ""
    echo "🏠 LOCAL DASHBOARD:"
    echo "  👉 $LOCAL_APP_URL"
    echo ""
    echo "💡 You can create as many polls as you want on this dashboard."
    echo "   Each poll gets its own unique Vote Link and Results Link!"
else
    echo "Service started. Run ./status.sh in a few seconds to view the public links."
fi
echo "========================================================="
