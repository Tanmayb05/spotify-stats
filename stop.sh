#!/bin/bash

# Spotify Stats - Stop Script
# Stops all running servers and closes Terminal application

echo "🛑 Stopping all servers..."

# Kill all vite processes (frontend)
pkill -f "vite" && echo "  ✓ Frontend stopped"

# Kill all uvicorn processes (backend)
pkill -f "uvicorn app.main:app" && echo "  ✓ Backend stopped"

# Wait a moment for processes to terminate
sleep 1

echo ""
echo "✅ All servers stopped"
echo "🔒 Closing Terminal application..."

# Wait a moment before closing Terminal
sleep 0.5

# Close Terminal application entirely
osascript <<EOF
tell application "Terminal"
    quit
end tell
EOF
