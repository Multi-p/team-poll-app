#!/bin/bash
echo "Stopping Team Poll App service..."
systemctl --user stop team-poll.service
echo "✓ Service stopped."
