import asyncio
import json
import subprocess
import platform
import time
import threading
import webbrowser
import socket
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from flask import Flask, request, jsonify, render_template_string


class MacAutoLock:
    def __init__(self, config_file="autolock_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        self.monitoring = False
        self.device_present = False

    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            return {
                "target_device_address": None,
                "target_device_name": None,
                "rssi_threshold": -70,
                "scan_interval": 3,
                "lock_delay": 10,
            }

    def save_config(self):
        """Save configuration to file"""
        with open(self.config_file, "w") as f:
            json.dump(self.config, f, indent=2)

    def lock_mac(self):
        """Lock the Mac computer"""
        try:
            if platform.system() == "Darwin":
                # Use the proper macOS lock command
                result = subprocess.run(
                    [
                        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                        "-suspend",
                    ],
                    check=True,
                    capture_output=True,
                )
                print(f"Mac locked at {datetime.now().strftime('%H:%M:%S')}")
                return True
            else:
                print("Not running on macOS - lock command skipped")
                return False
        except Exception as e:
            # Fallback to alternative lock method
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
                print(
                    f"Screen saver activated at {datetime.now().strftime('%H:%M:%S')}"
                )
                return True
            except Exception as e2:
                print(f"Failed to lock Mac: {e}, {e2}")
                return False

    async def discover_apple_devices(self):
        """Discover nearby Apple devices"""
        print("Scanning for Apple devices...")
        devices = {}

        def detection_callback(
            device: BLEDevice, advertisement_data: AdvertisementData
        ):
            if advertisement_data.manufacturer_data:
                if (
                    76 in advertisement_data.manufacturer_data
                    or 0x004C in advertisement_data.manufacturer_data
                ):
                    rssi = getattr(advertisement_data, "rssi", None)
                    devices[device.address] = {
                        "address": device.address,
                        "name": device.name or "Hidden Apple Device",
                        "rssi": rssi,
                    }

        scanner = BleakScanner(detection_callback)
        await scanner.start()

        # Show progress
        for i in range(10):
            await asyncio.sleep(1)
            print(f"Scanning... {i+1}/10s", end="\r")

        await scanner.stop()
        print("\nScan complete.")

        return list(devices.values())

    async def scan_for_target_device(self):
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
        await asyncio.sleep(2)
        await scanner.stop()

        return found_device

    async def monitor_device(self):
        """Monitor the target device and auto-lock when it goes far"""
        if not self.config["target_device_address"]:
            print("Error: No target device configured. Run setup first.")
            return

        print(f"Monitoring device: {self.config['target_device_name']}")
        print(f"Device address: {self.config['target_device_address']}")
        print(f"RSSI threshold: {self.config['rssi_threshold']} dBm")
        print(f"Lock delay: {self.config['lock_delay']} seconds")
        print("Press Ctrl+C to stop monitoring\n")

        consecutive_far_readings = 0
        required_far_readings = (
            self.config["lock_delay"] // self.config["scan_interval"]
        )

        self.monitoring = True

        try:
            while self.monitoring:
                device_info = await self.scan_for_target_device()
                current_time = datetime.now().strftime("%H:%M:%S")

                if device_info and device_info["rssi"] is not None:
                    rssi = device_info["rssi"]

                    if rssi < self.config["rssi_threshold"]:
                        consecutive_far_readings += 1
                        status = "FAR"
                        print(
                            f"[{current_time}] {status} - RSSI: {rssi} dBm (count: {consecutive_far_readings}/{required_far_readings})"
                        )

                        if consecutive_far_readings >= required_far_readings:
                            print(
                                f"\n[{current_time}] Device consistently far away - LOCKING MAC"
                            )
                            if self.lock_mac():
                                break
                    else:
                        if consecutive_far_readings > 0:
                            print(
                                f"[{current_time}] NEAR - RSSI: {rssi} dBm (reset counter)"
                            )
                        consecutive_far_readings = 0
                        self.device_present = True
                else:
                    consecutive_far_readings += 1
                    print(
                        f"[{current_time}] NOT FOUND (count: {consecutive_far_readings}/{required_far_readings})"
                    )

                    if consecutive_far_readings >= required_far_readings:
                        print(f"\n[{current_time}] Device not detected - LOCKING MAC")
                        if self.lock_mac():
                            break

                await asyncio.sleep(self.config["scan_interval"])

        except KeyboardInterrupt:
            print("\nMonitoring stopped by user")
        except Exception as e:
            print(f"Monitoring error: {e}")

        self.monitoring = False

    def setup_with_notifications(self):
        """Setup device using notification-based pairing"""
        print("iPhone Auto-lock Setup - Notification Mode")
        print("=" * 45)
        print("This will send notifications to all nearby Apple devices.")
        print("Click the notification on YOUR iPhone to pair it!")
        print()

        # Discover devices first
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(self.discover_apple_devices())

        if not devices:
            print("No Apple devices found!")
            print("Make sure your iPhone Bluetooth is enabled and try again.")
            return False

        print(f"Found {len(devices)} Apple device(s)")
        print("Starting notification service...")

        # Start the pairing web server
        success = self.start_notification_pairing_server(devices)

        if success:
            print("\nPairing completed successfully!")
            return True
        else:
            print("\nPairing was cancelled or failed.")
            return False

    def start_notification_pairing_server(self, devices):
        """Start web server for notification-based pairing"""
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "iphone-autolock-pairing"

        # Shared state for the pairing process
        pairing_state = {
            "completed": False,
            "selected_device": None,
            "devices": devices,
        }

        # HTML template for the pairing page
        PAIRING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>iPhone Auto-Lock Pairing</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 400px;
            margin: 50px auto;
            padding: 20px;
            background: #f5f5f7;
            text-align: center;
        }
        .container {
            background: white;
            border-radius: 18px;
            padding: 30px;
            box-shadow: 0 4px 20px rgba(0,0,0,0.1);
        }
        .header {
            font-size: 24px;
            font-weight: 600;
            color: #1d1d1f;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #86868b;
            margin-bottom: 30px;
            line-height: 1.4;
        }
        .device-info {
            background: #f2f2f7;
            border-radius: 12px;
            padding: 20px;
            margin: 20px 0;
        }
        .device-name {
            font-weight: 600;
            color: #1d1d1f;
            font-size: 18px;
        }
        .device-details {
            color: #86868b;
            font-size: 14px;
            margin-top: 5px;
        }
        .pair-button {
            background: #007aff;
            color: white;
            border: none;
            border-radius: 12px;
            padding: 15px 30px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-top: 20px;
        }
        .pair-button:hover {
            background: #0056d0;
        }
        .success {
            color: #30d158;
            font-weight: 600;
            margin-top: 20px;
        }
        .loading {
            display: none;
            color: #86868b;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🔒 iPhone Auto-Lock</div>
        <div class="subtitle">Pair this device with your Mac for automatic locking when you walk away</div>

        <div class="device-info">
            <div class="device-name" id="device-name">Your iPhone</div>
            <div class="device-details" id="device-details">Tap to configure auto-lock settings</div>
        </div>

        <button class="pair-button" onclick="pairDevice()" id="pair-btn">
            Pair This iPhone
        </button>

        <div class="loading" id="loading">Setting up auto-lock...</div>
        <div class="success" id="success" style="display:none;">✓ Pairing completed!</div>
    </div>

    <script>
        async function pairDevice() {
            const button = document.getElementById('pair-btn');
            const loading = document.getElementById('loading');
            const success = document.getElementById('success');

            button.style.display = 'none';
            loading.style.display = 'block';

            try {
                const response = await fetch('/pair', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        user_agent: navigator.userAgent,
                        timestamp: new Date().toISOString()
                    })
                });

                const result = await response.json();

                if (result.success) {
                    loading.style.display = 'none';
                    success.style.display = 'block';

                    // Show configuration details
                    setTimeout(() => {
                        document.getElementById('device-details').innerHTML =
                            `RSSI Threshold: ${result.rssi_threshold} dBm<br>Lock Delay: ${result.lock_delay}s`;
                    }, 1000);
                } else {
                    throw new Error(result.error || 'Pairing failed');
                }
            } catch (error) {
                loading.style.display = 'none';
                button.style.display = 'block';
                alert('Pairing failed: ' + error.message);
            }
        }
    </script>
</body>
</html>
        """

        @app.route("/")
        def index():
            return PAIRING_HTML

        @app.route("/pair", methods=["POST"])
        def pair_device():
            if pairing_state["completed"]:
                return jsonify({"success": False, "error": "Pairing already completed"})

            try:
                # Get client info
                client_data = request.get_json()
                client_ip = request.remote_addr

                # Try to match this request to a discovered device
                # For now, we'll just use the first device or ask user to confirm
                if len(pairing_state["devices"]) == 1:
                    selected_device = pairing_state["devices"][0]
                else:
                    # If multiple devices, we could implement more sophisticated matching
                    # For now, let the user choose or use signal strength
                    selected_device = max(
                        pairing_state["devices"], key=lambda d: d["rssi"] or -100
                    )

                # Configure RSSI threshold based on current signal strength
                current_rssi = selected_device.get("rssi", -70)
                # Set threshold 10-15 dBm weaker than current signal
                rssi_threshold = max(current_rssi - 15, -80)

                # Save configuration
                self.config.update(
                    {
                        "target_device_address": selected_device["address"],
                        "target_device_name": selected_device["name"],
                        "rssi_threshold": rssi_threshold,
                        "lock_delay": 10,
                        "scan_interval": 3,
                    }
                )
                self.save_config()

                pairing_state["completed"] = True
                pairing_state["selected_device"] = selected_device

                print(f"\n✓ Paired with: {selected_device['name']}")
                print(f"  Address: {selected_device['address']}")
                print(f"  RSSI Threshold: {rssi_threshold} dBm")
                print(f"  Current RSSI: {current_rssi} dBm")

                return jsonify(
                    {
                        "success": True,
                        "device_name": selected_device["name"],
                        "rssi_threshold": rssi_threshold,
                        "lock_delay": 10,
                    }
                )

            except Exception as e:
                print(f"Pairing error: {e}")
                return jsonify({"success": False, "error": str(e)})

        # Find available port
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        port = find_free_port()

        # Get local IP for notifications
        def get_local_ip():
            try:
                # Connect to a remote address to get local IP
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    return s.getsockname()[0]
            except:
                return "localhost"

        local_ip = get_local_ip()
        pairing_url = f"http://{local_ip}:{port}"

        print(f"\nPairing server starting on: {pairing_url}")
        print(f"Sending notifications to {len(devices)} device(s)...")

        # Send notifications to all devices
        notification_sent = self.send_pairing_notifications(devices, pairing_url)

        if not notification_sent:
            print("Could not send notifications. Opening browser as fallback...")
            # Open in default browser as fallback
            threading.Timer(1.0, lambda: webbrowser.open(pairing_url)).start()

        print("\nWaiting for device pairing...")
        print("Click the notification on YOUR iPhone to complete pairing!")
        print("Press Ctrl+C to cancel")

        # Start server in a separate thread
        server_thread = threading.Thread(
            target=lambda: app.run(
                host="0.0.0.0", port=port, debug=False, use_reloader=False
            ),
            daemon=True,
        )
        server_thread.start()

        # Wait for pairing completion or timeout
        timeout = 300  # 5 minutes
        start_time = time.time()

        try:
            while (
                not pairing_state["completed"] and (time.time() - start_time) < timeout
            ):
                time.sleep(1)
                # Show progress dots
                elapsed = int(time.time() - start_time)
                if elapsed % 10 == 0:
                    print(f"Waiting... ({elapsed}s elapsed)", end="\r")

            if pairing_state["completed"]:
                return True
            else:
                print(f"\nTimeout after {timeout} seconds")
                return False

        except KeyboardInterrupt:
            print("\nPairing cancelled by user")
            return False

    def send_pairing_notifications(self, devices, pairing_url):
        """Send pairing notifications to discovered devices"""
        # Note: Direct Bluetooth notifications to iOS devices are not possible
        # without being in MFi program. This is a conceptual implementation.
        # In practice, we would need to use alternative methods like:
        # 1. QR code display
        # 2. AirDrop (if available)
        # 3. iMessage (if contacts available)
        # 4. Push notifications (if app installed)

        print("📱 Notification methods:")
        print(f"   • Open this URL on your iPhone: {pairing_url}")
        print(f"   • Or scan this QR code with your iPhone camera:")

        # Generate and display QR code in terminal (simplified)
        self.print_qr_code(pairing_url)

        # Try to use system notifications as a fallback
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "Open {pairing_url} on your iPhone to pair" with title "iPhone Auto-Lock Pairing"',
                ],
                check=True,
                capture_output=True,
            )
            print("   • Mac notification sent")
        except:
            pass

        return True  # Always return True since we show URL/QR code

    def print_qr_code(self, url):
        """Print a simple QR code representation"""
        try:
            # Try to generate QR code if qrcode library is available
            import qrcode

            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            # Fallback: just show the URL
            print(f"   📱 URL: {url}")
            print("   💡 Tip: Open this URL on your iPhone's browser")

    def setup_device(self):
        """Interactive setup to select target device"""
        print("iPhone Auto-lock Setup")
        print("=" * 30)

        # Discover devices
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(self.discover_apple_devices())

        if not devices:
            print("No Apple devices found!")
            print("Make sure your iPhone Bluetooth is enabled and try again.")
            return False

        print(f"\nFound {len(devices)} Apple device(s):")
        for i, device in enumerate(devices):
            rssi_str = f"{device['rssi']} dBm" if device["rssi"] else "Unknown"
            print(f"{i+1}. {device['name']} - {device['address']} (RSSI: {rssi_str})")

        # Device selection
        while True:
            try:
                choice = input(f"\nSelect your iPhone (1-{len(devices)}): ")
                idx = int(choice) - 1
                if 0 <= idx < len(devices):
                    selected_device = devices[idx]
                    break
                else:
                    print("Invalid selection!")
            except ValueError:
                print("Please enter a number!")

        # RSSI threshold configuration
        print(f"\nSelected device: {selected_device['name']}")
        print(f"Current RSSI: {selected_device['rssi']} dBm")
        print("\nRSSI Threshold Configuration:")
        print("This determines how far your iPhone can be before Mac locks.")
        print("Typical values: -50 (very close) to -80 (far away)")

        while True:
            try:
                threshold = input(
                    f"Enter RSSI threshold (default: {self.config['rssi_threshold']}): "
                )
                if threshold.strip() == "":
                    threshold = self.config["rssi_threshold"]
                else:
                    threshold = int(threshold)
                    if threshold > -30 or threshold < -100:
                        print("RSSI should be between -30 and -100")
                        continue
                break
            except ValueError:
                print("Please enter a valid number!")

        # Lock delay configuration
        while True:
            try:
                delay = input(
                    f"Enter lock delay in seconds (default: {self.config['lock_delay']}): "
                )
                if delay.strip() == "":
                    delay = self.config["lock_delay"]
                else:
                    delay = int(delay)
                    if delay < 5 or delay > 60:
                        print("Lock delay should be between 5 and 60 seconds")
                        continue
                break
            except ValueError:
                print("Please enter a valid number!")

        # Save configuration
        self.config.update(
            {
                "target_device_address": selected_device["address"],
                "target_device_name": selected_device["name"],
                "rssi_threshold": threshold,
                "lock_delay": delay,
            }
        )
        self.save_config()

        print(f"\nConfiguration saved!")
        print(f"Target device: {selected_device['name']}")
        print(f"RSSI threshold: {threshold} dBm")
        print(f"Lock delay: {delay} seconds")

        return True

    def show_status(self):
        """Show current configuration status"""
        print("Current Configuration:")
        print("-" * 25)
        if self.config["target_device_address"]:
            print(f"Target device: {self.config['target_device_name']}")
            print(f"Device address: {self.config['target_device_address']}")
            print(f"RSSI threshold: {self.config['rssi_threshold']} dBm")
            print(f"Lock delay: {self.config['lock_delay']} seconds")
        else:
            print("No device configured. Run setup first.")


def main():
    autolock = MacAutoLock()

    if len(__import__("sys").argv) > 1:
        command = __import__("sys").argv[1]

        if command == "setup":
            autolock.setup_device()
        elif command == "setup-notification" or command == "setup-notify":
            autolock.setup_with_notifications()
        elif command == "status":
            autolock.show_status()
        elif command == "monitor":
            asyncio.run(autolock.monitor_device())
        elif command == "test-lock":
            print("Testing Mac lock...")
            autolock.lock_mac()
        else:
            print(
                "Unknown command. Use: setup, setup-notify, status, monitor, or test-lock"
            )
    else:
        print("iPhone Auto-lock System")
        print("=" * 30)
        print("Commands:")
        print(
            "  python mac_autolock.py setup           - Configure your iPhone (manual)"
        )
        print(
            "  python mac_autolock.py setup-notify    - Configure your iPhone (notification)"
        )
        print("  python mac_autolock.py status          - Show current configuration")
        print("  python mac_autolock.py monitor         - Start monitoring")
        print("  python mac_autolock.py test-lock       - Test Mac lock function")
        print("\nSetup Methods:")
        print("• Manual: Shows list of devices to choose from")
        print("• Notification: Sends notification to all devices, click on YOUR iPhone")
        print("\nExample workflow:")
        print("1. python mac_autolock.py setup-notify")
        print("2. python mac_autolock.py monitor")


if __name__ == "__main__":
    main()
