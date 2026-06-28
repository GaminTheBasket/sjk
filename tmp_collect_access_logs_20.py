import json
import os
import urllib.request
import urllib.error

URL = 'http://26.144.83.132:8000/access/logs/recent'
HEADERS = {'Authorization': 'Bearer local-dev-token'}
TARGET = os.path.join('collections', 'access_logs_20.json')

os.makedirs('collections', exist_ok=True)
collected = []
ids = set()
page = 0

while len(collected) < 20 and page < 10:
    query = f'{URL}?limit=20'
    req = urllib.request.Request(query, headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            payload = json.loads(resp.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        print('HTTPERROR', e.code, e.reason)
        print(e.read().decode('utf-8', errors='replace'))
        break
    except Exception as e:
        print('ERROR', type(e).__name__, e)
        break

    items = payload.get('items') if isinstance(payload, dict) else None
    if not isinstance(items, list):
        # if the endpoint returns a single record
        items = [payload]

    added = 0
    for item in items:
        log_id = item.get('logId') if isinstance(item, dict) else None
        if not log_id:
            log_id = json.dumps(item, sort_keys=True)
        if log_id in ids:
            continue
        ids.add(log_id)
        collected.append(item)
        added += 1
        if len(collected) >= 20:
            break

    if added == 0:
        break
    page += 1

with open(TARGET, 'w', encoding='utf-8') as f:
    json.dump({'items': collected, 'count': len(collected)}, f, indent=2, ensure_ascii=False)

print('WROTE', TARGET, 'records=', len(collected))
