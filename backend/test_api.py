import requests, json

BASE = 'http://localhost:8000'

# Test: get runs
r = requests.get(f'{BASE}/runs')
print('GET /runs status:', r.status_code)
if r.ok:
    runs = r.json()
    print(f'  Runs in DB: {len(runs)}')
    if runs:
        last = runs[0]
        print(f'  Last run id={last["id"]}, status={last["status"]}, matched={last.get("total_matched","?")}')
