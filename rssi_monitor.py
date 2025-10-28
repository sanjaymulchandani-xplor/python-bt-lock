import asyncio
import json
import subprocess
import platform
import time
import signal
import sys
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


class ContinuousRSSIMonitor:
    def __init__(self, config_file="autolock_config.json", log_file="rssi_monitor.log"):
        self.config_file = Path(config_file)
        self.log_file = Path(log_file)
        self.config = self.load_config()
        self.monitoring = False
        self.last_rssi = None
        self.consecutive_readings = 0
        self.start_time = datetime.now()

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            print(
                "Error: No configuration found. Run 'python mac_autolock.py setup' first."
            )
            sys.exit(1)

    def signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        print(f"\nReceived signal {signum}. Shutting down gracefully...")
        self.monitoring = False

    def log_message(self, message, also_print=True):
        """Log message to file and optionally print to console"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"

        # Write to log file
        with open(self.log_file, "a") as f:
            f.write(log_entry + "\n")

        # Print to console if requested
        if also_print:
            print(log_entry)

    def lock_mac(self):
        """Lock the Mac computer"""
        try:
            if platform.system() == "Darwin":
                subprocess.run(
                    [
                        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                        "-suspend",
                    ],
                    check=True,
                    capture_output=True,
                )
                return True
            else:
                return False
        except Exception:
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to start current screen saver',
                    ],
                    check=True,
                    capture_output=True,
                )
                return True
            except Exception:
                return False

    async def scan_for_device(self):
        """Scan for the target device and return its current RSSI"""
        if not self.config["target_device_address"]:
            return None

        found_device = None
        target_address = self.config["target_device_address"]

        def detection_callback(
            device: BLEDevice, advertisement_data: AdvertisementData
        ):
            nonlocal found_device
            if device.address == target_address:
                rssi = getattr(advertisement_data, "rssi", None)
                found_device = {
                    "address": device.address,
                    "name": device.name
                    or self.config.get("target_device_name", "iPhone"),
                    "rssi": rssi,
                    "timestamp": datetime.now(),
                }

        scanner = BleakScanner(detection_callback)
        await scanner.start()
        await asyncio.sleep(2)  # 2 second scan
        await scanner.stop()

        return found_device

    def get_signal_status(self, rssi):
        """Get human-readable signal status"""
        if rssi is None:
            return "UNKNOWN"
        elif rssi >= -50:
            return "EXCELLENT"
        elif rssi >= -60:
            return "GOOD"
        elif rssi >= -70:
            return "FAIR"
        elif rssi >= -80:
            return "WEAK"
        else:
            return "VERY_WEAK"

    def get_distance_estimate(self, rssi):
        """Estimate distance based on RSSI"""
        if rssi is None:
            return "Unknown"
        elif rssi >= -50:
            return "Very Close (<1m)"
        elif rssi >= -60:
            return "Close (1-3m)"
        elif rssi >= -70:
            return "Moderate (3-10m)"
        elif rssi >= -80:
            return "Far (10-20m)"
        else:
            return "Very Far (>20m)"

    def should_lock(self, rssi):
        """Determine if Mac should be locked based on RSSI"""
        threshold = self.config.get("rssi_threshold", -70)
        lock_delay = self.config.get("lock_delay", 10)

        if rssi is None or rssi < threshold:
            self.consecutive_readings += 1
        else:
            self.consecutive_readings = 0

        required_readings = lock_delay // 5  # 5 second intervals
        return self.consecutive_readings >= required_readings

    async def continuous_monitor(self):
        """Main continuous monitoring loop"""
        device_name = self.config.get("target_device_name", "iPhone")
        device_address = self.config["target_device_address"]
        rssi_threshold = self.config.get("rssi_threshold", -70)

        # Log startup information
        self.log_message("=" * 60)
        self.log_message("CONTINUOUS RSSI MONITOR STARTED")
        self.log_message(f"Target Device: {device_name}")
        self.log_message(f"Device Address: {device_address}")
        self.log_message(f"RSSI Threshold: {rssi_threshold} dBm")
        self.log_message(
            f"Auto-lock: {'ENABLED' if self.config.get('auto_lock_enabled', True) else 'DISABLED'}"
        )
        self.log_message(f"Monitoring interval: 5 seconds")
        self.log_message("=" * 60)

        self.monitoring = True
        reading_count = 0

        try:
            while self.monitoring:
                reading_count += 1
                device_info = await self.scan_for_device()

                if device_info and device_info["rssi"] is not None:
                    rssi = device_info["rssi"]
                    status = self.get_signal_status(rssi)
                    distance = self.get_distance_estimate(rssi)

                    # Check if we should lock
                    should_lock = self.should_lock(rssi)
                    lock_status = ""

                    if should_lock and self.config.get("auto_lock_enabled", True):
                        if self.lock_mac():
                            lock_status = " -> MAC LOCKED"
                            self.log_message(
                                f"AUTO-LOCK TRIGGERED: Signal consistently weak"
                            )
                        else:
                            lock_status = " -> LOCK FAILED"
                    elif self.consecutive_readings > 0:
                        required = self.config.get("lock_delay", 10) // 5
                        lock_status = f" -> Will lock in {(required - self.consecutive_readings) * 5}s"

                    # Log the reading
                    uptime = datetime.now() - self.start_time
                    uptime_str = str(uptime).split(".")[0]  # Remove microseconds

                    message = (
                        f"#{reading_count:04d} | RSSI: {rssi:3d} dBm | {status:10s} | "
                        f"{distance:15s} | Uptime: {uptime_str}{lock_status}"
                    )

                    self.log_message(message)
                    self.last_rssi = rssi

                else:
                    # Device not found
                    should_lock = self.should_lock(None)
                    lock_status = ""

                    if should_lock and self.config.get("auto_lock_enabled", True):
                        if self.lock_mac():
                            lock_status = " -> MAC LOCKED"
                            self.log_message(f"AUTO-LOCK TRIGGERED: Device not found")
                        else:
                            lock_status = " -> LOCK FAILED"
                    elif self.consecutive_readings > 0:
                        required = self.config.get("lock_delay", 10) // 5
                        lock_status = f" -> Will lock in {(required - self.consecutive_readings) * 5}s"

                    uptime = datetime.now() - self.start_time
                    uptime_str = str(uptime).split(".")[0]

                    message = (
                        f"#{reading_count:04d} | DEVICE NOT FOUND | Signal: NONE      | "
                        f"Distance: Unknown    | Uptime: {uptime_str}{lock_status}"
                    )

                    self.log_message(message)
                    self.last_rssi = None

                # Wait 5 seconds before next reading
                await asyncio.sleep(5)

        except Exception as e:
            self.log_message(f"ERROR: {e}")
        finally:
            self.log_message("CONTINUOUS MONITOR STOPPED")
            self.log_message("=" * 60)

    def show_status(self):
        """Show current monitoring status"""
        print("Continuous RSSI Monitor Status")
        print("=" * 40)

        if self.config.get("target_device_address"):
            print(f"Target Device: {self.config.get('target_device_name', 'Unknown')}")
            print(f"Device Address: {self.config['target_device_address']}")
            print(f"RSSI Threshold: {self.config.get('rssi_threshold', -70)} dBm")
            print(
                f"Auto-lock: {'ENABLED' if self.config.get('auto_lock_enabled', True) else 'DISABLED'}"
            )
            print(f"Log File: {self.log_file}")
            print(
                f"Last RSSI: {self.last_rssi} dBm"
                if self.last_rssi
                else "Last RSSI: Not available"
            )

            if self.log_file.exists():
                print(f"Log File Size: {self.log_file.stat().st_size} bytes")
        else:
            print("No device configured. Run setup first.")

    def tail_logs(self, lines=20):
        """Show recent log entries"""
        if not self.log_file.exists():
            print("No log file found.")
            return

        try:
            with open(self.log_file, "r") as f:
                all_lines = f.readlines()
                recent_lines = (
                    all_lines[-lines:] if len(all_lines) > lines else all_lines
                )

                print(f"Last {len(recent_lines)} log entries:")
                print("-" * 80)
                for line in recent_lines:
                    print(line.strip())
        except Exception as e:
            print(f"Error reading log file: {e}")


def main():
    monitor = ContinuousRSSIMonitor()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == "start":
            print("Starting continuous RSSI monitoring...")
            print("Press Ctrl+C to stop")
            asyncio.run(monitor.continuous_monitor())

        elif command == "status":
            monitor.show_status()

        elif command == "logs":
            lines = int(sys.argv[2]) if len(sys.argv) > 2 else 20
            monitor.tail_logs(lines)

        elif command == "enable-autolock":
            monitor.config["auto_lock_enabled"] = True
            with open(monitor.config_file, "w") as f:
                json.dump(monitor.config, f, indent=2)
            print("Auto-lock ENABLED")

        elif command == "disable-autolock":
            monitor.config["auto_lock_enabled"] = False
            with open(monitor.config_file, "w") as f:
                json.dump(monitor.config, f, indent=2)
            print("Auto-lock DISABLED")

        elif command == "clear-logs":
            if monitor.log_file.exists():
                monitor.log_file.unlink()
                print("Log file cleared")
            else:
                print("No log file to clear")

        else:
            print("Unknown command")

    else:
        print("Continuous iPhone RSSI Monitor")
        print("=" * 40)
        print("Commands:")
        print(
            "  python rssi_monitor.py start              - Start continuous monitoring"
        )
        print("  python rssi_monitor.py status             - Show current status")
        print(
            "  python rssi_monitor.py logs [n]           - Show last n log entries (default: 20)"
        )
        print(
            "  python rssi_monitor.py enable-autolock    - Enable automatic Mac locking"
        )
        print(
            "  python rssi_monitor.py disable-autolock   - Disable automatic Mac locking"
        )
        print("  python rssi_monitor.py clear-logs         - Clear log file")
        print()
        print("Example:")
        print("  python rssi_monitor.py start    # Start monitoring")
        print("  python rssi_monitor.py logs 50  # Show last 50 log entries")


if __name__ == "__main__":
    main()
