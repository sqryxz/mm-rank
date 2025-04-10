import json
import os

ISSUANCE_DATA_FILE = 'issuance_data.json'

def save_issuance_data(total_issuance):
    data = {
        'total_issuance': total_issuance
    }
    with open(ISSUANCE_DATA_FILE, 'w') as f:
        json.dump(data, f)

def load_issuance_data():
    try:
        with open(ISSUANCE_DATA_FILE, 'r') as f:
            data = json.load(f)
            return data.get('total_issuance', 0)
    except (FileNotFoundError, json.JSONDecodeError):
        return 0 