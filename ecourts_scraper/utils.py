import json


def save_json(obj, path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    return path


def load_json(path):
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)
