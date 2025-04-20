from flask import Flask, render_template, jsonify, request
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountLines
import json
import time
from storage import load_data, save_data

app = Flask(__name__)

# Configure XRPL client
JSON_RPC_URL = "https://s2.ripple.com:51234"
client = JsonRpcClient(JSON_RPC_URL)

# PFT token issuer address
PFT_ISSUER = "r4yc85M1hwsegVGZ1pawpZPwj65SVs8PzD"

# Load tracked addresses from storage
TRACKED_ADDRESSES = load_data()

def get_pft_balance(address):
    try:
        # Request account lines
        account_lines = AccountLines(
            account=address,
            peer=PFT_ISSUER
        )
        response = client.request(account_lines)
        
        # Find PFT balance
        for line in response.result.get("lines", []):
            if line.get("account") == PFT_ISSUER:
                return float(line.get("balance", "0"))
        return 0
    except Exception as e:
        print(f"Error getting balance for {address}: {str(e)}")
        return 0

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/balances')
def get_balances():
    balances = []
    for address, info in TRACKED_ADDRESSES.items():
        balance = get_pft_balance(address)
        balances.append({
            'address': address,
            'nickname': info.get('nickname', ''),
            'balance': balance
        })
    
    # Sort by balance in descending order
    balances.sort(key=lambda x: x['balance'], reverse=True)
    return jsonify(balances)

@app.route('/api/nickname', methods=['POST'])
def update_nickname():
    data = request.json
    address = data.get('address')
    nickname = data.get('nickname')
    
    if address in TRACKED_ADDRESSES:
        TRACKED_ADDRESSES[address]['nickname'] = nickname
        # Save to persistent storage
        save_data(TRACKED_ADDRESSES)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Address not found'}), 404

@app.route('/api/address', methods=['POST'])
def add_address():
    data = request.json
    address = data.get('address')
    nickname = data.get('nickname', '')
    
    if not address:
        return jsonify({'success': False, 'error': 'Address is required'}), 400
        
    # Add new address to tracking list
    TRACKED_ADDRESSES[address] = {'nickname': nickname}
    # Save to persistent storage
    save_data(TRACKED_ADDRESSES)
    return jsonify({'success': True})

@app.route('/api/address/<address>', methods=['DELETE'])
def remove_address(address):
    if address in TRACKED_ADDRESSES:
        del TRACKED_ADDRESSES[address]
        # Save to persistent storage
        save_data(TRACKED_ADDRESSES)
        return jsonify({'success': True})
    return jsonify({'success': False, 'error': 'Address not found'}), 404

if __name__ == '__main__':
    app.run(debug=True, port=5002) 