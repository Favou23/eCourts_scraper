# eCourts Scraper

This project implements a CLI and a small web UI that fetches court cause-lists from the official eCourts service and helps you:

- Check whether a case (by CNR or by case type/number/year) is listed today or tomorrow.
- Show the serial number and court name (if present in the cause list).
- Optionally download the case PDF if available.
- Download the entire cause list HTML and (from the UI) download matched PDFs as a ZIP.

Important: all data is fetched in real time from the live eCourts site (https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/). The server does not store sample select data; dependent selects (districts/complexes) are requested on demand.

## Setup

Create a virtualenv and install dependencies (PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## CLI usage

Check a case by CNR (searches cause list for today by default):

```powershell
python -m ecourts_scraper.cli check --cnr ABCD1234567890 --when today
```

Search tomorrow's list:

```powershell
python -m ecourts_scraper.cli check --cnr ABCD1234567890 --when tomorrow
```

Check by case type/number/year:

```powershell
python -m ecourts_scraper.cli check --type "Criminal" --number 123 --year 2024 --when today
```

Cause list helpers:

- Print initial select options parsed from the landing page:

```powershell
python -m ecourts_scraper.cli causelist-options
```

- Download cause list HTML for a date (use correct select values as needed):

```powershell
python -m ecourts_scraper.cli causelist --date today --state 26 --district 12 --complex 345 --est 678 --court-no 9
```

- Download PDFs for a court complex (first found or all judges):

```powershell
# Download first PDF found for the complex on the date
python -m ecourts_scraper.cli causelist-download --state 26 --district 12 --complex 345 --date 2025-10-16

# Download all judge PDFs for the complex on the date
python -m ecourts_scraper.cli causelist-download --state 26 --district 12 --complex 345 --date 2025-10-16 --all-judges
```

Notes:
- Do NOT include angle brackets when passing arguments in PowerShell. Use `--cnr ABCD1234` (not `--cnr <ABCD1234>`).
- CLI commands save some results as JSON (for example, `check` saves `result_YYYY-MM-DD.json`).

## Web UI (recommended for interactive use)

Run the Flask UI locally from project root:

```powershell
# Option A: use the convenience script
python run_web.py

# Option B: use the flask CLI
$env:FLASK_APP = 'ecourts_scraper.web'
$env:FLASK_ENV = 'development'
python -m flask run

# then open http://127.0.0.1:5000 in your browser
```

What the UI provides
- Real-time dependent selects: when you choose a State the UI requests districts from the server; when you choose a District the UI requests Court Complexes. These calls are live (no cached sample data).
- CAPTCHA workflow: when you click Get Cause List the UI shows the CAPTCHA image fetched from eCourts; you must type it before the server can POST the cause-list request.
- PDF ZIP download: check the "Download PDFs as ZIP" checkbox before submitting to have the server fetch all found PDF links and return them as a ZIP attachment.

Usage example (browser):
1. Open the UI, select a State.
2. Wait for Districts to load, then select a District.
3. Wait for Complexes to load, optionally enter a Court Name and choose a date.
4. Type the CAPTCHA you see and either click Get Cause List or check "Download PDFs as ZIP" and submit to download.

## How it works (implementation notes)

- `ecourts_scraper.scraper.ECourtsScraper.get_cause_list_page()` fetches the landing page and parses initial `<select>` options.
- `get_dependent_options(state, district)` calls the cause list endpoint with `sess_state_code` and/or `sees_dist_code` to obtain dependent selects in the same way the site's AJAX would.
- The web UI exposes two AJAX endpoints:
  - `/api/districts?state=<code>` — returns districts for the state
  - `/api/complexes?state=<code>&district=<code>` — returns complexes for the state+district
- On submit, `submit_cause_list_form()` posts the form (using the provided CAPTCHA text) and the server extracts PDF links from the returned HTML. If you requested download, the server downloads the PDF bytes and returns a ZIP.

## Limitations & caveats

- CAPTCHA: you must manually type the CAPTCHA displayed in the UI. If the CAPTCHA is incorrect the eCourts server will reject the request and the UI will display an error.
- PDF discovery: the scraper looks for direct `.pdf` links in the returned cause list HTML. Some cause lists link to intermediate pages that contain the PDF 
- Rate-limiting: repeated automated requests to eCourts can trigger rate limits. For bulk downloads, we should add polite rate-limiting and retries.

## Troubleshooting

results.
- Captcha errors: if the submitted CAPTCHA is wrong you will get an error page. Try refreshing the page (which requests a fresh CAPTCHA) and re-try.

## Tests

Run the unit tests with:

```powershell
python -m pytest -q
```


