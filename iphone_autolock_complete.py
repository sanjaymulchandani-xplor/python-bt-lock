#!/usr/bin/env python3
"""
iPhone Auto-Lock Complete Setup & Monitor
==========================================

One-stop solution for iPhone proximity-based Mac auto-lock.
This script handles everything from device pairing to continuous monitoring.

Features:
- Automatic device discovery and pairing
- Notification-based iPhone identification
- Continuous RSSI monitoring
- Automatic Mac locking when iPhone goes far
- Web interface for easy setup
- Background service capabilities

Usage:
    python iphone_autolock_complete.py          # Start complete setup & monitoring
    python iphone_autolock_complete.py quick    # Quick start (if already paired)
    python iphone_autolock_complete.py reset    # Reset and start over
"""

import asyncio
import json
import subprocess
import platform
import time
import threading
import webbrowser
import socket
import signal
import sys
import os
from datetime import datetime
from pathlib import Path
from bleak import BleakScanner
from bleak.backends.device import BLEDevice
from bleak.backends.scanner import AdvertisementData
from flask import Flask, request, jsonify, render_template_string


class CompleteAutoLockSystem:
    def __init__(
        self, config_file="autolock_config.json", log_file="autolock_complete.log"
    ):
        self.config_file = Path(config_file)
        self.log_file = Path(log_file)
        self.config = self.load_config()
        self.monitoring = False
        self.device_present = False
        self.pairing_completed = False

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

    def log_message(self, message):
        """Log message to both console and file"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {message}"
        print(log_entry)

        # Also log to file
        try:
            with open(self.log_file, "a") as f:
                f.write(log_entry + "\n")
        except Exception:
            pass  # Continue even if logging fails

    def lock_mac(self):
        """Lock the Mac computer"""
        try:
            if platform.system() == "Darwin":
                result = subprocess.run(
                    [
                        "/System/Library/CoreServices/Menu Extras/User.menu/Contents/Resources/CGSession",
                        "-suspend",
                    ],
                    check=True,
                    capture_output=True,
                )
                self.log_message("🔒 MAC LOCKED successfully")
                return True
            else:
                self.log_message("❌ Mac locking not supported on this platform")
                return False
        except subprocess.CalledProcessError:
            try:
                subprocess.run(
                    [
                        "osascript",
                        "-e",
                        'tell application "System Events" to keystroke "q" using {control down, command down}',
                    ],
                    check=True,
                )
                self.log_message("🔒 MAC LOCKED via AppleScript")
                return True
            except Exception as e:
                self.log_message(f"❌ Failed to lock Mac: {e}")
                return False

    async def discover_apple_devices(self):
        """Discover nearby Apple devices"""
        self.log_message("🔍 Scanning for Apple devices...")
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
        found_devices = list(devices.values())
        self.log_message(f"✅ Found {len(found_devices)} Apple device(s)")
        return found_devices

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
        await asyncio.sleep(self.config["scan_interval"])
        await scanner.stop()

        return found_device

    def start_pairing_process(self):
        """Start the notification-based pairing process"""
        self.log_message("🚀 Starting notification-based iPhone pairing...")

        # Discover devices
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        devices = loop.run_until_complete(self.discover_apple_devices())

        if not devices:
            self.log_message(
                "❌ No Apple devices found! Make sure iPhone Bluetooth is enabled."
            )
            return False

        # Start pairing server
        success = self.start_pairing_server(devices)
        return success

    def start_pairing_server(self, devices):
        """Start web server for notification-based pairing"""
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "complete-autolock-system"

        pairing_state = {
            "completed": False,
            "selected_device": None,
            "devices": devices,
            "start_monitoring": False,
        }

        # HTML template for the complete pairing page
        COMPLETE_PAIRING_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>🔒 iPhone Auto-Lock Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            max-width: 400px;
            margin: 30px auto;
            padding: 20px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            text-align: center;
        }
        .container {
            background: white;
            border-radius: 20px;
            padding: 30px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
        }
        .header {
            font-size: 28px;
            font-weight: 700;
            background: linear-gradient(45deg, #667eea, #764ba2);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: 10px;
        }
        .subtitle {
            color: #666;
            margin-bottom: 30px;
            line-height: 1.5;
            font-size: 16px;
        }
        .step-indicator {
            display: flex;
            justify-content: space-between;
            margin: 20px 0;
            padding: 0 20px;
        }
        .step {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: #f0f0f0;
            display: flex;
            align-items: center;
            justify-content: center;
            font-weight: bold;
            color: #999;
        }
        .step.active {
            background: #667eea;
            color: white;
        }
        .step.completed {
            background: #4CAF50;
            color: white;
        }
        .device-info {
            background: #f8f9ff;
            border-radius: 15px;
            padding: 25px;
            margin: 25px 0;
            border: 2px solid #e3e8ff;
        }
        .device-name {
            font-weight: 600;
            color: #1d1d1f;
            font-size: 20px;
            margin-bottom: 8px;
        }
        .device-details {
            color: #666;
            font-size: 14px;
            line-height: 1.4;
        }
        .pair-button {
            background: linear-gradient(45deg, #667eea, #764ba2);
            color: white;
            border: none;
            border-radius: 15px;
            padding: 18px 35px;
            font-size: 16px;
            font-weight: 600;
            cursor: pointer;
            width: 100%;
            margin-top: 25px;
            transition: transform 0.2s;
        }
        .pair-button:hover {
            transform: translateY(-2px);
        }
        .pair-button:disabled {
            background: #ccc;
            cursor: not-allowed;
            transform: none;
        }
        .success {
            color: #4CAF50;
            font-weight: 600;
            margin-top: 20px;
            font-size: 18px;
        }
        .loading {
            display: none;
            color: #667eea;
            margin-top: 20px;
            font-size: 16px;
        }
        .monitoring-info {
            background: #e8f5e8;
            border-radius: 12px;
            padding: 20px;
            margin-top: 20px;
            border-left: 4px solid #4CAF50;
        }
        .pulse {
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0% { opacity: 1; }
            50% { opacity: 0.5; }
            100% { opacity: 1; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">🔒 iPhone Auto-Lock</div>
        <div class="subtitle">Complete setup and monitoring in one go!</div>

        <div class="step-indicator">
            <div class="step active" id="step1">1</div>
            <div class="step" id="step2">2</div>
            <div class="step" id="step3">3</div>
        </div>

        <div class="device-info">
            <div class="device-name">📱 Your iPhone</div>
            <div class="device-details" id="device-details">
                This will pair your iPhone with your Mac and start automatic monitoring.
                When you walk away, your Mac will lock automatically!
            </div>
        </div>

        <button class="pair-button" onclick="startCompleteSetup()" id="setup-btn">
            🚀 Start Complete Setup
        </button>

        <div class="loading" id="loading">
            <div class="pulse">⏳ Setting up your iPhone auto-lock system...</div>
        </div>

        <div class="success" id="success" style="display:none;">
            <div>✅ Setup Complete!</div>
            <div class="monitoring-info" id="monitoring-info" style="display:none;">
                <strong>🔄 Monitoring Started</strong><br>
                Your Mac will now lock automatically when your iPhone goes far away.<br>
                <small>Close this page - monitoring continues in background.</small>
            </div>
        </div>
    </div>

    <script>
        async function startCompleteSetup() {
            const button = document.getElementById('setup-btn');
            const loading = document.getElementById('loading');
            const success = document.getElementById('success');
            const step2 = document.getElementById('step2');
            const step3 = document.getElementById('step3');
            const monitoringInfo = document.getElementById('monitoring-info');

            button.style.display = 'none';
            loading.style.display = 'block';
            step2.classList.add('active');

            try {
                // Step 1: Pair device
                const pairResponse = await fetch('/pair', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        user_agent: navigator.userAgent,
                        timestamp: new Date().toISOString(),
                        complete_setup: true
                    })
                });

                const pairResult = await pairResponse.json();

                if (!pairResult.success) {
                    throw new Error(pairResult.error || 'Pairing failed');
                }

                // Update UI for successful pairing
                step2.classList.remove('active');
                step2.classList.add('completed');
                step3.classList.add('active');

                document.getElementById('device-details').innerHTML =
                    `<strong>✅ Paired Successfully!</strong><br>
                     Device: ${pairResult.device_name}<br>
                     RSSI Threshold: ${pairResult.rssi_threshold} dBm<br>
                     Lock Delay: ${pairResult.lock_delay}s`;

                // Step 2: Start monitoring
                const monitorResponse = await fetch('/start-monitoring', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' }
                });

                const monitorResult = await monitorResponse.json();

                if (monitorResult.success) {
                    step3.classList.remove('active');
                    step3.classList.add('completed');
                    loading.style.display = 'none';
                    success.style.display = 'block';
                    monitoringInfo.style.display = 'block';
                } else {
                    throw new Error('Failed to start monitoring');
                }

            } catch (error) {
                loading.style.display = 'none';
                button.style.display = 'block';
                button.textContent = '❌ Setup Failed - Try Again';
                button.disabled = false;
                alert('Setup failed: ' + error.message);
            }
        }
    </script>
</body>
</html>
        """

        @app.route("/")
        def index():
            return COMPLETE_PAIRING_HTML

        @app.route("/pair", methods=["POST"])
        def pair_device():
            if pairing_state["completed"]:
                return jsonify({"success": False, "error": "Pairing already completed"})

            try:
                client_data = request.get_json()

                # Select best device (highest RSSI)
                if len(pairing_state["devices"]) == 1:
                    selected_device = pairing_state["devices"][0]
                else:
                    selected_device = max(
                        pairing_state["devices"], key=lambda d: d["rssi"] or -100
                    )

                # Configure optimal settings
                current_rssi = selected_device.get("rssi", -70)
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

                self.log_message(
                    f"✅ Paired with: {selected_device['name']} ({selected_device['address']})"
                )
                self.log_message(
                    f"📊 RSSI Threshold: {rssi_threshold} dBm (Current: {current_rssi} dBm)"
                )

                return jsonify(
                    {
                        "success": True,
                        "device_name": selected_device["name"],
                        "rssi_threshold": rssi_threshold,
                        "lock_delay": 10,
                    }
                )

            except Exception as e:
                self.log_message(f"❌ Pairing error: {e}")
                return jsonify({"success": False, "error": str(e)})

        @app.route("/start-monitoring", methods=["POST"])
        def start_monitoring():
            if not pairing_state["completed"]:
                return jsonify({"success": False, "error": "Must pair device first"})

            try:
                # Signal that monitoring should start
                pairing_state["start_monitoring"] = True
                self.pairing_completed = True

                self.log_message("🔄 Starting continuous monitoring...")
                return jsonify({"success": True})

            except Exception as e:
                self.log_message(f"❌ Monitoring start error: {e}")
                return jsonify({"success": False, "error": str(e)})

        # Find available port and start server
        def find_free_port():
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(("", 0))
                s.listen(1)
                port = s.getsockname()[1]
            return port

        def get_local_ip():
            try:
                with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                    s.connect(("8.8.8.8", 80))
                    return s.getsockname()[0]
            except:
                return "localhost"

        port = find_free_port()
        local_ip = get_local_ip()
        pairing_url = f"http://{local_ip}:{port}"

        self.log_message(f"🌐 Pairing server: {pairing_url}")
        self.log_message(f"📱 Open this URL on your iPhone: {pairing_url}")

        # Show QR code
        self.print_qr_code(pairing_url)

        # Send notification
        try:
            subprocess.run(
                [
                    "osascript",
                    "-e",
                    f'display notification "Open {pairing_url} on your iPhone" with title "iPhone Auto-Lock Setup"',
                ],
                check=True,
                capture_output=True,
            )
            self.log_message("📢 Mac notification sent")
        except:
            pass

        # Start server in background
        server_thread = threading.Thread(
            target=lambda: app.run(
                host="0.0.0.0", port=port, debug=False, use_reloader=False
            ),
            daemon=True,
        )
        server_thread.start()

        # Wait for pairing and monitoring signal
        timeout = 300  # 5 minutes
        start_time = time.time()

        self.log_message("⏳ Waiting for iPhone pairing...")

        try:
            while (
                not pairing_state["start_monitoring"]
                and (time.time() - start_time) < timeout
            ):
                time.sleep(1)
                elapsed = int(time.time() - start_time)
                if elapsed % 30 == 0 and elapsed > 0:
                    self.log_message(f"⏳ Still waiting... ({elapsed}s elapsed)")

            if pairing_state["start_monitoring"]:
                self.log_message("✅ Pairing completed! Starting monitoring...")
                return True
            else:
                self.log_message(f"⏰ Timeout after {timeout} seconds")
                return False

        except KeyboardInterrupt:
            self.log_message("🛑 Setup cancelled by user")
            return False

    def print_qr_code(self, url):
        """Print QR code for easy access"""
        try:
            import qrcode

            qr = qrcode.QRCode(version=1, box_size=1, border=1)
            qr.add_data(url)
            qr.make(fit=True)
            qr.print_ascii(invert=True)
        except ImportError:
            self.log_message(f"📱 QR Code: {url}")

    async def continuous_monitoring(self):
        """Continuous monitoring with auto-lock"""
        if not self.config["target_device_address"]:
            self.log_message("❌ No device configured!")
            return

        self.monitoring = True
        consecutive_far_readings = 0
        required_far_readings = max(
            1, self.config["lock_delay"] // self.config["scan_interval"]
        )

        self.log_message("🔄 Starting continuous monitoring...")
        self.log_message(f"📊 Target: {self.config['target_device_name']}")
        self.log_message(f"📊 RSSI Threshold: {self.config['rssi_threshold']} dBm")
        self.log_message(f"📊 Lock Delay: {self.config['lock_delay']}s")
        self.log_message("🔄 Monitoring every 3 seconds...")

        try:
            scan_count = 0
            while self.monitoring:
                scan_count += 1
                device = await self.scan_for_target_device()
                current_time = datetime.now().strftime("%H:%M:%S")

                if device and device["rssi"] is not None:
                    rssi = device["rssi"]

                    # Determine signal quality
                    if rssi > -50:
                        quality = "EXCELLENT"
                        distance = "Very Close (<1m)"
                    elif rssi > -60:
                        quality = "GOOD"
                        distance = "Close (1-3m)"
                    elif rssi > -70:
                        quality = "FAIR"
                        distance = "Medium (3-10m)"
                    elif rssi > -80:
                        quality = "WEAK"
                        distance = "Far (10-20m)"
                    else:
                        quality = "VERY WEAK"
                        distance = "Very Far (20m+)"

                    if rssi <= self.config["rssi_threshold"]:
                        consecutive_far_readings += 1
                        self.log_message(
                            f"#{scan_count:04d} | RSSI: {rssi} dBm | {quality} | {distance} | FAR ({consecutive_far_readings}/{required_far_readings})"
                        )

                        if consecutive_far_readings >= required_far_readings:
                            self.log_message(
                                f"🔒 LOCKING MAC - iPhone too far for {self.config['lock_delay']}s"
                            )
                            if self.lock_mac():
                                break
                    else:
                        if consecutive_far_readings > 0:
                            self.log_message(
                                f"#{scan_count:04d} | RSSI: {rssi} dBm | {quality} | {distance} | NEAR (reset counter)"
                            )
                        else:
                            self.log_message(
                                f"#{scan_count:04d} | RSSI: {rssi} dBm | {quality} | {distance} | NEAR"
                            )
                        consecutive_far_readings = 0
                        self.device_present = True
                else:
                    consecutive_far_readings += 1
                    self.log_message(
                        f"#{scan_count:04d} | DEVICE NOT FOUND | Signal: NONE | Distance: Unknown | ({consecutive_far_readings}/{required_far_readings})"
                    )

                    if consecutive_far_readings >= required_far_readings:
                        self.log_message(
                            f"🔒 LOCKING MAC - iPhone not detected for {self.config['lock_delay']}s"
                        )
                        if self.lock_mac():
                            break

                await asyncio.sleep(self.config["scan_interval"])

        except KeyboardInterrupt:
            self.log_message("🛑 Monitoring stopped by user")
        except Exception as e:
            self.log_message(f"❌ Monitoring error: {e}")

        self.monitoring = False
        self.log_message("🔄 Monitoring stopped")

    def run_complete_system(self):
        """Run the complete system from start to finish"""
        self.log_message("🚀 iPhone Auto-Lock Complete System Starting...")
        self.log_message("=" * 50)

        # Check if already configured
        if self.config["target_device_address"]:
            self.log_message(
                f"📱 Found existing configuration for: {self.config['target_device_name']}"
            )
            user_input = input("Use existing configuration? (y/n): ").lower().strip()
            if user_input == "y":
                self.log_message("✅ Using existing configuration")
                asyncio.run(self.continuous_monitoring())
                return
            else:
                self.log_message("🔄 Starting fresh setup...")

        # Start pairing process
        if self.start_pairing_process():
            self.log_message("✅ Pairing completed successfully!")
            self.log_message("🔄 Starting continuous monitoring...")
            asyncio.run(self.continuous_monitoring())
        else:
            self.log_message("❌ Pairing failed or was cancelled")

    def quick_start(self):
        """Quick start for already configured devices"""
        if not self.config["target_device_address"]:
            self.log_message("❌ No device configured! Please run full setup first.")
            return False

        self.log_message("🚀 Quick Start - Using existing configuration")
        self.log_message(f"📱 Target: {self.config['target_device_name']}")
        asyncio.run(self.continuous_monitoring())
        return True

    def reset_configuration(self):
        """Reset configuration and start fresh"""
        self.log_message("🔄 Resetting configuration...")

        # Remove config file
        if self.config_file.exists():
            self.config_file.unlink()
            self.log_message("✅ Configuration file deleted")

        # Remove log file
        if self.log_file.exists():
            self.log_file.unlink()
            self.log_message("✅ Log file cleared")

        # Reset config
        self.config = {
            "target_device_address": None,
            "target_device_name": None,
            "rssi_threshold": -70,
            "scan_interval": 3,
            "lock_delay": 10,
        }

        self.log_message("🚀 Starting fresh setup...")
        self.run_complete_system()


def signal_handler(sig, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Shutting down iPhone Auto-Lock system...")
    sys.exit(0)


def main():
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    system = CompleteAutoLockSystem()

    if len(sys.argv) > 1:
        command = sys.argv[1].lower()

        if command == "quick":
            system.quick_start()
        elif command == "reset":
            system.reset_configuration()
        elif command == "help":
            print(
                """
iPhone Auto-Lock Complete System
===============================

Commands:
    python iphone_autolock_complete.py          # Complete setup & monitoring
    python iphone_autolock_complete.py quick    # Quick start (existing config)
    python iphone_autolock_complete.py reset    # Reset and start over
    python iphone_autolock_complete.py help     # Show this help

Features:
• One-command setup and monitoring
• Notification-based iPhone pairing
• Continuous RSSI monitoring
• Automatic Mac locking
• Beautiful web interface
• Background service ready

The complete system handles everything automatically!
            """
            )
        else:
            print(f"Unknown command: {command}")
            print("Use 'help' to see available commands")
    else:
        # Default: run complete system
        system.run_complete_system()


if __name__ == "__main__":
    main()
