# iPhone Auto-Lock System

Professional Bluetooth RSSI-based system that automatically locks your Mac when your iPhone goes far away. Uses signal strength monitoring to provide seamless security without manual intervention.

## Features

- **Automatic Mac Locking**: Locks your Mac when iPhone signal weakens or disappears
- **RSSI-Based Detection**: Uses Bluetooth signal strength to determine distance
- **Multiple Interfaces**: Command-line and web-based setup options
- **Continuous Monitoring**: Real-time RSSI logging every 5 seconds
- **Configurable Thresholds**: Customize distance and timing settings
- **Background Service**: Run as always-on background monitoring

## 🚀 Getting Started (Complete Guide)

### Prerequisites
- **macOS** (with Bluetooth enabled)
- **iPhone** (with Bluetooth enabled)
- **Python 3.7+** installed
- Both devices should be paired/trusted (not required but recommended)

### Step 1: Download and Setup

```bash
# Clone the repository
git clone https://github.com/sanjaymulchandani-xplor/python-bt-lock.git
cd python-bt-lock

# Create and activate virtual environment
python3 -m venv bluetooth_env
source bluetooth_env/bin/activate

# Install required packages
pip install -r requirements.txt
```

### Step 2: Configure Your iPhone (EASY METHOD)

```bash
# Run the notification-based setup (recommended)
python mac_autolock.py setup-notify
```

**What happens:**
1. 📱 A QR code appears in your terminal
2. 🔔 You'll get a Mac notification with a link
3. 📲 Open the link **on your iPhone** (not Mac)
4. ✅ System automatically detects and configures your iPhone
5. 🎯 RSSI threshold is set based on your current distance

### Step 3: Test the System

```bash
# Test that Mac locking works
python mac_autolock.py test-lock

# Check your configuration
python mac_autolock.py status
```

### Step 4: Start Auto-Lock Monitoring

```bash
# Start monitoring (will run until you stop it)
python mac_autolock.py monitor
```

**How to test:**
1. Keep terminal open to see status messages
2. Walk away with your iPhone (to another room)
3. Mac should lock automatically when signal gets weak
4. Walk back - no automatic unlock (for security)

### Step 5: Set Up Background Monitoring (Optional)

If you want it to run automatically:

```bash
# Start as background service
./rssi_service.sh start

# Check if it's running
./rssi_service.sh status

# View real-time logs
./rssi_service.sh follow

# Stop the service
./rssi_service.sh stop
```

### Step 6: Fine-tune Settings (If Needed)

If it locks too often or not often enough:

```bash
# Watch RSSI values in real-time
python rssi_monitor.py start
```

1. **Note the RSSI** when you're at your desk (e.g., -45 dBm)
2. **Walk to where you want it to lock** (e.g., another room)
3. **Note the RSSI** at that distance (e.g., -70 dBm)
4. **Stop monitoring** (Ctrl+C)
5. **Edit the config** to set threshold between those values

```bash
# Edit configuration file
nano autolock_config.json
```

Change the `rssi_threshold` value:
- **More sensitive** (locks sooner): higher number like -60
- **Less sensitive** (locks later): lower number like -75

## Quick Start (TL;DR)

For experienced users who want to get started immediately:

```bash
# 1. Setup
git clone https://github.com/sanjaymulchandani-xplor/python-bt-lock.git
cd python-bt-lock
python3 -m venv bluetooth_env && source bluetooth_env/bin/activate
pip install -r requirements.txt

# 2. Configure iPhone
python mac_autolock.py setup-notify  # Follow prompts on your iPhone

# 3. Start monitoring
python mac_autolock.py monitor       # Or: ./rssi_service.sh start
```

## Detailed Setup Instructions

### 1. Setup Environment
```bash
cd python-bt-lock
python3 -m venv bluetooth_env
source bluetooth_env/bin/activate
pip install -r requirements.txt
```

### 2. Configure Your iPhone

#### Option A: Notification-Based Setup (Recommended)
```bash
python mac_autolock.py setup-notify
```
This will:
- Scan for all Apple devices
- Start a web server and show you a QR code
- Send a Mac notification with the pairing URL
- Wait for you to click the notification **on your iPhone**
- Automatically configure optimal settings based on current signal strength

#### Option B: Manual Setup
```bash
python mac_autolock.py setup
```
This shows a list of detected Apple devices for manual selection.

### 3. Start Auto-Lock Monitoring
```bash
python mac_autolock.py monitor
```

### 4. Or Start Continuous RSSI Logging
```bash
python rssi_monitor.py start
```

## Core Scripts

### `mac_autolock.py` - Main Auto-Lock System
Professional command-line interface for iPhone proximity monitoring and auto-locking.

**Commands:**
```bash
python mac_autolock.py setup           # Configure your iPhone (manual)
python mac_autolock.py setup-notify    # Configure your iPhone (notification)
python mac_autolock.py status          # Show current configuration
python mac_autolock.py monitor         # Start monitoring and auto-lock
python mac_autolock.py test-lock       # Test Mac locking function
```

#### Notification-Based Setup
The `setup-notify` command provides the easiest way to pair your iPhone:

1. **Scans for all Apple devices** in Bluetooth range
2. **Starts a local web server** with a pairing interface
3. **Displays a QR code** in the terminal for easy access
4. **Sends a Mac notification** with the pairing URL
5. **Waits for you to interact** - open the URL on YOUR iPhone
6. **Automatically configures** optimal RSSI threshold based on current signal strength

**Benefits:**
- No guessing which device is yours from a list
- Automatically sets optimal RSSI threshold
- Works even if multiple Apple devices are nearby
- Provides visual QR code and clickable notification

**How it works:**
When you open the pairing URL on your iPhone, the system:
- Identifies your device by the incoming connection
- Measures current RSSI (signal strength)
- Sets threshold 15 dBm weaker than current signal
- Saves configuration automatically

### `rssi_monitor.py` - Continuous RSSI Monitoring
Always-on monitoring that logs your iPhone's RSSI every 5 seconds with detailed analytics.

**Commands:**
```bash
python rssi_monitor.py start              # Start continuous monitoring
python rssi_monitor.py status             # Show current status
python rssi_monitor.py logs [n]           # Show last n log entries
python rssi_monitor.py enable-autolock    # Enable automatic Mac locking
python rssi_monitor.py disable-autolock   # Disable automatic Mac locking
python rssi_monitor.py clear-logs         # Clear log file
```

**Sample Output:**
```
#0001 | RSSI: -42 dBm | EXCELLENT  | Very Close (<1m) | Uptime: 0:00:05
#0002 | RSSI: -45 dBm | EXCELLENT  | Very Close (<1m) | Uptime: 0:00:10
#0003 | RSSI: -58 dBm | GOOD       | Close (1-3m)     | Uptime: 0:00:15
#0004 | RSSI: -72 dBm | WEAK       | Far (10-20m)     | Uptime: 0:00:20 -> Will lock in 5s
#0005 | DEVICE NOT FOUND | Signal: NONE | Distance: Unknown | Uptime: 0:00:25 -> MAC LOCKED
```

### `mac_autolock_web.py` - Web Interface
Browser-based setup interface for easier iPhone identification.

```bash
python mac_autolock_web.py
# Open http://localhost:8080 on your iPhone
```

### `rssi_service.sh` - Background Service Manager
Manage the RSSI monitor as a background service.

```bash
./rssi_service.sh start    # Start as background service
./rssi_service.sh stop     # Stop background service
./rssi_service.sh status   # Check service status
./rssi_service.sh logs     # View recent logs
./rssi_service.sh follow   # Follow logs in real-time
```

## RSSI Configuration Guide

### Understanding RSSI Values
RSSI (Received Signal Strength Indicator) measures Bluetooth signal strength in dBm:

- **-30 to -50 dBm**: Excellent signal (very close, same desk)
- **-50 to -60 dBm**: Good signal (across room)
- **-60 to -70 dBm**: Fair signal (different room)
- **-70 to -80 dBm**: Weak signal (far away, different floor)
- **-80 to -100 dBm**: Very weak signal (very far)

### Setting RSSI Thresholds

#### Method 1: During Initial Setup
```bash
python mac_autolock.py setup
# Follow prompts to set RSSI threshold
```

#### Method 2: Edit Configuration File
Edit `autolock_config.json`:
```json
{
  "target_device_address": "34CAB122-3952-B9FD-817B-212B21AF0AA9",
  "target_device_name": "Hidden Apple Device",
  "rssi_threshold": -60,
  "scan_interval": 3,
  "lock_delay": 10
}
```

#### Method 3: Command Line Configuration
```bash
# View current settings
python mac_autolock.py status

# Reset and reconfigure everything
python mac_autolock.py setup

# Test different thresholds
python rssi_monitor.py start  # Watch RSSI values in real-time
# Note the RSSI when you're at your desired "lock distance"
# Stop with Ctrl+C and update config file
```

### Recommended RSSI Settings by Use Case

#### Office/Shared Space (High Security)
```json
{
  "rssi_threshold": -50,
  "lock_delay": 5
}
```
Locks when you step away from desk.

#### Home Office (Balanced)
```json
{
  "rssi_threshold": -65,
  "lock_delay": 10
}
```
Locks when you leave the room.

#### Relaxed Environment (Low Sensitivity)
```json
{
  "rssi_threshold": -75,
  "lock_delay": 15
}
```
Locks only when you go far away.

### Calibrating Your Setup

1. **Find Your Baseline**:
   ```bash
   python rssi_monitor.py start
   ```
   Note the RSSI when sitting at your desk.

2. **Test Distance Points**:
   - Walk to where you want auto-lock to trigger
   - Note the RSSI value at that distance
   - Set threshold 5-10 dBm higher (less negative) than that value

3. **Fine-tune Lock Delay**:
   - `5 seconds`: Quick response, may have false triggers
   - `10 seconds`: Balanced (recommended)
   - `15+ seconds`: Conservative, fewer false triggers

### Resetting Configuration

#### Complete Reset
```bash
rm autolock_config.json
python mac_autolock.py setup
```

#### Reset Only RSSI Threshold
```bash
python mac_autolock.py setup
# Select same device, change only RSSI threshold
```

#### Manual Configuration Reset
Edit `autolock_config.json` and change values:
```json
{
  "rssi_threshold": -70,    # Change this value
  "lock_delay": 10,         # And/or this value
  "scan_interval": 3
}
```

## Background Monitoring

### Start Always-On Monitoring
```bash
# Option 1: Using service manager
./rssi_service.sh start

# Option 2: Direct background start
nohup python rssi_monitor.py start > /dev/null 2>&1 &
```

### Monitor Performance
```bash
# Check if running
./rssi_service.sh status

# View recent activity
./rssi_service.sh logs 50

# Follow real-time logs
./rssi_service.sh follow
```

### Stop Background Monitoring
```bash
./rssi_service.sh stop
```

## ❓ Common First-Time User Questions

### "How do I know it's working?"
```bash
python rssi_monitor.py start
```
You'll see real-time output like:
```
#0001 | RSSI: -42 dBm | EXCELLENT  | Very Close (<1m) | Uptime: 0:00:05
#0002 | RSSI: -45 dBm | EXCELLENT  | Very Close (<1m) | Uptime: 0:00:10
```

### "It's not detecting my iPhone"
1. Make sure iPhone Bluetooth is ON
2. Bring iPhone very close during setup
3. Try the manual setup: `python mac_autolock.py setup`
4. Make sure both devices are discoverable

### "It locks too often"
Edit `autolock_config.json` and change:
```json
"rssi_threshold": -75,  # Make this number smaller (more negative)
"lock_delay": 15        # Wait longer before locking
```

### "It never locks"
Edit `autolock_config.json` and change:
```json
"rssi_threshold": -55,  # Make this number bigger (less negative)  
"lock_delay": 5         # Wait shorter time before locking
```

### "How do I stop it?"
- **Foreground monitoring**: Press `Ctrl+C`
- **Background service**: `./rssi_service.sh stop`

### "How do I restart everything?"
```bash
# Stop any running monitors
./rssi_service.sh stop

# Delete configuration 
rm autolock_config.json

# Reconfigure
python mac_autolock.py setup-notify
```

## Troubleshooting

### No Devices Found During Setup
1. Enable iPhone Bluetooth
2. Make iPhone discoverable temporarily
3. Bring iPhone closer during setup
4. Try multiple scans

### False Auto-Lock Triggers
1. **Increase RSSI threshold** (make less negative): -55 → -65
2. **Increase lock delay**: 10s → 15s
3. **Check for interference**: WiFi, other Bluetooth devices

### Mac Never Locks
1. **Decrease RSSI threshold** (make more negative): -70 → -60
2. **Decrease lock delay**: 15s → 10s
3. **Test lock function**: `python mac_autolock.py test-lock`

### Monitor Stops Working
1. **Check device address**: iPhone address may change (iOS privacy)
2. **Re-run setup**: `python mac_autolock.py setup`
3. **Check logs**: `python rssi_monitor.py logs`

## Configuration Files

- `autolock_config.json` - Main configuration
- `rssi_monitor.log` - Continuous monitoring logs
- `requirements.txt` - Python dependencies

## Project Structure

```
python-bt-lock/
├── mac_autolock.py      # Main auto-lock system
├── rssi_monitor.py      # Continuous RSSI monitoring
├── mac_autolock_web.py  # Web interface
├── rssi_service.sh      # Background service manager
├── autolock_config.json # Configuration
├── requirements.txt     # Dependencies
├── bluetooth_env/       # Virtual environment
└── README.md           # This file
```

This system provides professional, reliable automatic Mac security based on your iPhone's proximity!
