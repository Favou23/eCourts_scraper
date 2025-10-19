# eCourts Scraper 🏛️

A Python CLI and web application to fetch court case information and cause lists from the official eCourts India service.

[![Python Version](https://img.shields.io/badge/python-3.8%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📑 Table of Contents

- [Features](#-features)
- [Installation](#-installation)
- [CLI Usage](#-cli-usage)
  - [Check Case Status](#-check-case-status)
  - [Browse Available Courts](#%EF%B8%8F-browse-available-courts)
  - [Download Cause List](#-download-cause-list)
  - [Search in Cause List](#-search-in-cause-list)
  - [Download PDFs](#-download-pdfs)
- [Web UI](#-web-ui)
- [Command Reference](#-command-reference)
- [Example Workflow](#-example-workflow)
- [Important Notes](#-important-notes)
- [Troubleshooting](#-troubleshooting)
- [Project Structure](#-project-structure)
- [Requirements](#-requirements)
- [Limitations](#%EF%B8%8F-limitations)

---

## ✨ Features

- ✅ **Check case status** by CNR or case details (type/number/year)
- ✅ **View case listings** for today or tomorrow
- ✅ **Download cause lists** as HTML or PDF
- ✅ **Interactive web UI** with dependent dropdowns (State → District → Complex)
- ✅ **Save results** as JSON for record-keeping

---

## 🚀 Installation

### Prerequisites

- Python 3.8 or higher
- pip (Python package manager)
- Virtual environment (recommended)

### Step 1: Clone the Repository

```bash
git clone https://github.com/yourusername/ecourts_scraper.git
cd ecourts_scraper
```

### Step 2: Create Virtual Environment

**Windows (PowerShell):**
```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### Step 3: Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 💻 CLI Usage

The CLI provides several commands to interact with eCourts data.

### 📋 Check Case Status

Check if a case is listed today or tomorrow and retrieve case information.

#### By CNR (Case Number Reference)

```bash
# Check today's listing
python -m ecourts_scraper.cli check --cnr "DL01-123456-2025"

# Check tomorrow's listing
python -m ecourts_scraper.cli check --cnr "DL01-123456-2025" --tomorrow

# Download PDF if available
python -m ecourts_scraper.cli check --cnr "DL01-123456-2025" --download-pdf
```

#### By Case Details

```bash
# Check with case type, number, and year
python -m ecourts_scraper.cli check --type CRL --number 12345 --year 2025

# Check tomorrow's listing
python -m ecourts_scraper.cli check --type CRL --number 12345 --year 2025 --tomorrow
```

**Output:**
- ✅ Displays case serial number and court name
- 📄 Saves results to `result_YYYY-MM-DD.json`
- 🖥️ Shows case details in formatted console output

---

### 🏛️ Browse Available Courts

Get lists of states, districts, and court complexes.

#### List All States

```bash
python -m ecourts_scraper.cli causelist-options
```

**Example Output:**
```
States:
  8 -> Bihar
  26 -> Delhi
  23 -> Madhya Pradesh
  ...
```

#### List Districts for a State

```bash
# Example: Get districts for Bihar (state code 8)
python -m ecourts_scraper.cli causelist-options --state 8
```

**Example Output:**
```
Districts:
  26 -> Patna
  28 -> Gaya
  15 -> Muzaffarpur
  ...
```

#### List Court Complexes for a District

```bash
# Example: Get complexes for Bihar, Patna district
python -m ecourts_scraper.cli causelist-options --state 8 --district 26
```

> **💡 Tip:** Use the numeric codes from the output in subsequent commands.

---

### 📥 Download Cause List

Download the complete cause list HTML for a specific court and date.

```bash
# Download today's cause list
python -m ecourts_scraper.cli causelist --state 8 --district 26 --date today

# Download tomorrow's cause list
python -m ecourts_scraper.cli causelist --state 8 --district 26 --date tomorrow

# With court complex (optional)
python -m ecourts_scraper.cli causelist --state 8 --district 26 --complex 1 --date today
```

**Output:** 
- 📄 Saves HTML file as `causelist_YYYY-MM-DD.html`

---

### 🔍 Search in Cause List

Search for a specific case in a downloaded cause list.

```bash
# Search by CNR
python -m ecourts_scraper.cli search-causelist \
  --cnr "DL01-123456-2024" \
  --state 26 \
  --district 1

# Search by case number or keyword
python -m ecourts_scraper.cli search-causelist \
  --query "12345/2024" \
  --state 26 \
  --district 1 \
  --date today
```

---

### 📄 Download PDFs

Download PDF files for a specific court complex and date.

```bash
# Download first PDF found
python -m ecourts_scraper.cli causelist-download \
  --state 8 \
  --district 26 \
  --complex 1 \
  --date 2025-10-20

# Download all judge PDFs
python -m ecourts_scraper.cli causelist-download \
  --state 8 \
  --district 26 \
  --complex 1 \
  --date 2025-10-20 \
  --all-judges
```

**Output:** 
- 📂 Downloads PDF(s) to `downloads/` folder

---

## 🌐 Web UI

Launch the interactive web interface for easier navigation.

### Start the Server

**Option 1: Using the convenience script**
```bash
python run_web.py
```

**Option 2: Using Flask CLI**

**Windows (CMD):**
```cmd
set FLASK_APP=ecourts_scraper.webapi
flask run
```

**Windows (PowerShell):**
```powershell
$env:FLASK_APP="ecourts_scraper.webapi"
flask run
```

**Linux/macOS:**
```bash
export FLASK_APP=ecourts_scraper.webapi
flask run
```

Then open **http://127.0.0.1:5000** in your browser.

### Using the Web UI

1. **Select State** - Choose from the dropdown
2. **Select District** - Wait for districts to load, then choose
3. **Select Court Complex** - Wait for complexes to load, then choose
4. **Select Court Number** - Choose the specific court
5. **Pick Date** - Select the date for the cause list
6. **Submit** - Get the cause list

---

## 📚 Command Reference

### All Available Commands

| Command | Description |
|---------|-------------|
| `check` | Check case status by CNR or case details |
| `search-causelist` | Search for a case in a specific court's cause list |
| `causelist` | Download full cause list HTML |
| `causelist-options` | List available states/districts/complexes |
| `causelist-download` | Download cause list PDFs |

### Get Help for Any Command

```bash
# General help
python -m ecourts_scraper.cli --help

# Command-specific help
python -m ecourts_scraper.cli check --help
python -m ecourts_scraper.cli causelist-options --help
python -m ecourts_scraper.cli causelist --help
```

---

## 🎯 Example Workflow

Here's a complete example of checking a case:

```bash
# Step 1: Find your state code
python -m ecourts_scraper.cli causelist-options
# Output shows: 26 -> Delhi

# Step 2: Find your district code
python -m ecourts_scraper.cli causelist-options --state 26
# Output shows: 1 -> Central District

# Step 3: Download today's cause list
python -m ecourts_scraper.cli causelist --state 26 --district 1 --date today
# Output: causelist_2025-10-19.html

# Step 4: Search for your case in the downloaded list
python -m ecourts_scraper.cli search-causelist \
  --cnr "DL01-123456-2024" \
  --state 26 \
  --district 1
```

---

## 📌 Important Notes

### About CNR Numbers

- **CNR (Case Number Reference)** is a unique identifier for each case
- **Format:** `STATECODE##-########-YEAR` (e.g., `DL01-123456-2024`)
- ⚠️ You must use **real CNR numbers** from the eCourts system
- ⚠️ Test/fake CNRs will return "HTTP 400" errors

### Getting Real CNR Numbers

1. Visit [eCourts India](https://services.ecourts.gov.in/ecourtindia_v6/)
2. Navigate to **"Case Status"** section
3. Search for any public case
4. Copy the CNR from the results
5. Use that CNR in the CLI commands

### State/District Codes

- Use `causelist-options` command to get valid codes
- State and district combinations must be valid
- Invalid combinations will return "HTTP 400" errors

---

## 🔧 Troubleshooting

### Common Errors

#### ❌ HTTP 400 - Invalid Parameter

**Cause:** Invalid CNR, fake case number, or wrong state/district combination

**Solution:** 
- Use real CNR from eCourts website
- Verify state/district codes using `causelist-options`
- Ensure CNR format matches: `STATECODE##-########-YEAR`

#### ❌ File not found

**Cause:** Cause list download failed

**Solution:** 
- Check state/district codes are valid
- Ensure date is valid (today or tomorrow)
- Verify internet connection

#### ❌ No PDF links found

**Cause:** The court hasn't published PDFs for that date

**Solution:** 
- Try a different date
- Check the HTML file manually
- Contact the court to verify PDF availability

### Getting Debug Information

Enable debug mode for detailed output:

**Linux/macOS:**
```bash
export DEBUG=1
python -m ecourts_scraper.cli check --cnr "..."
```

**Windows (CMD):**
```cmd
set DEBUG=1
python -m ecourts_scraper.cli check --cnr "..."
```

**Windows (PowerShell):**
```powershell
$env:DEBUG=1
python -m ecourts_scraper.cli check --cnr "..."
```

---

## 📁 Project Structure

```
ecourts_scraper/
├── __init__.py
├── cli.py              # CLI commands and interface
├── scraper.py          # Core scraping logic
├── webapi.py           # Flask web server
├── utils.py            # Helper functions
├── templates/          # Web UI HTML templates
│   └── index.html
└── static/             # CSS, JS, and assets
    └── style.css

downloads/              # Downloaded PDF files (auto-created)
*.html                  # Downloaded cause lists
*.json                  # Saved results
```

---

## 📦 Requirements

- **Python:** 3.8 or higher
- **Core Dependencies:**
  - `requests` - HTTP requests
  - `beautifulsoup4` - HTML parsing
  - `click` - CLI framework
  - `flask` - Web framework
  - `flask-cors` - CORS support

See [`requirements.txt`](requirements.txt) for the complete list.

---

## ⚠️ Limitations

- Requires real case data from eCourts (no test/demo mode available)
- Rate limiting may apply for bulk requests
- Some courts may not publish cause lists online
- CAPTCHA handling not implemented (for web automation)

---

## 📄 License

This project is for **educational purposes only**. 

Please respect eCourts terms of service and avoid excessive automated requests that may impact their servers.

---

## 👨‍💻 Author

Developed as part of an internship task - October 2025

---

## 🤝 Support

For issues or questions:

1. ✅ Check the [Troubleshooting](#-troubleshooting) section
2. ✅ Review command help: `python -m ecourts_scraper.cli <command> --help`
3. ✅ Verify you're using valid state/district/CNR codes
4. ✅ Open an issue on GitHub (if repository is public)

---

## 🙏 Acknowledgments

- [eCourts India](https://services.ecourts.gov.in/) for providing the public court data API  

