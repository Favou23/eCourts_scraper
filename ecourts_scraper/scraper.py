import requests
from bs4 import BeautifulSoup
import datetime
import os
import time
from typing import Optional, Dict, Any


class ECourtsScraper:
    BASE = 'https://services.ecourts.gov.in/ecourtindia_v6/'

    def __init__(self, session=None):
        self.s = session or requests.Session()
        # small default headers
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

            # For client/server errors, don't retry on 4xx except maybe 429
            if r.status_code == 429 and attempt < retries:
                # rate limited - backoff and retry
                time.sleep(backoff * (2 ** attempt))
                attempt += 1
                continue

            return {'error': f'HTTP {r.status_code}', 'status': r.status_code, 'url': url, 'text': r.text[:200]}


    def check_by_cnr(self, cnr, download_pdf=False):
        # Endpoint guess: search by CNR - this is a best-effort scraper.
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
        # If JSON, inspect keys for listings
        if isinstance(data, dict):
            # best-effort fields
            listing = data.get('listing') or data.get('data') or data
            # try to extract serial/court if present
            serial = listing.get('serial') if isinstance(listing, dict) else None
            court = listing.get('court') if isinstance(listing, dict) else None
            out = {'raw': listing}
            if serial or court:
                out.update({'serial': serial, 'court': court})
            return out

        # If HTML/text, use BeautifulSoup to find cause-list table rows and extract serial & court
        soup = BeautifulSoup(data, 'html.parser')
        rows = []
        table = soup.find('table')
        if table:
            # extract headers
            headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
            for tr in table.find_all('tr'):
                cols = [td.get_text(strip=True) for td in tr.find_all('td')]
                if cols:
                    rows.append(cols)

            parsed = {'rows': rows}
            # heuristically map header names to serial and court
            if headers:
                # normalize
                hmap = {i: h for i, h in enumerate(headers)}
                # find likely serial index
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

            # look for PDF links
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

        # Fallback: try to collect some text rows
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
        # The site uses dd-mm-YYYY format for cause list date
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
        # date param expected as dd-mm-YYYY in many eCourts forms
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
        # search rows in first table
        table = soup.find('table')
        if not table:
            # fallback: search raw text
            if query in html:
                return {'found': True, 'serial': None, 'court': None, 'pdf': None, 'file': fname}
            return {'found': False, 'file': fname}

        headers = [th.get_text(strip=True).lower() for th in table.find_all('th')]
        # find rows
        for tr in table.find_all('tr'):
            cols = [td.get_text(strip=True) for td in tr.find_all('td')]
            if not cols:
                continue
            row_text = ' '.join(cols)
            if query in row_text or query.lower() in row_text.lower():
                # try extract serial and court using headers mapping
                serial = None
                court = None
                for i, h in enumerate(headers):
                    if 'serial' in h or 's. no' in h or 's.no' in h:
                        if i < len(cols):
                            serial = cols[i]
                    if 'court' in h or 'bench' in h:
                        if i < len(cols):
                            court = cols[i]
                # Find PDF link in this row
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
        if 'error' in out:
            return out
        r = out['response']
        soup = BeautifulSoup(r.text, 'html.parser')
        selects = {}
        for sel in soup.find_all('select'):
            name = sel.get('name') or sel.get('id') or 'select'
            opts = []
            for o in sel.find_all('option'):
                val = o.get('value')
                txt = o.get_text(strip=True)
                opts.append((val, txt))
            selects[name] = opts
        return {'options': selects, 'html': r.text}

    def get_dependent_options(self, state: Optional[str]=None, district: Optional[str]=None) -> Dict[str, Any]:
        """Fetch the cause_list endpoint with optional state/district params and parse selects.

        This attempts to emulate the site's AJAX behavior by requesting the same endpoint
        the site uses to return dependent selects. It returns a mapping similar to
        get_cause_list_page: {'options': {select_name: [(value,text), ...]}, 'html': html}
        """
        url = self.BASE + 'causeList/causelists'
        params = {}
        if state:
            params['sess_state_code'] = state
        if district:
            params['sees_dist_code'] = district
        out = self._get(url, params=params)
        if 'error' in out:
            return out
        r = out['response']
        soup = BeautifulSoup(r.text, 'html.parser')
        selects = {}
        for sel in soup.find_all('select'):
            name = sel.get('name') or sel.get('id') or 'select'
            opts = []
            for o in sel.find_all('option'):
                val = o.get('value')
                txt = o.get_text(strip=True)
                opts.append((val, txt))
            selects[name] = opts
        return {'options': selects, 'html': r.text}

    def _find_captcha_url(self, html: str) -> Optional[str]:
        soup = BeautifulSoup(html, 'html.parser')
        img = soup.find('img', {'id': 'captcha_img'}) or soup.find('img', {'alt': 'captcha'})
        if img and img.get('src'):
            src = img['src']
            if src.startswith('http'):
                return src
            return requests.compat.urljoin(self.BASE, src)
        # fallback: find any image near 'captcha'
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
        # Collect hidden inputs
        hidden = {i.get('name'): i.get('value','') for i in form.find_all('input', {'type': 'hidden'}) if i.get('name')}
        return {'action': requests.compat.urljoin(self.BASE, action), 'fields': fields, 'hidden': hidden}

    def submit_cause_list_form(self, state, district, complex_value, court_name, date, captcha) -> Dict[str, Any]:
        # Fetch page and parse form
        page = self.get_cause_list_page()
        if 'error' in page:
            return page
        html = page['html']
        parsed = self.parse_cause_list_form(html)
        if 'error' in parsed:
            return parsed
        action = parsed['action']
        data = {}
        # include hidden inputs
        data.update(parsed.get('hidden', {}))
        # Map known fields if present
        # heuristics for field names
        # copy provided selections
        for k in ['state','district','complex','court','CauseListDate','cause_list_date']:
            if k in parsed['fields']:
                data[k] = ''
        # Put values
        # attempt to guess real names by scanning parsed['fields'] keys
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
        # Add captcha
        # Try common captcha field names
        for captcha_field in ['captcha','txtCaptcha','captcha_text','captchaValue']:
            if captcha_field in parsed['fields']:
                data[captcha_field] = captcha
        # As a fallback, add 'captcha' key
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
            # normalize relative
            if href.lower().endswith('.pdf'):
                if href.startswith('http'):
                    links.append(href)
                else:
                    links.append(requests.compat.urljoin(self.BASE, href))

        # If date provided, try filter anchors that contain the date string
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
