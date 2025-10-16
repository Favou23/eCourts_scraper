from ecourts_scraper.scraper import ECourtsScraper
from pathlib import Path
import datetime


def test_search_fixture(tmp_path):
    # copy sample_case.html to a filename that download_cause_list would produce
    fixture = Path(__file__).parent / 'fixtures' / 'sample_case.html'
    dest = tmp_path / 'causelist_2025-10-16.html'
    dest.write_text(fixture.read_text(encoding='utf-8'), encoding='utf-8')

    scraper = ECourtsScraper()
    # monkeypatch download_cause_list by replacing the method on instance
    def fake_download(date):
        return str(dest)

    scraper.download_cause_list = fake_download
    res = scraper.search_case_in_cause_list(datetime.date(2025,10,16), 'Cr. 123/2024')
    assert res['found']
    assert res['serial'] == '1'
    assert 'Special Court A' in res['court']
