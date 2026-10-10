"""Bounty burst scanner v2 - no repo commits, state in Actions Cache.

State and dashboard live in ./state/ which is cached by GitHub Actions
between runs. Nothing is ever committed back to the repo.

Cold start (no cache): seeds a baseline silently, no alerts.
"""
import json
import os
import re
import urllib.parse
import urllib.request

WATCH = [
    ("documenso/documenso", ["bounty", "\U0001f48e Bounty"]),
]

NTFY_TOPIC = "ansh-bounty-alerts"
STATE_DIR = "state"


def api(url: str):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'python', 'Accept': 'application/vnd.github+json'})
    return json.load(urllib.request.urlopen(req))


def notify(msg: str, url: str):
    try:
        req = urllib.request.Request(f'https://ntfy.sh/{NTFY_TOPIC}',
                                     data=msg.encode('utf-8'),
                                     headers={'Title': 'BOUNTY FOUND', 'Priority': 'urgent'})
        urllib.request.urlopen(req)
    except Exception as e:
        print(f'notify failed: {e}')


DASH_CSS = """
body{font-family:-apple-system,system-ui,sans-serif;background:#0d1117;color:#e6edf3;
 max-width:900px;margin:2rem auto;padding:0 1rem}
h1{border-bottom:1px solid #30363d;padding-bottom:.5rem}
.bounty{background:#161b22;border:1px solid #30363d;border-radius:8px;
 padding:1rem;margin:.75rem 0}
.bounty a{color:#58a6ff;text-decoration:none;font-weight:600}
.amount{background:#238636;color:#fff;border-radius:4px;padding:2px 8px;
 font-size:.85rem;margin-right:.5rem}
.meta{color:#8b949e;font-size:.8rem;margin-top:.4rem}
"""


def write_dashboard(rows):
    os.makedirs(STATE_DIR, exist_ok=True)
    items = '\n'.join(
        f'<div class="bounty"><span class="amount">{r["amount"]}</span>'
        f'<a href="{r["url"]}">{r["title"]}</a>'
        f'<div class="meta">{r["repo"]}#{r["number"]} - found {r["found"]}</div></div>'
        for r in rows)
    html = f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Bounty Monitor</title>
<style>{DASH_CSS}</style></head><body>
<h1>Bounty Monitor - {len(rows)} found</h1>
<p style="color:#8b949e">updated {__import__('time').strftime('%Y-%m-%d %H:%M UTC', __import__('time').gmtime())}</p>
{items if items else '<p>No bounties found yet.</p>'}
</body></html>"""
    with open(os.path.join(STATE_DIR, 'bounties.html'), 'w', encoding='utf-8') as f:
        f.write(html)


def main():
    os.makedirs(STATE_DIR, exist_ok=True)
    seen_path = os.path.join(STATE_DIR, 'seen.json')
    hist_path = os.path.join(STATE_DIR, 'history.json')

    cold = not os.path.exists(seen_path)
    try:
        with open(seen_path) as f:
            seen = set(json.load(f))
    except Exception:
        seen = set()

    try:
        with open(hist_path) as f:
            history = json.load(f)
    except Exception:
        history = []

    if cold:
        print('cold start: seeding baseline, no alerts')

    for repo, labels in WATCH:
        for label in labels:
            q = urllib.parse.quote(f'repo:{repo} label:"{label}" state:open type:issue')
            try:
                d = api(f'https://api.github.com/search/issues?q={q}&sort=created&order=desc&per_page=20')
            except Exception as e:
                print(f'{repo} [{label}] error: {e}')
                continue
            for i in d.get('items', []):
                key = f"{repo}#{i['number']}"
                if key in seen:
                    continue
                seen.add(key)
                amts = re.findall(r'\$[\d,]+', i['title'] + ' ' + (i.get('body') or '')[:300])
                entry = {'repo': repo, 'number': i['number'], 'title': i['title'],
                         'amount': amts[0] if amts else '?', 'url': i['html_url'],
                         'found': __import__('time').strftime('%Y-%m-%d %H:%M', __import__('time').gmtime())}
                history.insert(0, entry)
                if cold:
                    print(f'baseline: {key}')
                else:
                    print(f'NEW: {key}')
                    notify(f"{key} {entry['amount']} {i['title'][:70]} {i['html_url']}")

    with open(seen_path, 'w') as f:
        json.dump(sorted(seen), f)
    with open(hist_path, 'w') as f:
        json.dump(history, f)
    write_dashboard(history)
    print(f'done: {len(seen)} tracked, {len(history)} in history')


if __name__ == '__main__':
    main()
