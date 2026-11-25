#!/bin/bash
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINKS_FILE="$APP_DIR/active_links.txt"

systemctl --user status team-poll.service --no-pager

if [ -f "$LINKS_FILE" ]; then
    source "$LINKS_FILE"
    echo ""
    echo "========================================================="
    echo "🎉 TEAM POLL APP IS LIVE & RUNNING!"
    echo "========================================================="
    echo "🌐 PUBLIC LINKS (Accessible anywhere):"
    echo "  👉 Poll Creator & Dashboard: $PUBLIC_APP_URL"
    echo ""
    echo "🏠 LOCAL NETWORK LINKS:"
    echo "  👉 Poll Creator & Dashboard: $LOCAL_APP_URL"
    echo "========================================================="
fi
