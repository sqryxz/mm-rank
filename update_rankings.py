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

def get_issuer_payments_12h():
    """Get total PFT issued in the last 12 hours by looking at transactions from the issuer"""
    try:
        # Get current ledger info
        ledger_response = requests.post(JSON_RPC_URL, json={
            "method": "ledger",
            "params": [
                {
                    "ledger_index": "validated",
                    "accounts": False,
                    "full": False,
                    "transactions": False,
                    "expand": False,
                    "owner_funds": False
                }
            ]
        }).json()
        
        current_ledger = int(ledger_response["result"]["ledger_index"])
        # Estimate ledger from 12 hours ago (assuming ~4s per ledger)
        ledgers_per_12h = int((12 * 60 * 60) / 4)  # ~10800 ledgers
        ledger_12h_ago = current_ledger - ledgers_per_12h
        
        print(f"Current ledger: {current_ledger}")
        print(f"Estimated ledger 12h ago: {ledger_12h_ago}")
        
        # Get transactions
        tx_response = requests.post(JSON_RPC_URL, json={
            "method": "account_tx",
            "params": [
                {
                    "account": PFT_ISSUER,
                    "ledger_index_min": ledger_12h_ago,
                    "ledger_index_max": current_ledger,
                    "binary": False,
                    "forward": False,
                    "limit": 400
                }
            ]
        }).json()

        total_issued = 0
        
        if "result" in tx_response and "transactions" in tx_response["result"]:
            print(f"Found {len(tx_response['result']['transactions'])} transactions")
            
            for tx in tx_response["result"]["transactions"]:
                if "tx" not in tx or "TransactionType" not in tx["tx"]:
                    continue
                    
                tx_type = tx["tx"]["TransactionType"]
                if tx_type not in ["Payment", "TrustSet"]:
                    continue
                    
                if "meta" not in tx or "TransactionResult" not in tx["meta"] or tx["meta"]["TransactionResult"] != "tesSUCCESS":
                    continue
                
                print(f"Processing {tx_type} transaction")
                
                if tx_type == "Payment":
                    if ("Amount" in tx["tx"] and 
                        isinstance(tx["tx"]["Amount"], dict) and
                        tx["tx"]["Amount"].get("currency") == "PFT" and
                        tx["tx"]["Amount"].get("issuer") == PFT_ISSUER):
                        
                        amount = float(tx["tx"]["Amount"]["value"])
                        total_issued += amount
                        print(f"Found PFT payment: {amount}")
                
                elif tx_type == "TrustSet":
                    if "LimitAmount" in tx["tx"]:
                        limit = tx["tx"]["LimitAmount"]
                        if (isinstance(limit, dict) and 
                            limit.get("currency") == "PFT" and
                            limit.get("issuer") == PFT_ISSUER):
                            
                            trust_amount = float(limit["value"])
                            total_issued += trust_amount
                            print(f"Found PFT trust set: {trust_amount}")
        
        print(f"Total PFT issued from transactions: {total_issued}")
        return total_issued
        
    except Exception as e:
        print(f"Error getting issuer payments: {str(e)}")
        return 0

def get_balance_12h_ago(address, history):
    current_time = datetime.now(timezone.utc)
    twelve_hours_ago = current_time - timedelta(hours=12)
    
    # Get address history
    address_history = history.get(address, [])
    
    # Find the closest balance to 12 hours ago
    closest_balance = 0
    closest_time_diff = timedelta(days=365)  # Large initial value
    
    for entry in address_history:
        entry_time = datetime.fromisoformat(entry['timestamp'])
        time_diff = abs(entry_time - twelve_hours_ago)
        
        if time_diff < closest_time_diff and entry_time <= twelve_hours_ago:
            closest_time_diff = time_diff
            closest_balance = entry['balance']
    
    return closest_balance

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
    
    # Get PFT issued in last 12 hours from actual transactions
    recent_issuance = get_issuer_payments_12h()
    
    # Load previous balances
    previous_balances = load_previous_balances()
    previous_total = previous_balances['total_balance']
    
    # Calculate current total
    total_current = sum(b['balance'] for b in balances)
    total_12h_ago = sum(get_balance_12h_ago(b['address'], balance_history) for b in balances)
    
    # Calculate balance changes since last update
    balance_increase = total_current - previous_total if previous_total > 0 else 0
    balance_increase_percentage = (balance_increase / previous_total * 100) if previous_total > 0 else 0
    
    # Calculate percentage of balance increase relative to new issuance
    issuance_percentage = (balance_increase / recent_issuance * 100) if recent_issuance > 0 else 0
    
    # Create the message content
    message = f"🏆 **PFT Holdings Leaderboard** - {current_time_str}\n\n"
    
    # Add issuance information
    message += f"🔄 **PFT Issued (Last 12h)**: {recent_issuance:,.2f}\n"
    message += f"📊 **Total PFT Held**: {total_current:,.2f}"
    
    # Add total holdings change
    if total_12h_ago > 0:
        total_change = format_balance_change(total_current, total_12h_ago)
        message += f" {total_change}"
    message += "\n"
    
    # Add change in holdings as percentage of total tracked
    message += f"📈 **Change in PFT Held (12h)**: "
    if total_current == total_12h_ago:
        message += "No change"
    else:
        change = total_current - total_12h_ago
        change_symbol = "⬆️" if change > 0 else "⬇️"
        change_percentage = (abs(change) / total_current * 100) if total_current > 0 else 0
        message += f"{change_symbol} {change_percentage:.1f}% of tracked holdings"
    message += "\n"
    
    # Add balance changes since last update
    if previous_total > 0:
        message += f"\n📊 **Changes Since Last Update**:\n"
        message += f"💰 Total Balance Increase: {balance_increase:,.2f} PFT (+{balance_increase_percentage:.1f}%)\n"
        message += f"📈 Percentage of New Issuance: {issuance_percentage:.1f}%\n"
    
    message += "\n"
    
    # Add all holders (no limit)
    for i, balance in enumerate(balances, 1):
        nickname = balance['nickname'] or 'Anonymous'
        address = balance['address']
        amount = f"{balance['balance']:,.2f}"
        
        # Calculate change indicator using 12h ago balance
        prev_balance = get_balance_12h_ago(address, balance_history)
        change_indicator = format_balance_change(balance['balance'], prev_balance)
        
        # Add change since last update if available
        last_balance = previous_balances['balances'].get(address, 0)
        if last_balance > 0:
            balance_change = balance['balance'] - last_balance
            if balance_change != 0:
                change_percent = (balance_change / last_balance * 100)
                change_str = f" (Δ{'+' if balance_change > 0 else ''}{balance_change:,.2f}, {change_percent:+.1f}% since last update)"
                message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT {change_indicator}{change_str}\n"
            else:
                message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT {change_indicator}\n"
        else:
            message += f"{i}. **{nickname}** (`{address[:6]}...{address[-4:]}`) - {amount} PFT {change_indicator}\n"
    
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