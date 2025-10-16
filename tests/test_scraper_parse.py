from ecourts_scraper.scraper import ECourtsScraper
from pathlib import Path


def test_parse_sample_fixture():
    scraper = ECourtsScraper()
    fixture = Path(__file__).parent / 'fixtures' / 'sample_case.html'
    html = fixture.read_text(encoding='utf-8')
    res = scraper._parse_case_response(html)
    # ensure rows parsed and serial/court extracted
    assert 'rows' in res
    assert res['rows'][0][0] == '1'
    assert res.get('serial') == '1'
    assert res.get('court') == 'Special Court A'
