#!/bin/bash
"""
RSSI Monitor Service Manager
Manages the continuous RSSI monitoring as a background service
"""

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/bluetooth_env"
PYTHON_SCRIPT="$SCRIPT_DIR/rssi_monitor.py"
PID_FILE="$SCRIPT_DIR/rssi_monitor.pid"
LOG_FILE="$SCRIPT_DIR/rssi_monitor.log"

case "$1" in
    start)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "RSSI Monitor is already running (PID: $PID)"
                exit 1
            else
                rm -f "$PID_FILE"
            fi
        fi

        echo "Starting RSSI Monitor..."
        source "$VENV_DIR/bin/activate"
        nohup python "$PYTHON_SCRIPT" start > /dev/null 2>&1 &
        echo $! > "$PID_FILE"
        echo "RSSI Monitor started (PID: $(cat $PID_FILE))"
        echo "View logs with: python rssi_monitor.py logs"
        ;;

    stop)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "Stopping RSSI Monitor (PID: $PID)..."
                kill -TERM "$PID"
                sleep 2
                if kill -0 "$PID" 2>/dev/null; then
                    echo "Process still running, force killing..."
                    kill -KILL "$PID"
                fi
                rm -f "$PID_FILE"
                echo "RSSI Monitor stopped"
            else
                echo "RSSI Monitor is not running"
                rm -f "$PID_FILE"
            fi
        else
            echo "RSSI Monitor is not running"
        fi
        ;;

    restart)
        $0 stop
        sleep 2
        $0 start
        ;;

    status)
        if [ -f "$PID_FILE" ]; then
            PID=$(cat "$PID_FILE")
            if kill -0 "$PID" 2>/dev/null; then
                echo "RSSI Monitor is running (PID: $PID)"
                echo "Uptime: $(ps -o etime= -p $PID | tr -d ' ')"
                echo "Log file: $LOG_FILE"
                echo "Recent activity:"
                tail -n 5 "$LOG_FILE" 2>/dev/null || echo "No recent logs"
            else
                echo "RSSI Monitor is not running (stale PID file)"
                rm -f "$PID_FILE"
            fi
        else
            echo "RSSI Monitor is not running"
        fi
        ;;

    logs)
        LINES=${2:-20}
        if [ -f "$LOG_FILE" ]; then
            tail -n "$LINES" "$LOG_FILE"
        else
            echo "No log file found"
        fi
        ;;

    follow)
        if [ -f "$LOG_FILE" ]; then
            tail -f "$LOG_FILE"
        else
            echo "No log file found"
        fi
        ;;

    *)
        echo "RSSI Monitor Service Manager"
        echo "Usage: $0 {start|stop|restart|status|logs [n]|follow}"
        echo ""
        echo "Commands:"
        echo "  start    - Start the RSSI monitor in background"
        echo "  stop     - Stop the RSSI monitor"
        echo "  restart  - Restart the RSSI monitor"
        echo "  status   - Show current status"
        echo "  logs [n] - Show last n log entries (default: 20)"
        echo "  follow   - Follow log output in real-time"
        exit 1
        ;;
esac
