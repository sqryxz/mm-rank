import os
import json
import requests
from datetime import datetime, timezone, timedelta
from xrpl.clients import JsonRpcClient
from xrpl.models.requests import AccountLines
from pft_data import load_issuance_data

# Configure XRPL client
JSON_RPC_URL = "https://s1.ripple.com:51234/"
client = JsonRpcClient(JSON_RPC_URL)

# PFT token issuer address
PFT_ISSUER = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"
# Rembrancer address for tracking PFT issuance
REMBRANCER_ADDRESS = "r4yc85M1hwsegVGZ1pawpZPwj65SVs8PzD"

# File to store balance history
BALANCE_HISTORY_FILE = 'balance_history.json'
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
        return {
            "last_update": None,
            "total_balance": 0,
            "balances": {}
        }

def save_previous_balances(data):
    with open(PREVIOUS_BALANCES_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def load_balance_history():
    try:
        with open(BALANCE_HISTORY_FILE, 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}

def save_balance_history(history):
    with open(BALANCE_HISTORY_FILE, 'w') as f:
        json.dump(history, f, indent=2)

def get_pft_balance(address):
    try:
        # Make a direct request to get account lines
        payload = {
            "method": "account_lines",
            "params": [{
                "account": address,
                "peer": PFT_ISSUER,
                "ledger_index": "validated"
            }]
        }
        
        response = requests.post(JSON_RPC_URL, json=payload)
        response.raise_for_status()
        result = response.json()
        
        if "result" in result and "lines" in result["result"]:
            for line in result["result"]["lines"]:
                if line.get("account") == PFT_ISSUER and line.get("currency") == "PFT":
                    return float(line.get("balance", "0"))
        return 0
    except Exception as e:
        print(f"Error getting balance for {address}: {str(e)}")
        return 0

def get_rembrancer_balance_change():
    """Get total PFT issued by looking at the balance change in the Rembrancer address"""
    try:
        # Get current balance
        current_balance = get_pft_balance(REMBRANCER_ADDRESS)
        
        # Load balance history
        balance_history = load_balance_history()
        rembrancer_history = balance_history.get(REMBRANCER_ADDRESS, [])
        
        if not rembrancer_history:
            print(f"No history found for Rembrancer address, returning current balance: {current_balance}")
            return abs(current_balance)
        
        # Get the earliest balance in our history
        earliest_balance = rembrancer_history[0]['balance']
        
        # Calculate the change (negative value indicates decrease)
        balance_change = earliest_balance - current_balance
        
        print(f"Rembrancer current balance: {current_balance}")
        print(f"Rembrancer earliest recorded balance: {earliest_balance}")
        print(f"Total PFT issued (based on Rembrancer balance decrease): {abs(balance_change)}")
        
        # Return absolute value of balance decrease
        return abs(balance_change)
        
    except Exception as e:
        print(f"Error getting Rembrancer balance change: {str(e)}")
        return 0

def get_previous_run_balance(address, history):
    """Get the balance from the previous run of the script for the given address"""
    # Get address history
    address_history = history.get(address, [])
    
    if len(address_history) <= 1:
        # If there's only one entry (the current one) or no entries, return 0
        return 0
    
    # Return the second most recent balance (latest is current run, second latest is previous run)
    # Sort by timestamp in descending order to ensure we get the most recent ones first
    sorted_history = sorted(address_history, key=lambda x: x['timestamp'], reverse=True)
    
    # The second entry (index 1) will be the previous run's balance
    if len(sorted_history) > 1:
        return sorted_history[1]['balance']
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

def format_discord_message(balances, balance_history):
    current_time = datetime.now(timezone.utc)
    current_time_str = current_time.strftime("%Y-%m-%d %H:%M UTC")
    
    # Get PFT issued based on Rembrancer balance change
    recent_issuance = get_rembrancer_balance_change()
    
    # Get current Remembrancer balance
    remembrancer_balance = get_pft_balance(REMBRANCER_ADDRESS)
    
    # Load previous balances
    previous_balances = load_previous_balances()
    previous_total = previous_balances['total_balance']
    
    # Calculate current total (excluding Remembrancer)
    total_current = sum(b['balance'] for b in balances if b['address'] != REMBRANCER_ADDRESS)
    total_previous_run = sum(get_previous_run_balance(b['address'], balance_history) for b in balances if b['address'] != REMBRANCER_ADDRESS)
    
    # Calculate balance changes since last update
    balance_increase = total_current - previous_total if previous_total > 0 else 0
    balance_increase_percentage = (balance_increase / previous_total * 100) if previous_total > 0 else 0
    
    # Calculate percentage of balance increase relative to new issuance
    change_in_total_held = total_current - total_previous_run if total_previous_run > 0 else 0
    issuance_percentage = (change_in_total_held / recent_issuance * 100) if recent_issuance > 0 else 0
    
    # Create the message content
    message = f"🏆 **PFT Holdings Leaderboard** - {current_time_str}\n\n"
    
    # Add issuance information
    message += f"🔄 **PFT Issued**: {recent_issuance:,.2f}\n"
    message += f"📊 **Total PFT Held**: {total_current:,.2f}"
    
    # Add total holdings change
    if total_previous_run > 0:
        total_change = format_balance_change(total_current, total_previous_run)
        message += f" {total_change}"
    message += "\n"
    
    # Add percentage of new issuance
    if previous_total > 0:
        message += f"📈 Percentage of New Issuance: {issuance_percentage:.1f}%\n"
    
    # Add Remembrancer PFT Balance
    message += f"💰 Remembrancer PFT Balance: {remembrancer_balance:,.2f}\n"
    
    message += "\n"
    
    # Add all holders (no limit), excluding Rembrancer
    i = 1
    for balance in balances:
        # Skip Rembrancer address
        if balance['address'] == REMBRANCER_ADDRESS:
            continue
            
        nickname = balance['nickname'] or 'Anonymous'
        address = balance['address']
        amount = f"{balance['balance']:,.2f}"
        
        # Calculate change indicator using previous run balance
        prev_balance = get_previous_run_balance(address, balance_history)
        change_indicator = format_balance_change(balance['balance'], prev_balance)
        
        message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT {change_indicator}\n"
        i += 1
    
    return {
        "content": message,
        "username": "PFT Tracker",
        "avatar_url": "https://xrpl.org/assets/img/xrp-symbol-white.svg"
    }

def main():
    # Load tracked addresses and balance history
    tracked_addresses = load_data()
    balance_history = load_balance_history()
    current_time = datetime.now(timezone.utc).isoformat()
    
    # Get current balances
    balances = []
    
    # Update balance history for tracked addresses
    for address, info in tracked_addresses.items():
        balance = get_pft_balance(address)
        balances.append({
            'address': address,
            'nickname': info.get('nickname', ''),
            'balance': balance
        })
        
        # Add to history
        if address not in balance_history:
            balance_history[address] = []
        
        balance_history[address].append({
            'timestamp': current_time,
            'balance': balance
        })
        
        # Keep only last 7 days of history
        cutoff_time = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        balance_history[address] = [
            entry for entry in balance_history[address]
            if entry['timestamp'] >= cutoff_time
        ]
    
    # Sort by balance
    balances.sort(key=lambda x: x['balance'], reverse=True)
    
    # Format message
    message = format_discord_message(balances, balance_history)
    
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
    
    # Save updated balance history
    save_balance_history(balance_history)
    
    # Save current balances as previous balances for next update
    previous_balances = {
        "last_update": current_time,
        "total_balance": sum(b['balance'] for b in balances),
        "balances": {b['address']: b['balance'] for b in balances}
    }
    save_previous_balances(previous_balances)

if __name__ == '__main__':
    main() 