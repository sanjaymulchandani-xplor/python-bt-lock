import asyncio
import json
import subprocess
import platform
import time
from datetime import datetime, timedelta
from pathlib import Path
from flask import Flask, render_template_string, request, jsonify
import threading
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData


class MacAutoLockSystem:
    def __init__(self, config_file="autolock_config.json"):
        self.config_file = Path(config_file)
        self.config = self.load_config()
        self.target_device = None
        self.monitoring = False
        self.last_seen = None
        self.device_present = False
        self.rssi_threshold = -70  # Default threshold for "far away"

    def load_config(self):
        """Load configuration from file"""
        try:
            with open(self.config_file, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            default_config = {
                "target_device_address": None,
                "target_device_name": None,
                "rssi_threshold": -70,
                "scan_interval": 3,
                "lock_delay": 10,
                "monitoring_enabled": False,
            }
            self.save_config(default_config)
            return default_config

    def save_config(self, config=None):
        """Save configuration to file"""
        if config is None:
            config = self.config
        with open(self.config_file, "w") as f:
            json.dump(config, f, indent=2)

    def set_target_device(self, device_address, device_name):
        """Set the target iPhone device"""
        self.config["target_device_address"] = device_address
        self.config["target_device_name"] = device_name
        self.save_config()
        print(f"Target device set: {device_name} ({device_address})")

    def lock_mac(self):
        """Lock the Mac computer"""
        try:
            if platform.system() == "Darwin":
                # Use the proper macOS lock command
                subprocess.run(
                    [
                        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                        "-suspend",
                    ],
                    check=True,
                )
                print(f"Mac locked at {datetime.now()}")
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
                )
                print(f"Screen saver activated at {datetime.now()}")
                return True
            except Exception as e2:
                print(f"Failed to lock Mac: {e}, {e2}")
                return False

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
        await asyncio.sleep(2)  # Quick scan
        await scanner.stop()

        return found_device

    async def monitor_device(self):
        """Monitor the target device and auto-lock when it goes far"""
        print(f"Starting monitoring for device: {self.config['target_device_address']}")
        print(f"RSSI threshold: {self.rssi_threshold} dBm")
        print(f"Lock delay: {self.config['lock_delay']} seconds")

        consecutive_far_readings = 0
        required_far_readings = (
            self.config["lock_delay"] // self.config["scan_interval"]
        )

        while self.monitoring:
            try:
                device_info = await self.scan_for_target_device()

                if device_info:
                    rssi = device_info["rssi"]
                    self.last_seen = device_info["timestamp"]

                    if rssi is not None:
                        if rssi < self.rssi_threshold:
                            consecutive_far_readings += 1
                            print(
                                f"Device far away: RSSI {rssi} dBm (count: {consecutive_far_readings}/{required_far_readings})"
                            )

                            if consecutive_far_readings >= required_far_readings:
                                print("Device consistently far away - locking Mac")
                                if self.lock_mac():
                                    self.monitoring = (
                                        False  # Stop monitoring after lock
                                    )
                                    break
                        else:
                            consecutive_far_readings = 0
                            if not self.device_present:
                                print(f"Device nearby: RSSI {rssi} dBm")
                            self.device_present = True
                    else:
                        print("Could not determine RSSI")
                else:
                    consecutive_far_readings += 1
                    print(
                        f"Device not found (count: {consecutive_far_readings}/{required_far_readings})"
                    )

                    if consecutive_far_readings >= required_far_readings:
                        print("Device not detected - locking Mac")
                        if self.lock_mac():
                            self.monitoring = False
                            break

                await asyncio.sleep(self.config["scan_interval"])

            except Exception as e:
                print(f"Monitoring error: {e}")
                await asyncio.sleep(5)

        print("Monitoring stopped")

    def start_monitoring(self):
        """Start monitoring in a separate thread"""
        if not self.config["target_device_address"]:
            print("No target device configured")
            return False

        if self.monitoring:
            print("Monitoring already active")
            return False

        self.monitoring = True
        self.config["monitoring_enabled"] = True
        self.save_config()

        # Start monitoring in asyncio loop
        def run_monitor():
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.monitor_device())

        monitor_thread = threading.Thread(target=run_monitor, daemon=True)
        monitor_thread.start()
        return True

    def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring = False
        self.config["monitoring_enabled"] = False
        self.save_config()
        print("Monitoring stopped")

    async def discover_apple_devices(self):
        """Discover nearby Apple devices for identification"""
        print("Scanning for Apple devices...")
        devices = []

        def detection_callback(
            device: BLEDevice, advertisement_data: AdvertisementData
        ):
            if advertisement_data.manufacturer_data:
                if (
                    76 in advertisement_data.manufacturer_data
                    or 0x004C in advertisement_data.manufacturer_data
                ):
                    rssi = getattr(advertisement_data, "rssi", None)
                    devices.append(
                        {
                            "address": device.address,
                            "name": device.name or "Hidden Apple Device",
                            "rssi": rssi,
                        }
                    )

        scanner = BleakScanner(detection_callback)
        await scanner.start()
        await asyncio.sleep(10)  # Longer scan for discovery
        await scanner.stop()

        # Remove duplicates and sort by signal strength
        unique_devices = {}
        for device in devices:
            if device["address"] not in unique_devices:
                unique_devices[device["address"]] = device
            else:
                # Keep the one with better signal
                if device["rssi"] and (
                    not unique_devices[device["address"]]["rssi"]
                    or device["rssi"] > unique_devices[device["address"]]["rssi"]
                ):
                    unique_devices[device["address"]] = device

        sorted_devices = sorted(
            unique_devices.values(),
            key=lambda x: x["rssi"] if x["rssi"] else -999,
            reverse=True,
        )

        return sorted_devices


app = Flask(__name__)
autolock_system = MacAutoLockSystem()

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>iPhone Auto-Lock Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #333; text-align: center; }
        .status { padding: 10px; margin: 10px 0; border-radius: 5px; text-align: center; }
        .status.success { background: #d4edda; color: #155724; border: 1px solid #c3e6cb; }
        .status.warning { background: #fff3cd; color: #856404; border: 1px solid #ffeaa7; }
        .status.error { background: #f8d7da; color: #721c24; border: 1px solid #f5c6cb; }
        .device-list { margin: 20px 0; }
        .device { background: #f8f9fa; margin: 10px 0; padding: 15px; border-radius: 5px; border: 1px solid #e9ecef; }
        .device h3 { margin: 0 0 10px 0; color: #495057; }
        .device-info { font-size: 14px; color: #6c757d; margin: 5px 0; }
        .btn { background: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 5px; cursor: pointer; margin: 5px; }
        .btn:hover { background: #0056b3; }
        .btn.success { background: #28a745; }
        .btn.danger { background: #dc3545; }
        .settings { margin: 20px 0; }
        .setting { margin: 10px 0; }
        .setting label { display: block; margin-bottom: 5px; font-weight: bold; }
        .setting input { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
        .current-device { background: #e7f3ff; border: 2px solid #007bff; }
        .monitoring-active { background: #d4edda; border: 2px solid #28a745; }
    </style>
</head>
<body>
    <div class="container">
        <h1>iPhone Auto-Lock Setup</h1>

        <div id="status" class="status" style="display: none;"></div>

        <div class="settings">
            <h2>Current Configuration</h2>
            <div class="setting">
                <label>Target Device:</label>
                <span id="current-device">{{ config.target_device_name or 'None configured' }}</span>
            </div>
            <div class="setting">
                <label>RSSI Threshold (dBm):</label>
                <input type="number" id="rssi-threshold" value="{{ config.rssi_threshold }}" min="-100" max="-30">
            </div>
            <div class="setting">
                <label>Lock Delay (seconds):</label>
                <input type="number" id="lock-delay" value="{{ config.lock_delay }}" min="5" max="60">
            </div>
        </div>

        <div style="text-align: center; margin: 20px 0;">
            <button class="btn" onclick="discoverDevices()">Discover Apple Devices</button>
            <button class="btn success" onclick="startMonitoring()" id="start-btn">Start Monitoring</button>
            <button class="btn danger" onclick="stopMonitoring()" id="stop-btn">Stop Monitoring</button>
            <button class="btn" onclick="updateSettings()">Update Settings</button>
        </div>

        <div id="device-list" class="device-list"></div>

        <div id="instructions" style="margin-top: 30px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
            <h3>Instructions:</h3>
            <ol>
                <li>Make sure your iPhone's Bluetooth is enabled</li>
                <li>Click "Discover Apple Devices" to scan for nearby devices</li>
                <li>Click "Select This Device" next to your iPhone</li>
                <li>Adjust RSSI threshold and lock delay as needed</li>
                <li>Click "Start Monitoring" to begin auto-lock protection</li>
            </ol>
            <p><strong>Note:</strong> Lower RSSI values mean weaker signal (farther away).
            Typical values: -40 to -60 dBm (close), -70 to -80 dBm (far).</p>
        </div>
    </div>

    <script>
        function showStatus(message, type) {
            const status = document.getElementById('status');
            status.textContent = message;
            status.className = 'status ' + type;
            status.style.display = 'block';
            setTimeout(() => status.style.display = 'none', 5000);
        }

        function discoverDevices() {
            showStatus('Scanning for Apple devices...', 'warning');
            fetch('/discover', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        displayDevices(data.devices);
                        showStatus('Found ' + data.devices.length + ' Apple devices', 'success');
                    } else {
                        showStatus('Error: ' + data.error, 'error');
                    }
                })
                .catch(error => showStatus('Network error', 'error'));
        }

        function displayDevices(devices) {
            const container = document.getElementById('device-list');
            container.innerHTML = '<h2>Discovered Apple Devices</h2>';

            devices.forEach(device => {
                const div = document.createElement('div');
                div.className = 'device';
                div.innerHTML = `
                    <h3>${device.name}</h3>
                    <div class="device-info">Address: ${device.address}</div>
                    <div class="device-info">Signal Strength: ${device.rssi || 'Unknown'} dBm</div>
                    <button class="btn" onclick="selectDevice('${device.address}', '${device.name}')">
                        Select This Device
                    </button>
                `;
                container.appendChild(div);
            });
        }

        function selectDevice(address, name) {
            fetch('/select-device', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ address: address, name: name })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    document.getElementById('current-device').textContent = name;
                    showStatus('Device selected successfully', 'success');
                } else {
                    showStatus('Error selecting device', 'error');
                }
            });
        }

        function startMonitoring() {
            fetch('/start-monitoring', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showStatus('Monitoring started', 'success');
                    } else {
                        showStatus('Error: ' + data.error, 'error');
                    }
                });
        }

        function stopMonitoring() {
            fetch('/stop-monitoring', { method: 'POST' })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showStatus('Monitoring stopped', 'warning');
                    } else {
                        showStatus('Error stopping monitoring', 'error');
                    }
                });
        }

        function updateSettings() {
            const rssiThreshold = document.getElementById('rssi-threshold').value;
            const lockDelay = document.getElementById('lock-delay').value;

            fetch('/update-settings', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    rssi_threshold: parseInt(rssiThreshold),
                    lock_delay: parseInt(lockDelay)
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus('Settings updated', 'success');
                } else {
                    showStatus('Error updating settings', 'error');
                }
            });
        }
    </script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML_TEMPLATE, config=autolock_system.config)


@app.route("/discover", methods=["POST"])
def discover():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(autolock_system.discover_apple_devices())
        return jsonify({"success": True, "devices": devices})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/select-device", methods=["POST"])
def select_device():
    try:
        data = request.json
        autolock_system.set_target_device(data["address"], data["name"])
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/start-monitoring", methods=["POST"])
def start_monitoring():
    try:
        if autolock_system.start_monitoring():
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Could not start monitoring"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/stop-monitoring", methods=["POST"])
def stop_monitoring():
    try:
        autolock_system.stop_monitoring()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/update-settings", methods=["POST"])
def update_settings():
    try:
        data = request.json
        autolock_system.config["rssi_threshold"] = data["rssi_threshold"]
        autolock_system.config["lock_delay"] = data["lock_delay"]
        autolock_system.rssi_threshold = data["rssi_threshold"]
        autolock_system.save_config()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


def run_web_server():
    """Run the Flask web server"""
    app.run(host="0.0.0.0", port=8080, debug=False)


if __name__ == "__main__":
    print("iPhone Auto-Lock System")
    print("=" * 30)
    print("Web interface starting at: http://localhost:8080")
    print("Open this URL on your iPhone to identify your device")
    print("Press Ctrl+C to stop")

    try:
        run_web_server()
    except KeyboardInterrupt:
        print("\nShutting down...")
        autolock_system.stop_monitoring()
