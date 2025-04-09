#!/usr/bin/env python3
import json
import sys
import os
from typing import Dict, Any

STORAGE_FILE = "address_data.json"

def load_data() -> Dict[str, Any]:
    """Load address data from JSON file."""
    if os.path.exists(STORAGE_FILE):
        try:
            with open(STORAGE_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print(f"Error reading {STORAGE_FILE}, starting with empty data")
    return {}

def save_data(data: Dict[str, Any]) -> None:
    """Save address data to JSON file."""
    try:
        with open(STORAGE_FILE, 'w') as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print(f"Error saving data: {str(e)}")

def list_addresses():
    """List all tracked addresses."""
    data = load_data()
    if not data:
        print("No addresses being tracked.")
        return
    
    print("\nCurrently tracked addresses:")
    print("-" * 50)
    for address, info in data.items():
        nickname = info.get('nickname', 'No nickname')
        print(f"Address: {address}")
        print(f"Nickname: {nickname}")
        print("-" * 50)

def add_address(address: str, nickname: str = ""):
    """Add a new address to track."""
    data = load_data()
    data[address] = {"nickname": nickname}
    save_data(data)
    print(f"Added address {address}" + (f" with nickname {nickname}" if nickname else ""))

def remove_address(address: str):
    """Remove an address from tracking."""
    data = load_data()
    if address in data:
        del data[address]
        save_data(data)
        print(f"Removed address {address}")
    else:
        print(f"Address {address} not found in tracking list")

def update_nickname(address: str, nickname: str):
    """Update the nickname for an address."""
    data = load_data()
    if address in data:
        data[address]['nickname'] = nickname
        save_data(data)
        print(f"Updated nickname for {address} to {nickname}")
    else:
        print(f"Address {address} not found in tracking list")

def print_usage():
    print("""
Usage:
    python3 manage_addresses.py list
    python3 manage_addresses.py add <address> [nickname]
    python3 manage_addresses.py remove <address>
    python3 manage_addresses.py update-nickname <address> <nickname>
    """)

def main():
    if len(sys.argv) < 2:
        print_usage()
        return

    command = sys.argv[1]

    if command == "list":
        list_addresses()
    elif command == "add" and len(sys.argv) >= 3:
        address = sys.argv[2]
        nickname = sys.argv[3] if len(sys.argv) > 3 else ""
        add_address(address, nickname)
    elif command == "remove" and len(sys.argv) == 3:
        remove_address(sys.argv[2])
    elif command == "update-nickname" and len(sys.argv) == 4:
        update_nickname(sys.argv[2], sys.argv[3])
    else:
        print_usage()

if __name__ == "__main__":
    main() 