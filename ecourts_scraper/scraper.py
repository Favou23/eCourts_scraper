
import requests
from bs4 import BeautifulSoup
import datetime
import os
import time
from typing import Optional, Dict, Any
import atexit

# Playwright globals for reuse to avoid relaunching the browser on every call                             
_pw_runtime = None
_pw_browser = None

def _start_playwright_browser():
    """Start Playwright runtime and a single browser instance for reuse.

    Returns tuple (playwright_runtime, browser) or (None, None) if Playwright isn't available.
    """
    global _pw_runtime, _pw_browser
    if _pw_browser is not None and _pw_runtime is not None:
        return _pw_runtime, _pw_browser
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return None, None
    try:
        _pw_runtime = sync_playwright().start()
        _pw_browser = _pw_runtime.chromium.launch(headless=True)
        # ensure we stop playwright on exit
        def _stop():
            try:
                if _pw_browser:
                    _pw_browser.close()
            except Exception:
                pass
            try:
                if _pw_runtime:
                    _pw_runtime.stop()
            except Exception:
                pass
        atexit.register(_stop)
        return _pw_runtime, _pw_browser
    except Exception:
        return None, None


class ECourtsScraper:
    BASE = 'https://services.ecourts.gov.in/ecourtindia_v6/'
    
    _dependent_options_cache = {}
    _cache_ttl = 300  # seconds

    def __init__(self, session=None):
        self.s = session or requests.Session()
     
        self.s.headers.update({
            'User-Agent': 'ecourts-scraper/0.1 (+https://example.local)'
        })

    def _get(self, url, params=None, timeout=15, retries=3, backoff=1.0) -> Dict[str, Any]:
        """GET with retries. Returns dict with either 'response' or 'error'.

        Error structure: {'error': 'HTTP 400', 'status': 400, 'url': url}
        """
        attempt = 0
        while attempt <= retries:
            try:
                r = self.s.get(url, params=params, timeout=timeout)
            except requests.RequestException as exc:
                if attempt == retries:
                    return {'error': str(exc)}
                attempt += 1
                time.sleep(backoff * (2 ** (attempt-1)))
                continue

            if 200 <= r.status_code < 300:
                return {'response': r}

            if r.status_code == 429 and attempt < retries:
                time.sleep(backoff * (2 ** attempt))
                attempt += 1
                continue

            return {'error': f'HTTP {r.status_code}', 'status': r.status_code, 'url': url, 'text': r.text[:200]}


    def check_by_cnr(self, cnr, download_pdf=False):
        url = self.BASE + 'case/cnrSearch'
        params = {'cnr': cnr}
        out = self._get(url, params=params)
        if 'error' in out:
            return out
        r = out['response']
        data = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
        return self._parse_case_response(data, download_pdf)

    def check_by_details(self, case_type, number, year, download_pdf=False):
        url = self.BASE + 'case/search'
        params = {'casetype': case_type, 'cno': number, 'cyear': year}
        out = self._get(url, params=params)
        if 'error' in out:
            return out
        r = out['response']
        data = r.json() if r.headers.get('content-type','').startswith('application/json') else r.text
        return self._parse_case_response(data, download_pdf)

    def _parse_case_response(self, data, download_pdf=False):
        if isinstance(data, dict):
            listing = data.get('listing') or data.get('data') or data
            serial = listing.get('serial') if isinstance(listing, dict) else None
            court = listing.get('court') if isinstance(listing, dict) else None
            out = {'raw': listing}
            if serial or court:
                out.update({'serial': serial, 'court': court})
            return out

        soup = BeautifulSoup(data, 'html.parser')
        rows = []
        table = soup.find('table')
        if table:
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            for tr in table.find_all('tr'):
                cols = [td.get_text(strip=True) for td in tr.find_all('td')]
                if cols:
                    rows.append(cols)

            parsed = {'rows': rows}
            if headers:
                hmap = {i: h for i, h in enumerate(headers)}
                serial_idx = None
                court_idx = None
                for i, h in hmap.items():
                    if 'serial' in h or 's. no' in h or 's.no' in h or 's no' in h:
                        serial_idx = i
                    if 'court' in h or 'bench' in h:
                        court_idx = i

                if rows:
                    first = rows[0]
                    if serial_idx is not None and serial_idx < len(first):
                        parsed['serial'] = first[serial_idx]
                    if court_idx is not None and court_idx < len(first):
                        parsed['court'] = first[court_idx]

            pdf_link = None
            a = table.find('a', href=True, string=lambda s: s and 'PDF' in s.upper()) if table else None
            if not a:
                a = soup.find('a', href=True, string=lambda s: s and 'PDF' in s.upper())
            if a:
                pdf_link = a['href']
            if pdf_link and download_pdf:
                fname = self._download_file(pdf_link)
                parsed['pdf'] = fname
            return parsed

        text_rows = [p.get_text(strip=True) for p in soup.find_all('p') if p.get_text(strip=True)]
        return {'text_rows': text_rows[:20]}

    def _download_file(self, url, dest_dir='downloads'):
        os.makedirs(dest_dir, exist_ok=True)
        local = os.path.join(dest_dir, os.path.basename(url.split('?')[0]))
        r = self.s.get(url, stream=True, timeout=30)
        if r.status_code == 200:
            with open(local, 'wb') as f:
                for chunk in r.iter_content(1024*8):
                    f.write(chunk)
            return local
        return None

    def download_cause_list(self, date: datetime.date, state: Optional[str]=None, district: Optional[str]=None,
                            complex_code: Optional[str]=None, est_code: Optional[str]=None, court_no: Optional[str]=None):
        """Download the cause list HTML for a given date and optional selectors.

        The eCourts endpoint expects parameters for state/district/complex and date in dd-mm-YYYY.
        Returns filename or error dict.
        """
        url = self.BASE + 'causeList/causelists'
        params = {}
        if state is not None:
            params['sess_state_code'] = state
        if district is not None:
            params['sees_dist_code'] = district
        if complex_code is not None:
            params['court_complex_code'] = complex_code
        if est_code is not None:
            params['court_est_code'] = est_code
        if court_no is not None:
            params['CL_court_no'] = court_no
        params['CauseListDate'] = date.strftime('%d-%m-%Y')

        out = self._get(url, params=params)
        if 'error' in out:
            return out
        r = out['response']
        fname = f'causelist_{date.isoformat()}.html'
        with open(fname, 'wb') as f:
            f.write(r.content)
        return fname

    def search_case_in_cause_list(self, date: datetime.date, query: str) -> Dict[str, Any]:
        """Download or load cause list HTML for date and search for query string.

        Query can be a CNR or case number string. Returns dict:
        {'found': bool, 'serial': str|None, 'court': str|None, 'pdf': url|None, 'file': filename}
        """
        fname_or_err = self.download_cause_list(date)
        if isinstance(fname_or_err, dict) and 'error' in fname_or_err:
            return {'error': fname_or_err}
        fname = fname_or_err
        if not os.path.exists(fname):
            return {'error': f'file not found {fname}'}
        html = open(fname, 'r', encoding='utf-8').read()
        soup = BeautifulSoup(html, 'html.parser')
        table = soup.find('table')
        if not table:
            if query in html:
                return {'found': True, 'serial': None, 'court': None, 'pdf': None, 'file': fname}
            return {'found': False, 'file': fname}

        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        for tr in table.find_all('tr'):
            cols = [td.get_text(strip=True) for td in tr.find_all('td')]
            if not cols:
                continue
            row_text = ' '.join(cols)
            if query in row_text or query.lower() in row_text.lower():
                serial = None
                court = None
                for i, h in enumerate(headers):
                    if 'serial' in h or 's. no' in h or 's.no' in h:
                        if i < len(cols):
                            serial = cols[i]
                    if 'court' in h or 'bench' in h:
                        if i < len(cols):
                            court = cols[i]
                a = tr.find('a', href=True)
                pdf = None
                if a and a['href'].lower().endswith('.pdf'):
                    href = a['href']
                    pdf = href if href.startswith('http') else requests.compat.urljoin(self.BASE, href)
                return {'found': True, 'serial': serial, 'court': court, 'pdf': pdf, 'file': fname}

        return {'found': False, 'file': fname}

    def get_cause_list_page(self) -> Dict[str, Any]:
        """Fetch the cause_list landing page and parse available selects/options.

        Returns a dict with 'options' mapping select names to list of (value, text).
        """
        url = self.BASE
        params = {'p': 'cause_list/'}
        out = self._get(url, params=params)
        r = out.get('response') if isinstance(out, dict) else None
        selects = {}
        if r:
            soup = BeautifulSoup(r.text, 'html.parser')
            for sel in soup.find_all('select'):
                name = sel.get('name') or sel.get('id') or 'select'
                opts = []
                for o in sel.find_all('option'):
                    val = o.get('value')
                    txt = o.get_text(strip=True)
                    opts.append((val, txt))
                selects[name] = opts
        html = r.text if r else ''
        return {'options': selects, 'html': html}

    def get_dependent_options(self, state=None, state_text=None, district=None, complex=None, court=None, date=None):

        """Fetch dependent select options from the cause_list endpoint.

        Tries multiple variants (with/without date) to emulate the site's AJAX responses.
        Returns {'options': {select_name: [(value,text), ...]}, 'html': html}
        """
        key = f"{state or ''}|{district or ''}|{date.isoformat() if date else ''}"
        now = time.time()
        cached = self._dependent_options_cache.get(key)
        if cached:
            exp, data = cached
            if exp > now:
                return {'options': data, 'html': ''}
            else:
                try:
                    del self._dependent_options_cache[key]
                except Exception:
                    pass

        url = self.BASE + 'causeList/causelists'
        params = {}
        if state:
            params['sess_state_code'] = state
        if district:
            # some pages use sess_dist_code (observed in site JS) while older code used sees_dist_code
            params['sees_dist_code'] = district
            params['sess_dist_code'] = district
        if date:
            params['CauseListDate'] = date.strftime('%d-%m-%Y')

        out = self._get(url, params=params)
        r = out.get('response') if isinstance(out, dict) else None
        selects = {}
        if r:
            soup = BeautifulSoup(r.text, 'html.parser')
            for sel in soup.find_all('select'):
                name = sel.get('name') or sel.get('id') or 'select'
                opts = []
                for o in sel.find_all('option'):
                    val = o.get('value')
                    txt = o.get_text(strip=True)
                    opts.append((val, txt))
                selects[name] = opts

        def _has_meaningful_options(selects_map):
            for opts in selects_map.values():
                meaningful_count = 0
                for val, txt in opts:
                    if not val:
                        continue
                    sval = str(val).strip()
                    if sval == '' or sval == '0':
                        continue
                    if txt and 'select' in (txt or '').lower():
                        continue
                    meaningful_count += 1
                if meaningful_count > 0:
                    return True
            return False

        meaningful = _has_meaningful_options(selects)
        if not meaningful and state:
            params2 = params.copy()
            params2['CauseListDate'] = datetime.date.today().strftime('%d-%m-%Y')
            out2 = self._get(url, params=params2)
            if 'response' in out2:
                r2 = out2['response']
                soup2 = BeautifulSoup(r2.text, 'html.parser')
                selects2 = {}
                for sel in soup2.find_all('select'):
                    name = sel.get('name') or sel.get('id') or 'select'
                    opts = []
                    for o in sel.find_all('option'):
                        val = o.get('value')
                        txt = o.get_text(strip=True)
                        opts.append((val, txt))
                    selects2[name] = opts
                for k, v in selects2.items():
                    if v:
                        selects[k] = v

            landing_url = self.BASE
            landing_params = {'p': 'cause_list/'}
            if state:
                landing_params['sess_state_code'] = state
            if district:
                landing_params['sees_dist_code'] = district
            if date:
                landing_params['CauseListDate'] = date.strftime('%d-%m-%Y')
            out3 = self._get(landing_url, params=landing_params)
            if 'response' in out3:
                r3 = out3['response']
                soup3 = BeautifulSoup(r3.text, 'html.parser')
                selects3 = {}
                for sel in soup3.find_all('select'):
                    name = sel.get('name') or sel.get('id') or 'select'
                    opts = []
                    for o in sel.find_all('option'):
                        val = o.get('value')
                        txt = o.get_text(strip=True)
                        opts.append((val, txt))
                    selects3[name] = opts
                for k, v in selects3.items():
                    if v:
                        selects[k] = v

        if not meaningful:
            ajax_res = self._try_ajax_endpoints_for_options(state=state, district=district, date=date)
            if ajax_res:
                for k, v in ajax_res.items():
                    if v:
                        selects[k] = v

        if not meaningful and os.environ.get('USE_HEADLESS') == '1':
            try:
                head_res = self._get_dependent_options_headless(state=state, district=district, date=date)
                if head_res:
                    for k, v in head_res.items():
                        if v:
                            selects[k] = v
            except Exception:
                pass

        try:
            self._dependent_options_cache[key] = (time.time() + self._cache_ttl, selects)
        except Exception:
            pass

        html = r.text if r else ''
        return {'options': selects, 'html': html}

    def _try_ajax_endpoints_for_options(self, state: Optional[str] = None, district: Optional[str] = None, date: Optional[datetime.date] = None):
        """Try AJAX endpoints for dependent dropdowns (districts, complexes, courts)."""
        results = {}

        # District fetch in its own try/except
        try:
            # 1️⃣ DISTRICT FETCH (only if no district is provided yet)
            if state and not district:
                url = "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus/fillDistrict"
                payload = {"state_code": state}
                print("DEBUG fetching districts →", url, payload)
                out = self._post(url, data=payload)
                r = out.get("response")
                if r and r.status_code == 200:
                    body = r.text.strip()
                    if not body:
                        return results

                    # Handle JSON or HTML
                    if body.startswith("{") or body.startswith("["):
                        try:
                            j = r.json()
                            if isinstance(j, list):
                                results["districts"] = [
                                    (str(it.get("id") or it.get("value") or it.get("code") or ""),
                                     str(it.get("name") or it.get("text") or ""))
                                    for it in j
                                ]
                                if results["districts"]:
                                    print(f"✅ Districts extracted: {len(results['districts'])}")
                                    return results
                        except Exception as e:
                            print("DEBUG district JSON parse error:", e)

                    # HTML parsing fallback
                    clean_html = (
                        body.replace("\\/", "/").replace('\\"', '"')
                        .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                    )
                    soup = BeautifulSoup(clean_html, "html.parser")
                    opts = [
                        (o.get("value"), o.get_text(strip=True))
                        for o in soup.find_all("option")
                        if o.get("value") and "select" not in o.get_text(strip=True).lower()
                    ]
                    if opts:
                        print(f"✅ Districts parsed from HTML: {len(opts)}")
                        results["districts"] = opts
                        return results
        except Exception as e:
            print("DEBUG district ajax error:", e)

        # Complex fetch in its own try/except
        try:
            # 2️⃣ COMPLEX FETCH (only if district is provided)
            if state and district:
                complex_endpoints = [
                    "https://services.ecourts.gov.in/ecourtindia_v6/?p=casestatus/fillcomplex",
                    "https://services.ecourts.gov.in/ecourtindia_v6/?p=cause_list/fillcomplex",
                ]
                param_sets = [
                    {"state_code": state, "dist_code": district},
                    {"sess_state_code": state, "sees_dist_code": district},
                    {"sess_state_code": state, "sess_dist_code": district},
                ]

                for url in complex_endpoints:
                    for payload in param_sets:
                        try:
                            print(f"DEBUG fetching complexes → {url} {payload}")
                            out = self._post(url, data=payload)
                            r = out.get("response")
                            if not r or r.status_code != 200:
                                continue
                            body = r.text.strip()
                            if not body:
                                continue

                            # Handle JSON-embedded HTML response
                            if body.startswith("{"):
                                try:
                                    j = r.json()
                                    if isinstance(j, dict) and "complex_list" in j:
                                        html_str = j["complex_list"]
                                        clean_html = (
                                            html_str.replace("\\/", "/").replace('\\"', '"')
                                            .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                                        )
                                        soup = BeautifulSoup(clean_html, "html.parser")
                                        opts = [
                                            (o.get("value"), o.get_text(strip=True))
                                            for o in soup.find_all("option")
                                            if o.get("value") and "select" not in o.get_text(strip=True).lower()
                                        ]
                                        if opts:
                                            print(f"✅ Complexes parsed from JSON field: {len(opts)}")
                                            results["complexes"] = opts
                                            return results
                                except Exception as e:
                                    print("DEBUG complex JSON parse error:", e)

                            # Fallback: parse direct HTML
                            clean_html = (
                                body.replace("\\/", "/").replace('\\"', '"')
                                .replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")
                            )
                            soup = BeautifulSoup(clean_html, "html.parser")
                            opts = [
                                (o.get("value"), o.get_text(strip=True))
                                for o in soup.find_all("option")
                                if o.get("value") and "select" not in o.get_text(strip=True).lower()
                            ]
                            if opts:
                                print(f" Complexes parsed from HTML: {len(opts)}")
                                results["complexes"] = opts
                                return results

                        except Exception as e:
                            print("DEBUG complex request error:", e)
        except Exception as e:
            print("DEBUG complex ajax error:", e)

        return results


    def _get_dependent_options_headless(self, state: Optional[str]=None, district: Optional[str]=None, date: Optional[datetime.date]=None):
        """Use a headless browser (Playwright) to load the cause_list page and let client JS populate selects.

        This is an optional heavy fallback. Requires `playwright` to be installed and browsers installed
        (run `python -m playwright install chromium` after installing the package).
        Returns a mapping of select name -> [(value,text), ...] or empty dict on failure.
        """
        if os.environ.get('USE_HEADLESS', '') != '1':
            try:
                import importlib
                if not importlib.util.find_spec('playwright'):
                    return {}
            except Exception:
                return {}

        # clean execution of page interactions
        page = None
        tmp_browser = None
        tmp_playwright = None
        used_temp = False
        try:
            # try shared browser first
            runtime, browser = _start_playwright_browser()
            print('DEBUG: _start_playwright_browser returned', bool(runtime), bool(browser))
            if browser:
                try:
                    page = browser.new_page()
                    print('DEBUG: opened page on shared browser')
                    page.goto(self.BASE + '?p=cause_list/', timeout=20000)
                    print('DEBUG: page.goto done (shared)')
                except Exception as e:
                    print('DEBUG: shared browser page/goto error', e)
                    page = None

            # fallback to temporary playwright instance if needed
            if page is None:
                try:
                    print('DEBUG: attempting to start temporary playwright')
                    from playwright.sync_api import sync_playwright
                    tmp_playwright = sync_playwright().start()
                    tmp_browser = tmp_playwright.chromium.launch(headless=True)
                    page = tmp_browser.new_page()
                    page.goto(self.BASE + '?p=cause_list/', timeout=20000)
                    used_temp = True
                    print('DEBUG: temporary playwright started and page loaded')
                except Exception as exc:
                    print('DEBUG: temporary playwright error', exc)
                    # nothing to do, will be handled below
                    pass

            if page is None:
                return {}

            def _collect_from_page(page_obj):
                selects_map = {}
                try:
                    for sel in page_obj.query_selector_all('select'):
                        name = sel.get_attribute('name') or sel.get_attribute('id') or 'select'
                        opts = []
                        for o in sel.query_selector_all('option'):
                            try:
                                val = o.get_attribute('value')
                            except Exception:
                                val = None
                            try:
                                txt = o.inner_text().strip()
                            except Exception:
                                txt = ''
                            opts.append((val, txt))
                        selects_map[name] = opts
                except Exception:
                    pass
                return selects_map

            def _collect_selects_from_page():
                return _collect_from_page(page)

            # if state provided, attempt to select it
            if state:
                selectors = ['select[name="sess_state_code"]', 'select[name="state"]', 'select[id="sess_state_code"]']
                for sel in selectors:
                    try:
                        page.select_option(sel, state)
                    except Exception:
                        pass

            # wait briefly for district options
            for sel in ['select[name="sees_dist_code"]', 'select[name="sess_dist_code"]', 'select[name="district"]', 'select[id="sees_dist_code"]', 'select[id="sess_dist_code"]']:
                try:
                    page.wait_for_selector(f"{sel} option:not([value='']), {sel} option[value]:not([value='0'])", timeout=1500)
                    break
                except Exception:
                    continue

            if district:
                district_selectors = ['select[name="sees_dist_code"]', 'select[name="sess_dist_code"]', 'select[name="district"]', 'select[id="sees_dist_code"]', 'select[id="sess_dist_code"]']
                for sel in district_selectors:
                    try:
                        page.select_option(sel, district)
                    except Exception:
                        try:
                            opt = page.query_selector(f"{sel} >> option:has-text('{district}')")
                            if opt:
                                opt.click()
                            else:
                                script = f"(function(){{var s=document.querySelector('{sel}'); if(s){{s.value='{district}'; s.dispatchEvent(new Event('change'));}}}})();"
                                try:
                                    page.evaluate(script)
                                except Exception:
                                    pass
                        except Exception:
                            pass

            # wait for complex or court options to populate
            try:
                page.wait_for_selector('select[name="court_complex_code"] option:not([value=""])', timeout=2000)
            except Exception:
                try:
                    page.wait_for_selector('select[name="CL_court_no"] option:not([value=""])', timeout=2000)
                except Exception:
                    page.wait_for_timeout(500)

            selects = _collect_selects_from_page()
            print('DEBUG: collected selects (count)', len(selects))

            # if courts aren't present, try auto-selecting a complex
            courts_present = False
            for k, opts in selects.items():
                lk = (k or '').lower()
                if 'court' in lk and len([o for o in opts if o and o[0] and o[0] != '0']) > 1:
                    courts_present = True
                    break
            complex_val = None
            for k, opts in selects.items():
                lk = (k or '').lower()
                if 'complex' in lk or 'court_complex' in lk:
                    for val, txt in opts:
                        if val and val != '0' and txt and 'select' not in txt.lower():
                            complex_val = val
                            break
                if complex_val:
                    break

            if not courts_present and complex_val:
                complex_selectors = ['select[name="court_complex_code"]', 'select[name="complex"]', 'select[id="court_complex_code"]']
                for sel in complex_selectors:
                    try:
                        page.select_option(sel, complex_val)
                    except Exception:
                        try:
                            opt = page.query_selector(f"{sel} >> option[value=\"{complex_val}\"]")
                            if opt:
                                opt.click()
                            else:
                                script = f"(function(){{var s=document.querySelector('{sel}'); if(s){{s.value='{complex_val}'; s.dispatchEvent(new Event('change'));}}}})();"
                                try:
                                    page.evaluate(script)
                                except Exception:
                                    pass
                        except Exception:
                            pass
                try:
                    page.wait_for_selector('select[name="CL_court_no"] option:not([value=""])', timeout=2000)
                except Exception:
                    page.wait_for_timeout(500)

            # final collection
            selects = _collect_selects_from_page()

            # cleanup
            try:
                if page and not used_temp:
                    try:
                        page.close()
                    except Exception:
                        pass
                if used_temp:
                    try:
                        tmp_browser.close()
                    except Exception:
                        pass
                    try:
                        tmp_playwright.stop()
                    except Exception:
                        pass
            except Exception:
                pass

            print('DEBUG: returning selects')
            return selects
        except Exception:
            # ensure temp resources are cleaned
            try:
                if tmp_browser:
                    tmp_browser.close()
            except Exception:
                pass
            try:
                if tmp_playwright:
                    tmp_playwright.stop()
            except Exception:
                pass
            return {}

    def _get_dependent_options_headless_temp(self, state: Optional[str]=None, district: Optional[str]=None, date: Optional[datetime.date]=None):
        """Launch a temporary Playwright instance (separate process) to collect selects.

        This is a heavier fallback used when the shared Playwright/browser path fails or
        returns empty. It isolates the Playwright runtime and avoids conflicts with any
        running event loops.
        """
        try:
            from playwright.sync_api import sync_playwright
        except Exception:
            return {}

        try:
            p = sync_playwright().start()
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(self.BASE + '?p=cause_list/', timeout=30000)

            # select state if provided
            if state:
                for sel in ['select[name="sess_state_code"]', 'select[name="state"]', 'select[id="sess_state_code"]']:
                    try:
                        page.select_option(sel, state)
                    except Exception:
                        pass

            # wait briefly for district options
            try:
                page.wait_for_selector('select[name="sees_dist_code"] option:not([value=""]), select[name="district"] option:not([value=""])', timeout=2000)
            except Exception:
                pass

            selects = {}
            for sel in page.query_selector_all('select'):
                name = sel.get_attribute('name') or sel.get_attribute('id') or 'select'
                opts = []
                for o in sel.query_selector_all('option'):
                    val = o.get_attribute('value')
                    txt = o.inner_text().strip()
                    opts.append((val, txt))
                selects[name] = opts

            try:
                page.close()
            except Exception:
                pass
            try:
                browser.close()
            except Exception:
                pass
            try:
                p.stop()
            except Exception:
                pass
            return selects
        except Exception:
            try:
                p.stop()
            except Exception:
                pass
            return {}

    def _find_captcha_url(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        img = soup.find('img', {'id': 'captcha_img'}) or soup.find('img', {'alt': 'captcha'})
        if img and img.get('src'):
            src = img['src']
            if src.startswith('http'):
                return src
            return requests.compat.urljoin(self.BASE, src)
        for img in soup.find_all('img', src=True):
            if 'captcha' in img.get('src','').lower() or 'captcha' in img.get('alt','').lower():
                src = img['src']
                return requests.compat.urljoin(self.BASE, src)
        return None

    def _post(self, url, data=None, timeout=15, retries=2, backoff=1.0):
        attempt = 0
        while attempt <= retries:
            try:
                r = self.s.post(url, data=data, timeout=timeout)
            except requests.RequestException as exc:
                if attempt == retries:
                    return {'error': str(exc)}
                attempt += 1
                time.sleep(backoff * (2 ** (attempt-1)))
                continue
            if 200 <= r.status_code < 300:
                return {'response': r}
            return {'error': f'HTTP {r.status_code}', 'status': r.status_code, 'text': r.text[:200]}

    def parse_cause_list_form(self, html: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html, 'html.parser')
        form = soup.find('form')
        if not form:
            return {'error': 'no form found'}
        action = form.get('action') or self.BASE
        fields = {}
        for inp in form.find_all(['input','select','textarea']):
            name = inp.get('name')
            if not name:
                continue
            if inp.name == 'select':
                fields[name] = [ (o.get('value'), o.get_text(strip=True)) for o in inp.find_all('option') ]
            else:
                fields[name] = inp.get('value','')
        hidden = {i.get('name'): i.get('value','') for i in form.find_all('input', {'type': 'hidden'}) if i.get('name')}
        return {'action': requests.compat.urljoin(self.BASE, action), 'fields': fields, 'hidden': hidden}

    def submit_cause_list_form(self, state, district, complex_value, court_name, date, captcha) -> Dict[str, Any]:
        page = self.get_cause_list_page()
        if 'error' in page:
            return page
        html = page['html']
        parsed = self.parse_cause_list_form(html)
        if 'error' in parsed:
            return parsed
        action = parsed['action']
        data = {}
        data.update(parsed.get('hidden', {}))
        for k in ['state','district','complex','court','CauseListDate','cause_list_date']:
            if k in parsed['fields']:
                data[k] = ''
        for fname in parsed['fields'].keys():
            ln = fname.lower()
            if 'state' in ln:
                data[fname] = state
            elif 'district' in ln:
                data[fname] = district
            elif 'complex' in ln or 'court_complex' in ln:
                data[fname] = complex_value
            elif 'courtname' in ln or 'court' == ln or 'court_name' in ln:
                data[fname] = court_name
            elif 'date' in ln:
                data[fname] = date
        for captcha_field in ['captcha','txtCaptcha','captcha_text','captchaValue']:
            if captcha_field in parsed['fields']:
                data[captcha_field] = captcha
        if 'captcha' not in data:
            data['captcha'] = captcha

        out = self._post(action, data=data)
        if 'error' in out:
            return out
        r = out['response']
        html2 = r.text
        links = self.find_cause_list_links(html2)
        return {'html': html2, 'links': links.get('links', [])}

    def find_cause_list_links(self, html: str, complex_value: Optional[str]=None, date: Optional[datetime.date]=None) -> Dict[str, Any]:
        """From a cause_list HTML (string), find likely PDF links for the given complex/date.

        Returns {'links': [url, ...]} or {'error': ...}
        """
        soup = BeautifulSoup(html, 'html.parser')
        anchors = soup.find_all('a', href=True)
        links = []
        for a in anchors:
            href = a['href']
            if href.lower().endswith('.pdf'):
                if href.startswith('http'):
                    links.append(href)
                else:
                    links.append(requests.compat.urljoin(self.BASE, href))

        if date and not links:
            date_str = date.strftime('%d-%m-%Y')
            for a in anchors:
                href = a['href']
                if date_str in href or date_str in a.get_text(' '):
                    if href.startswith('http'):
                        links.append(href)
                    else:
                        links.append(requests.compat.urljoin(self.BASE, href))

        return {'links': links}

    def download_urls(self, urls, dest_dir='downloads'):
        os.makedirs(dest_dir, exist_ok=True)
        saved = []
        for url in urls:
            try:
                r = self.s.get(url, stream=True, timeout=30)
            except requests.RequestException as e:
                saved.append({'url': url, 'error': str(e)})
                continue
            if r.status_code == 200:
                fname = os.path.join(dest_dir, os.path.basename(url.split('?')[0]))
                with open(fname, 'wb') as f:
                    for chunk in r.iter_content(1024*8):
                        f.write(chunk)
                saved.append({'url': url, 'path': fname})
            else:
                saved.append({'url': url, 'error': f'HTTP {r.status_code}'})
        return {'saved': saved}
