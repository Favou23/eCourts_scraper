"""Convenience script to run the Flask app without setting FLASK_APP env vars.
Run from project root:
    .\.venv\Scripts\Activate.ps1
    python run_web.py
"""
from ecourts_scraper.web import app

if __name__ == '__main__':
    app.run(debug=True)
