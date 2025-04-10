import os
import json
import requests
from datetime import datetime, timezone
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountLines
from pft_data import load_issuance_data

# Configure XRPL client
JSON_RPC_URL = "https://s2.ripple.com:51234"
client = JsonRpcClient(JSON_RPC_URL)

# PFT token issuer address
PFT_ISSUER = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"

# File to store previous balances
PREVIOUS_BALANCES_FILE = 'previous_balances.json'

def load_data():
    try:
        with open('address_data.json', 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

def load_previous_balances():
    try:
        with open(PREVIOUS_BALANCES_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_previous_balances(balances):
    with open(PREVIOUS_BALANCES_FILE, 'w') as f:
        json.dump(balances, f, indent=2)

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

def format_balance_change(current, previous):
    if previous == 0:
        return "🆕"
    change = current - previous
    if change == 0:
        return "="
    
    percentage = ((current / previous) - 1) * 100 if previous != 0 else 0
    if change > 0:
        return f"⬆️ +{change:,.2f} (+{percentage:.1f}%)"
    return f"⬇️ {change:,.2f} ({percentage:.1f}%)"

def format_discord_message(balances, previous_balances):
    current_time = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    
    # Get total PFT issuance
    total_issuance = load_issuance_data()
    if total_issuance == 0:
        total_issuance = 13818.00  # Fallback to known issuance if data not available
    
    # Calculate totals
    total_current = sum(b['balance'] for b in balances)
    total_previous = sum(previous_balances.values())
    
    # Calculate change in holdings as percentage of total issuance
    change_in_holdings = total_current - total_previous
    change_as_percent_of_issuance = (change_in_holdings / total_issuance * 100) if total_issuance > 0 else 0
    
    # Create the message content
    message = f"🏆 **PFT Holdings Leaderboard** - {current_time}\n\n"
    
    # Add total issuance first
    message += f"💫 **Total PFT Issued**: {total_issuance:,.2f}\n"
    
    # Add total holdings and change
    message += f"📊 **Total PFT Held**: {total_current:,.2f}"
    if total_previous > 0:
        total_change = format_balance_change(total_current, total_previous)
        message += f" {total_change}"
    message += "\n"
    
    # Add change in holdings as percentage of total issuance
    message += f"📈 **Change in PFT Held**: "
    if change_in_holdings == 0:
        message += "No change"
    else:
        change_symbol = "⬆️" if change_in_holdings > 0 else "⬇️"
        message += f"{change_symbol} {abs(change_as_percent_of_issuance):.1f}% of total issuance"
    message += "\n\n"
    
    # Add top holders
    for i, balance in enumerate(balances[:10], 1):
        nickname = balance['nickname'] or 'Anonymous'
        address = balance['address']
        amount = f"{balance['balance']:,.2f}"
        
        # Calculate change indicator
        prev_balance = previous_balances.get(address, 0)
        change_indicator = format_balance_change(balance['balance'], prev_balance)
        
        message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT {change_indicator}\n"
    
    return {
        "content": message,
        "username": "PFT Tracker",
        "avatar_url": "https://xrpl.org/assets/img/xrp-symbol-white.svg"
    }

def main():
    # Load tracked addresses and previous balances
    tracked_addresses = load_data()
    previous_balances = load_previous_balances()
    
    # Get current balances
    balances = []
    current_balances = {}  # For saving to previous_balances.json
    
    for address, info in tracked_addresses.items():
        balance = get_pft_balance(address)
        balances.append({
            'address': address,
            'nickname': info.get('nickname', ''),
            'balance': balance
        })
        current_balances[address] = balance
    
    # Sort by balance
    balances.sort(key=lambda x: x['balance'], reverse=True)
    
    # Format message
    message = format_discord_message(balances, previous_balances)
    
    # Get Discord webhook URL from environment variable
    webhook_url = os.getenv('DISCORD_WEBHOOK_URL')
    
    # If webhook URL exists, send to Discord
    if webhook_url:
        response = requests.post(webhook_url, json=message)
        if response.status_code != 204:
            raise Exception(f"Failed to send Discord message: {response.status_code}")
        print("Successfully updated rankings and sent Discord notification")
    else:
        # If no webhook URL, print to console
        print("\nRankings Report (Console Output):")
        print(message['content'])
    
    # Save current balances as previous for next run
    save_previous_balances(current_balances)

if __name__ == '__main__':
    main() 