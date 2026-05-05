#!/bin/bash
# Auto-update dev-archaeology dashboard
cd /Users/simongonzalezdecruz/workspaces/dev-archaeology

# Pull latest changes
git pull --rebase --quiet 2>/dev/null

# Restart the serve process if it's not running
if ! lsof -i :8099 > /dev/null 2>&1; then
    nohup python3 -m archaeology.cli serve --no-open --port 8099 > /dev/null 2>&1 &
    sleep 2
fi
