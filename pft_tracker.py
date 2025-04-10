import json
import requests
from datetime import datetime
import time
import os
from pft_data import save_issuance_data

class PFTTracker:
    def __init__(self):
        self.issuer_address = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"
        self.api_url = "https://s1.ripple.com:51234/"
        self.last_check_time = None
        self.load_last_check_time()

    def load_last_check_time(self):
        try:
            with open('last_check.json', 'r') as f:
                data = json.load(f)
                self.last_check_time = data.get('last_check_time')
        except FileNotFoundError:
            # On first run, look back 24 hours to show some initial data
            self.last_check_time = int(time.time()) - (24 * 60 * 60)

    def save_last_check_time(self):
        with open('last_check.json', 'w') as f:
            json.dump({'last_check_time': int(time.time())}, f)

    def get_transactions(self):
        payload = {
            "method": "account_tx",
            "params": [{
                "account": self.issuer_address,
                "binary": False,
                "forward": False,
                "ledger_index_min": -1,
                "ledger_index_max": -1,
                "limit": 200  # Increased limit to catch more transactions
            }]
        }

        try:
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching transactions: {e}")
            return None

    def analyze_issuance(self):
        tx_data = self.get_transactions()
        if not tx_data:
            return None

        total_issuance = 0
        transactions = []
        all_time_issuance = 0

        for tx in tx_data.get('result', {}).get('transactions', []):
            tx_type = tx.get('tx', {}).get('TransactionType')
            timestamp = tx.get('tx', {}).get('date')
            
            if tx_type == "Payment":
                amount = tx.get('tx', {}).get('Amount', {})
                if isinstance(amount, dict) and amount.get('currency') == "PFT":
                    value = float(amount.get('value', 0))
                    destination = tx.get('tx', {}).get('Destination', 'Unknown')
                    all_time_issuance += value
                    
                    if timestamp > self.last_check_time:
                        total_issuance += value
                        transactions.append({
                            'hash': tx['tx']['hash'],
                            'amount': value,
                            'destination': destination,
                            'timestamp': timestamp
                        })

        # Save the all-time issuance data for the leaderboard
        save_issuance_data(all_time_issuance)

        report = {
            'total_issuance': total_issuance,
            'all_time_issuance': all_time_issuance,
            'transactions': transactions,
            'from_time': self.last_check_time,
            'to_time': int(time.time())
        }

        self.save_last_check_time()
        return report

def format_report(report):
    output = []
    output.append("# PFT Issuance Report\n")
    
    # Add timestamp
    output.append(f"Report generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}\n")
    
    # Add period
    from_time = datetime.fromtimestamp(report['from_time']).strftime('%Y-%m-%d %H:%M:%S')
    to_time = datetime.fromtimestamp(report['to_time']).strftime('%Y-%m-%d %H:%M:%S')
    output.append(f"Period: {from_time} to {to_time}\n")
    
    # Add summary
    output.append(f"## Summary")
    output.append(f"Total PFT Issued (this period): {report['total_issuance']:,.2f} PFT")
    output.append(f"Total PFT Issued (all time in fetch window): {report['all_time_issuance']:,.2f} PFT\n")
    output.append(f"Number of Transactions (this period): {len(report['transactions'])}\n")
    
    # Add transaction details
    if report['transactions']:
        output.append("## Detailed Transactions\n")
        output.append("| Time | Amount | Destination | Transaction Hash |")
        output.append("|------|---------|-------------|-----------------|")
        
        for tx in sorted(report['transactions'], key=lambda x: x['timestamp'], reverse=True):
            time_str = datetime.fromtimestamp(tx['timestamp']).strftime('%Y-%m-%d %H:%M:%S')
            output.append(f"| {time_str} | {tx['amount']:,.2f} PFT | {tx['destination']} | [{tx['hash'][:8]}...](https://livenet.xrpl.org/transactions/{tx['hash']}) |")
    else:
        output.append("\n## No New Transactions\n")
        output.append("No new PFT issuance transactions were found in this period.")
        output.append("The next report will check for transactions after this timestamp.")
    
    return "\n".join(output)

def main():
    tracker = PFTTracker()
    report = tracker.analyze_issuance()
    
    if report:
        formatted_report = format_report(report)
        print(formatted_report)
    else:
        print("Error: Unable to generate PFT issuance report. Please check the XRPL API connection.")

if __name__ == "__main__":
    main() 