import os
import json
import requests
from datetime import datetime
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountLines

# Configure XRPL client
JSON_RPC_URL = "https://livenet.xrpl.org:51234"
client = JsonRpcClient(JSON_RPC_URL)

# PFT token issuer address
PFT_ISSUER = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"

def load_data():
    try:
        with open('data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def get_pft_balance(address):
    try:
        account_lines = AccountLines(
            account=address,
            peer=PFT_ISSUER
        )
        response = client.request(account_lines)
        
        for line in response.result.get("lines", []):
            if line.get("account") == PFT_ISSUER:
                return float(line.get("balance", "0"))
        return 0
    except Exception as e:
        print(f"Error getting balance for {address}: {str(e)}")
        return 0

def format_discord_message(balances):
    current_time = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    
    # Create the message content
    message = f"🏆 **PFT Holdings Leaderboard** - {current_time}\n\n"
    
    # Add top holders
    for i, balance in enumerate(balances[:10], 1):
        nickname = balance['nickname'] or 'Anonymous'
        address = balance['address']
        amount = f"{balance['balance']:,.2f}"
        message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT\n"
    
    return {
        "content": message,
        "username": "PFT Tracker",
        "avatar_url": "https://xrpl.org/assets/img/xrp-symbol-white.svg"
    }

def main():
    # Get Discord webhook URL from environment variable
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    if not webhook_url:
        raise ValueError("Discord webhook URL not found in environment variables")

    # Load tracked addresses
    tracked_addresses = load_data()
    
    # Get current balances
    balances = []
    for address, info in tracked_addresses.items():
        balance = get_pft_balance(address)
        balances.append({
            'address': address,
            'nickname': info.get('nickname', ''),
            'balance': balance
        })
    
    # Sort by balance
    balances.sort(key=lambda x: x['balance'], reverse=True)
    
    # Format and send Discord message
    message = format_discord_message(balances)
    response = requests.post(webhook_url, json=message)
    
    if response.status_code != 204:
        raise Exception(f"Failed to send Discord message: {response.status_code}")
    
    print("Successfully updated rankings and sent Discord notification")

if __name__ == '__main__':
    main() 