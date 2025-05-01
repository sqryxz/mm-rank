import json
import requests
from datetime import datetime
import time
import os
from pft_data import save_issuance_data

class PFTTracker:
    def __init__(self):
        self.issuer_address = "rnQUEEg8yyjrwk9FhyXpKavHyCRJM9BDMW"
        self.rembrancer_address = "r4yc85M1hwsegVGZ1pawpZPwj65SVs8PzD"
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

    def get_pft_balance(self, address):
        try:
            payload = {
                "method": "account_lines",
                "params": [{
                    "account": address,
                    "peer": self.issuer_address,
                    "ledger_index": "validated"
                }]
            }
            
            response = requests.post(self.api_url, json=payload)
            response.raise_for_status()
            result = response.json()
            
            if "result" in result and "lines" in result["result"]:
                for line in result["result"]["lines"]:
                    if line.get("account") == self.issuer_address and line.get("currency") == "PFT":
                        return float(line.get("balance", "0"))
            return 0
        except Exception as e:
            print(f"Error getting balance for {address}: {str(e)}")
            return 0

    def analyze_issuance(self):
        try:
            # Get current balance
            current_balance = self.get_pft_balance(self.rembrancer_address)
            
            # Load balance history
            try:
                with open('balance_history.json', 'r') as f:
                    balance_history = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError):
                balance_history = {}
            
            rembrancer_history = balance_history.get(self.rembrancer_address, [])
            
            if not rembrancer_history:
                print(f"No history found for Rembrancer address, using current balance: {current_balance}")
                total_issuance = abs(current_balance)
            else:
                # Get the earliest balance in our history
                earliest_balance = rembrancer_history[0]['balance']
                
                # Calculate the change
                total_issuance = abs(current_balance - earliest_balance)
                
                print(f"Rembrancer current balance: {current_balance}")
                print(f"Rembrancer earliest recorded balance: {earliest_balance}")
                print(f"Total PFT issued (based on Rembrancer balance change): {total_issuance}")

            # Save the issuance data
            save_issuance_data(total_issuance)

            report = {
                'total_issuance': total_issuance,
                'all_time_issuance': total_issuance,
                'transactions': [],
                'from_time': self.last_check_time,
                'to_time': int(time.time())
            }

            self.save_last_check_time()
            return report
            
        except Exception as e:
            print(f"Error analyzing issuance: {str(e)}")
            return None

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