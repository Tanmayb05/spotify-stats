#!/bin/bash

# Spotify Stats - Start Script
# Opens Terminal with two tabs: one for backend, one for frontend

PROJECT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

# Create AppleScript to open Terminal with two tabs
osascript <<EOF
tell application "Terminal"
    activate

    -- Create new window with backend tab
    do script "cd '$PROJECT_DIR' && source .venv/bin/activate && cd backend && echo '🚀 Starting Backend on port 3011...' && uvicorn app.main:app --reload --port 3011"

    -- Wait a moment for the window to be created
    delay 0.5

    -- Open new tab in the same window for frontend
    tell application "System Events"
        keystroke "t" using command down
    end tell

    -- Wait for new tab to be ready
    delay 0.5

    -- Execute frontend command in the new tab
    do script "cd '$PROJECT_DIR/frontend' && echo '🎨 Starting Frontend on port 3010...' && npm run dev" in front window

end tell
EOF

echo "✅ Servers starting in Terminal..."
echo ""
echo "📍 Frontend: http://localhost:3010"
echo "📍 Backend:  http://localhost:3011"
echo "📍 API Docs: http://localhost:3011/docs"
echo ""
echo "To stop servers, run: ./stop.sh"
