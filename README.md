# ASU Seat Studio

A minimalist web app and CLI monitor for tracking ASU class seat availability.

## What changed

- Preserved the original Selenium scraping workflow
- Extracted the monitor logic into reusable Python functions
- Added a Flask web interface with watched section highlighting, live stats, and optional iMessage alerts
- Kept the original terminal-based `NotifyMe.py` flow working

## Setup

1. Create and activate a Python virtual environment.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Make sure Google Chrome is installed.
4. For iMessage alerts, run on macOS with Messages configured.

## Run the web app

To start the app locally from a fresh terminal:

```bash
cd "/Users/jdemeule/Documents/New project/ASU"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Then open `http://127.0.0.1:5000` in your browser.

## Run the CLI monitor

```bash
python NotifyMe.py
```

## Inputs

- `subject`: example `MAT`
- `catalog_nbr`: example `101`
- `term`: example `2257`
- `watched`: comma-separated section numbers like `12345,12346`
- `phones`: comma-separated E.164 phone numbers like `+12065551234,+12065559876`

## Notes

- The app currently searches Tempe and iCourse sections, matching the original script.
- Auto-refresh is available in the web UI for repeated checks.
- iMessage notifications are only sent for watched sections with open seats.
- If you see a TLS or `cacert.pem` error after deleting or recreating a virtual environment, deactivate the shell, reactivate the current `.venv`, and restart the app.
