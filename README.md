# MM PFT Tracker

A Flask web application to track PFT token balances on the XRPL network.

## Features

- Track multiple XRPL addresses
- View PFT token balances
- Add/remove addresses
- Set nicknames for addresses
- Auto-updating balances
- Sorted display by balance amount

## Setup

1. Clone the repository:
```bash
git clone https://github.com/sqryxz/mm-rank.git
cd mm-rank
```

2. Install dependencies:
```bash
pip install flask xrpl-py
```

3. Run the application:
```bash
python3 app.py
```

The application will be available at `http://localhost:5000`

## Configuration

- The XRPL node URL can be configured in `app.py`
- PFT token issuer address is configured in `app.py`

## License

MIT 