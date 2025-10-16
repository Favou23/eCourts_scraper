from flask import Flask, render_template, request, send_file, redirect, url_for, session, jsonify
import traceback
from .scraper import ECourtsScraper
import tempfile
import os
import zipfile
from io import BytesIO

# Ensure Flask finds the templates folder located at project_root/templates
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
TEMPLATE_DIR = os.path.join(PROJECT_ROOT, 'templates')
STATIC_DIR = os.path.join(PROJECT_ROOT, 'static')
app = Flask(__name__, template_folder=TEMPLATE_DIR, static_folder=STATIC_DIR)
app.secret_key = os.environ.get('FLASK_SECRET', 'dev-secret')


@app.route('/')
def index():
    try:
        scraper = ECourtsScraper()
        res = scraper.get_cause_list_page()
        options = res.get('options', {}) if isinstance(res, dict) else {}
        return render_template('index.html', options=options)
    except Exception:
        tb = traceback.format_exc()
        # Return traceback for easier debugging in development
        return f"Internal server error:\n<pre>{tb}</pre>", 500


@app.route('/captcha')
def captcha():
    # Returns captcha image: we fetch fresh cause_list page and return captcha
    try:
        scraper = ECourtsScraper()
        page = scraper.get_cause_list_page()
        # scraper.get_cause_list_page returns html and options; find captcha via parser
        html = page.get('html')
        cap_url = scraper._find_captcha_url(html)
        if not cap_url:
            return 'No captcha found', 404
        out = scraper._get(cap_url)
        if 'error' in out:
            return f"Error fetching captcha: {out}", 500
        r = out['response']
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.png')
        tmp.write(r.content)
        tmp.flush()
        tmp.close()
        session['captcha_file'] = tmp.name
        return send_file(tmp.name, mimetype='image/png')
    except Exception:
        tb = traceback.format_exc()
        return f"Internal server error:\n<pre>{tb}</pre>", 500


@app.route('/submit', methods=['POST'])
def submit():
    # Accept form fields including captcha text and selected options
    try:
        state = request.form.get('state')
        district = request.form.get('district')
        complex_val = request.form.get('complex')
        court_name = request.form.get('court')
        date = request.form.get('date')
        captcha_text = request.form.get('captcha')

        scraper = ECourtsScraper()
        # parse form and perform POST to retrieve cause list
        res = scraper.submit_cause_list_form(state=state, district=district, complex_value=complex_val, court_name=court_name, date=date, captcha=captcha_text)
        if 'error' in res:
            return render_template('results.html', error=res)

        # If user requested download, fetch PDFs and return a ZIP
        do_download = request.form.get('download') == '1'
        if do_download:
            links = res.get('links', [])
            if not links:
                return render_template('results.html', error={'error': 'no pdf links found'})
            # download each URL into an in-memory ZIP
            mem = BytesIO()
            with zipfile.ZipFile(mem, 'w', zipfile.ZIP_DEFLATED) as zf:
                for idx, url in enumerate(links):
                    try:
                        r = scraper.s.get(url, stream=True, timeout=20)
                    except Exception as e:
                        continue
                    if r.status_code == 200:
                        name = os.path.basename(url.split('?')[0]) or f'doc_{idx}.pdf'
                        zf.writestr(name, r.content)
            mem.seek(0)
            return send_file(mem, mimetype='application/zip', as_attachment=True, download_name=f'causelist_{date or "download"}.zip')

        # res expected to include 'html' and 'links'
        return render_template('results.html', result=res)
    except Exception:
        tb = traceback.format_exc()
        return f"Internal server error:\n<pre>{tb}</pre>", 500



# AJAX endpoint: get districts for a state
@app.route('/api/districts')
def api_districts():
    state = request.args.get('state')
    if not state:
        return jsonify({'error': 'Missing state'}), 400
    scraper = ECourtsScraper()
    res = scraper.get_dependent_options(state=state)
    options = res.get('options', {}) if isinstance(res, dict) else {}
    districts = options.get('sees_dist_code', []) or options.get('sees_dist_code', [])
    # Filter out placeholder (value '0')
    districts = [ {'value': v, 'text': t} for v, t in districts if v != '0' ]
    return jsonify({'districts': districts})

# AJAX endpoint: get complexes for a state+district
@app.route('/api/complexes')
def api_complexes():
    state = request.args.get('state')
    district = request.args.get('district')
    if not state or not district:
        return jsonify({'error': 'Missing state or district'}), 400
    scraper = ECourtsScraper()
    res = scraper.get_dependent_options(state=state, district=district)
    options = res.get('options', {}) if isinstance(res, dict) else {}
    complexes = options.get('court_complex_code', [])
    # Filter out placeholder (value '0')
    complexes = [ {'value': v, 'text': t} for v, t in complexes if v != '0' ]
    return jsonify({'complexes': complexes})

if __name__ == '__main__':
    app.run(debug=True)
