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

    # Nerf values for specific addresses
    NERF_AMOUNTS = {
        "rPLpK9KKmjYzPQ8Faem7BRwfpQfCe9zrHS": 233545,   # wizbubba
        "rNTuZK66KQfWiwwBucvjXsonf5iD1BQJyH": 101412,   # hitori*
        "rs1yY1qVJ4ddvPXQs86EYW1HC3QdWu7NFo": 95607,    # perry
        "rMh3gsTKvLEpiucuxdkTybGE6A2tv9CLHE": 78814,    # nigel
        "rLvH7pxCCee7kFJo2Cn6NQy8GS33RHXk3U": 71924,    # btseal
        "rwonaUde5Vaa8mqnhqEgA29gcCfrv7qS9p": 63815,    # jolly*
        "rMm27Xh1JzGL4evVS1ZB1H25JpJapodSL1": 62601,    # lc66*
        "rGVzFTK1H9iNo3C2MDyx6M6K4tfs4PocPA": 39719,    # meech*
        "rpo5tVeCqigav9ZBpmPvYWeSBExSbYAK3c": 34789,    # snakespartan*
        "rPWD8aoBvP55T6mPSwxSPC52J2eN14PoHe": 31741,    # wilson
        "rKDYJt9gee8dGVadu6kb3vdBVTdiQRbcHP": 27038,    # russolini
    }

    # Apply nerf to balances for display only
    nerfed_balances = []
    for b in balances:
        nerfed_balance = b['balance']
        if b['address'] in NERF_AMOUNTS:
            nerfed_balance = max(0, nerfed_balance - NERF_AMOUNTS[b['address']])
        nerfed_balances.append({
            'address': b['address'],
            'nickname': b['nickname'],
            'balance': nerfed_balance
        })

    # Sort nerfed_balances by balance descending (most to least)
    nerfed_balances.sort(key=lambda x: x['balance'], reverse=True)

    # Load PFT issued during the most recent period (calculated by pft_tracker.py)
    period_issuance = load_issuance_data() 

    # Get current Remembrancer balance
    remembrancer_balance = get_pft_balance(REMBRANCER_ADDRESS)

    # Load previous total balance for comparison
    previous_balances = load_previous_balances()
    previous_total = previous_balances['total_balance']

    # Calculate current total (excluding Remembrancer) using the nerfed balances
    total_current = sum(b['balance'] for b in nerfed_balances if b['address'] != REMBRANCER_ADDRESS)
    # Calculate the total from the *previous run* using history (apply nerf to previous run as well)
    total_previous_run = sum(
        max(0, get_previous_run_balance(b['address'], balance_history) - NERF_AMOUNTS.get(b['address'], 0))
        for b in balances if b['address'] != REMBRANCER_ADDRESS
    )

    # Calculate balance changes since last actual run (using history)
    change_in_total_held = total_current - total_previous_run
    # Calculate percentage relative to the recent period's issuance
    issuance_percentage = (change_in_total_held / period_issuance * 100) if period_issuance > 0 else 0

    # Create the message content
    message = f"🏆 **PFT Holdings Leaderboard - Post Nerf** - {current_time_str}\n\n"

    # Add issuance information for the recent period
    message += f"🔄 **PFT Issued (Recent)**: {period_issuance:,.2f}\n"
    message += f"📊 **Total PFT Held**: {total_current:,.2f}"

    # Add total holdings change based on previous run
    if total_previous_run != 0:
        total_change = format_balance_change(total_current, total_previous_run)
        message += f" {total_change}"
    message += "\n"

    if period_issuance > 0:
        message += f"📈 Percentage of New Issuance: {issuance_percentage:.1f}%\n"

    message += f"💰 Remembrancer PFT Balance: {remembrancer_balance:,.2f}\n"
    message += "\n"

    # Add all holders (no limit), excluding Remembrancer
    i = 1
    for b, orig_b in zip(nerfed_balances, balances):
        if b['address'] == REMBRANCER_ADDRESS:
            continue
        nickname = b['nickname'] or 'Anonymous'
        address = b['address']
        amount = f"{b['balance']:,.2f}"
        # Calculate change indicator using nerfed previous run balance
        prev_balance = max(0, get_previous_run_balance(address, balance_history) - NERF_AMOUNTS.get(address, 0))
        change_indicator = format_balance_change(b['balance'], prev_balance)
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
    current_time = datetime.now(timezone.utc)
    
    # Get current balances
    current_balances = [] # Renamed to avoid confusion with the parameter name in format_discord_message
    
    # Update balance history for tracked addresses
    for address, info in tracked_addresses.items():
        balance = get_pft_balance(address)
        current_balances.append({
            'address': address,
            'nickname': info.get('nickname', ''),
            'balance': balance
        })
        
        # Add to history
        if address not in balance_history:
            balance_history[address] = []
        
        balance_history[address].append({
            'timestamp': current_time.isoformat(),
            'balance': balance
        })
        
        # Keep only last 7 days of history
        cutoff_time = (current_time - timedelta(days=7)).isoformat()
        balance_history[address] = [
            entry for entry in balance_history[address]
            if entry['timestamp'] >= cutoff_time
        ]
    
    # Sort by balance
    current_balances.sort(key=lambda x: x['balance'], reverse=True)
    
    # Format message using the fetched current balances and updated history
    message_payload = format_discord_message(current_balances, balance_history)

    # Save the updated balance history
    save_balance_history(balance_history)
    
    # Save current balances as previous for next run comparison
    # Store the total *excluding* remembrancer for consistent comparison with leaderboard total
    current_total_excluding_rembrancer = sum(b['balance'] for b in current_balances if b['address'] != REMBRANCER_ADDRESS)
    save_previous_balances({
        "last_update": current_time.isoformat(),
        "total_balance": current_total_excluding_rembrancer, # Save the correct total
        "balances": {b['address']: b['balance'] for b in current_balances}
    })

    # Send message to Discord
    webhook_url = os.environ.get('DISCORD_WEBHOOK_URL')
    if webhook_url:
        try:
            response = requests.post(webhook_url, json=message_payload)
            response.raise_for_status() # Raise an exception for bad status codes (4xx or 5xx)
            print("Successfully sent message to Discord.")
        except requests.exceptions.RequestException as e:
            print(f"Error sending message to Discord: {e}")
    else:
        print("DISCORD_WEBHOOK_URL environment variable not set. Skipping Discord notification.")

if __name__ == '__main__':
    main() 