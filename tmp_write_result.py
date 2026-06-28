import json
from pathlib import Path
from collections import Counter

src = Path('collections/access_logs_20.json')
if not src.exists():
    raise FileNotFoundError(f'Missing {src}')

with src.open('r', encoding='utf-8') as f:
    data = json.load(f)
items = data.get('items', data) if isinstance(data, dict) else data

status = Counter()
gate = Counter()
direction = Counter()
card = Counter()
note = Counter()
for item in items:
    status[item.get('status', 'UNKNOWN')] += 1
    gate[item.get('gateId', 'UNKNOWN')] += 1
    direction[item.get('direction', 'UNKNOWN')] += 1
    card[item.get('cardId', 'UNKNOWN')] += 1
    note[item.get('note', 'NONE')] += 1

summary = {
    'total_records': len(items),
    'status': dict(status),
    'gate': dict(gate),
    'direction': dict(direction),
    'top_cards': [{'cardId': k, 'count': v} for k, v in card.most_common(10)],
    'notes': dict(note),
}
result_path = Path('result.json')
result_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding='utf-8')
print(f'WROTE {result_path} with {len(items)} records')
