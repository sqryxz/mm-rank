import json
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

# Initialize storage if it doesn't exist
if not os.path.exists(STORAGE_FILE):
    save_data({
        "rLW9gnQo7BQhU6igk5keqYnH3TVrCxGRzm": {"nickname": "Example Wallet"}
    }) 