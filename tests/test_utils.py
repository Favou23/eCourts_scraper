from ecourts_scraper.utils import save_json, load_json
import os


def test_save_and_load(tmp_path):
    data = {'a': 1, 'b': 'x'}
    p = tmp_path / 'out.json'
    save_json(data, str(p))
    got = load_json(str(p))
    assert got == data
