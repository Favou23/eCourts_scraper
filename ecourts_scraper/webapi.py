
from flask import Flask, jsonify, request, render_template, send_from_directory
from flask_cors import CORS
from .scraper import ECourtsScraper
import os

app = Flask(__name__, template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
CORS(app)  # enable CORS for local testing

# single scraper instance (reuses requests.Session)
scraper = ECourtsScraper()

def normalise_selects(options_map):
    """
    Convert scraper.get_dependent_options 'options' dict into a normalized structure:
    {
      "states": [(val, text), ...],
      "districts": [(val, text), ...],
      "complexes": [(val, text), ...],
      "courts": [(val, text), ...]
    }
    The scraper returns keys like 'sess_state_code', 'sees_dist_code', 'court_complex_code', 'CL_court_no' etc.
    """
    out = {"states": [], "districts": [], "complexes": [], "courts": []}
    for k, opts in (options_map or {}).items():
        lk = (k or "").lower()
        if "state" in lk:
            out["states"] = [(str(v), str(t)) for v, t in opts]
        elif "dist" in lk:
            out["districts"] = [(str(v), str(t)) for v, t in opts]
        elif "complex" in lk:
            out["complexes"] = [(str(v), str(t)) for v, t in opts]
        elif "court" in lk or "cl_court" in lk or "cl_court_no" in lk:
            out["courts"] = [(str(v), str(t)) for v, t in opts]
        else:
            # fallback: try to classify by option text
            if any("court" in (t or "").lower() for _, t in opts):
                out["courts"] = [(str(v), str(t)) for v, t in opts]
    return out

@app.route("/")
def index():
    # serve the UI (template in package templates/)
    return render_template("index.html")

@app.route("/api/states", methods=["GET"])
def api_states():
    # get initial page and parse selects
    page = scraper.get_cause_list_page()
    opts = page.get("options", {})
    normalized = normalise_selects(opts)
    # return states (if none found, send html for debugging)
    if not normalized["states"]:
        return jsonify({"states": [], "debug_html": page.get("html","")})
    return jsonify({"states": [{"value": v, "text": t} for v, t in normalized["states"]]})

@app.route("/api/districts", methods=["GET"])
def api_districts():
    state = request.args.get("state")
    state_text = None

    # Try to find the state name from cached list
    page = scraper.get_cause_list_page()
    opts = page.get("options", {})
    states = opts.get("sess_state_code") or []
    for value, text in states:
        if str(value) == str(state):
            state_text = text
            break

    res = scraper.get_dependent_options(state=state, state_text=state_text)
    opts = res.get("options", {})
    normalized = normalise_selects(opts)
    return jsonify({
        "state": state,
        "districts": [{"value": v, "text": t} for v, t in normalized["districts"]],
        "debug_html": res.get("html","")
    })


@app.route("/api/complexes", methods=["GET"])
def api_complexes():
    state = request.args.get("state")
    district = request.args.get("district")
    if not state or not district:
        return jsonify({"error": "state and district params required"}), 400
    res = scraper.get_dependent_options(state=state, district=district)
    opts = res.get("options", {})
    normalized = normalise_selects(opts)
    return jsonify({
        "state": state,
        "district": district,
        "complexes": [{"value": v, "text": t} for v, t in normalized["complexes"]],
        "debug_html": res.get("html","")
    })

@app.route("/api/courts", methods=["GET"])
def api_courts():
    state = request.args.get("state")
    district = request.args.get("district")
    complex_val = request.args.get("complex")
    if not state or not district or not complex_val:
        return jsonify({"error": "state, district and complex params required"}), 400
    # get dependent options; scraper may populate CL_court_no or court_est_code, etc.
    res = scraper.get_dependent_options(state=state, district=district)
    opts = res.get("options", {})
    normalized = normalise_selects(opts)

    # If complexes exist, we may need to POST/select complex to get courts.
    # The scraper's headless fallback can auto-select a complex, but we will attempt to
    # emulate what the site does by returning courts found in the options map.
    # If the normalized courts list is empty, return debug_html for troubleshooting.
    return jsonify({
        "state": state,
        "district": district,
        "complex": complex_val,
        "courts": [{"value": v, "text": t} for v, t in normalized["courts"]],
        "debug_html": res.get("html","")
    })

# Serve static files (if any) and templates folder is inside package.
@app.route("/static/<path:filename>")
def static_files(filename):
    return send_from_directory(app.static_folder, filename)

for rule in app.url_map.iter_rules():
    print("Registered route:", rule)


if __name__ == "__main__":
    # Run for development
    app.run(host="0.0.0.0", port=5000, debug=True)
