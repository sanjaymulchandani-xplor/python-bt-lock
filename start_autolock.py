#!/usr/bin/env python3
"""
iPhone Auto-Lock Launcher
========================

Simple launcher script for the iPhone Auto-Lock system.
Choose your preferred mode of operation.
"""

import os
import sys
from pathlib import Path


def print_banner():
    print("🔒 iPhone Auto-Lock System")
    print("=" * 40)
    print("Automatically lock your Mac when your iPhone goes far away!")
    print()


def print_menu():
    print("Choose your setup method:")
    print()
    print("1. 🚀 Complete Setup (Recommended)")
    print("   • All-in-one: pairing + monitoring")
    print("   • Notification-based iPhone detection")
    print("   • Starts monitoring immediately after pairing")
    print()
    print("2. ⚡ Quick Start")
    print("   • Use existing iPhone configuration")
    print("   • Start monitoring immediately")
    print()
    print("3. 🔄 Reset & Start Fresh")
    print("   • Clear all settings and start over")
    print("   • Complete new setup process")
    print()
    print("4. ⚙️  Manual Setup")
    print("   • Step-by-step configuration")
    print("   • Choose from device list")
    print()
    print("5. 📊 Show Status")
    print("   • View current configuration")
    print()
    print("0. ❌ Exit")
    print()


def run_command(command):
    """Run a command in the virtual environment"""
    venv_path = Path("bluetooth_env/bin/activate")
    if venv_path.exists():
        os.system(f"source {venv_path} && {command}")
    else:
        print("❌ Virtual environment not found!")
        print(
            "Please run: python3 -m venv bluetooth_env && source bluetooth_env/bin/activate && pip install -r requirements.txt"
        )
        return False
    return True


def main():
    print_banner()

    # Check if we're in the right directory
    if not Path("mac_autolock.py").exists():
        print("❌ Error: Please run this from the python-bt-lock directory")
        sys.exit(1)

    while True:
        print_menu()

        try:
            choice = input("Enter your choice (0-5): ").strip()
            print()

            if choice == "1":
                print("🚀 Starting Complete Setup...")
                print("This will handle pairing and monitoring in one go!")
                print()
                run_command("python iphone_autolock_complete.py")
                break

            elif choice == "2":
                print("⚡ Starting Quick Start...")
                run_command("python iphone_autolock_complete.py quick")
                break

            elif choice == "3":
                print("🔄 Resetting configuration...")
                run_command("python iphone_autolock_complete.py reset")
                break

            elif choice == "4":
                print("⚙️  Starting Manual Setup...")
                print("1. First, configure your iPhone:")
                run_command("python mac_autolock.py setup-notify")
                print("\n2. Now start monitoring:")
                run_command("python mac_autolock.py monitor")
                break

            elif choice == "5":
                print("📊 Current Status:")
                run_command("python mac_autolock.py status")
                print("\nPress Enter to continue...")
                input()
                continue

            elif choice == "0":
                print("👋 Goodbye!")
                break

            else:
                print("❌ Invalid choice. Please enter 0-5.")
                continue

        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            continue


if __name__ == "__main__":
    main()
