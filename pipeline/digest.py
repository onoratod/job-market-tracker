"""What changed on the board since the last run.

Reads the previous snapshot (prior_snapshot.json, absent on a first run) and the one
merge.py just wrote, and records the difference as digest.json. dash2.py embeds it in
the page, so a reader sees "since yesterday" without anyone summarising by hand.

The snapshot stores fingerprint, deadline, title, inst and posted per listing, so a
changed fingerprint can be attributed to a specific field when it is one of those, and
is otherwise reported honestly as "details changed" rather than guessed at.
"""
import json, os, datetime
from snapshot import load_prior, sources_in

TODAY = (datetime.date.fromisoformat(os.environ['JOE_TODAY'])
         if os.environ.get('JOE_TODAY') else datetime.date.today())

new_snap = json.load(open('joe_snapshot.json'))
listings = new_snap['listings']
rows = {r['id']: r for r in json.load(open('rows.json'))}

prior = load_prior()
first_run = not prior
# A board added today has no history, so every one of its listings is "new" in a way
# nobody needs itemised. Count it once and say which board it was.
known_sources = sources_in(prior)
# A board that contributed nothing this run has not withdrawn its listings — it simply
# was not read. Calling 97 live jobs "withdrawn" would be the most alarming possible way
# to report a failed fetch.
unavailable = {s for s, v in new_snap.get('sources', {}).items() if not v.get('count')}
new_sources = sorted({v.get('src', 'joe') for v in listings.values()} - known_sources)

def brief(jid):
    """Everything the page needs to show one line about a listing."""
    r = rows.get(jid, {})
    return dict(id=jid,
                inst=r.get('inst', listings.get(jid, {}).get('inst', '')),
                title=r.get('title', listings.get(jid, {}).get('title', '')),
                unit=r.get('unit', ''), track=r.get('section', ''),
                dl=(r.get('deadline') or '')[:10], days=r.get('days'),
                posted=r.get('posted', ''), f=r.get('jtier'), g=r.get('gtier'),
                ok=r.get('eligible', True), src=r.get('src', 'joe'),
                url=r.get('url', ''))

WATCHED = [('deadline', 'deadline'), ('title', 'title'), ('inst', 'institution')]

added, changed, withdrawn = [], [], []
first_pull = {}
for jid, cur in listings.items():
    src = cur.get('src', 'joe')
    was = prior.get(jid)
    if was is None:
        if first_run:
            continue
        if src in new_sources:
            first_pull[src] = first_pull.get(src, 0) + 1
            continue
        added.append(brief(jid))
        continue
    if was.get('fingerprint') == cur.get('fingerprint'):
        continue
    moved = [(label, was.get(key, ''), cur.get(key, ''))
             for key, label in WATCHED if was.get(key, '') != cur.get(key, '')]
    entry = brief(jid)
    entry['moved'] = [{'field': l, 'from': a, 'to': b} for l, a, b in moved]
    # A fingerprint covers JEL codes, salary, location and the ad's length too. Say so
    # plainly rather than inventing a field name for a change we did not track.
    if not moved:
        entry['moved'] = [{'field': 'details', 'from': '', 'to': ''}]
    changed.append(entry)

for jid, was in prior.items():
    if (was.get('src') or (jid.split(':', 1)[0] if ':' in jid else 'joe')) in unavailable:
        continue
    if jid not in listings:
        src = was.get('src') or (jid.split(':', 1)[0] if ':' in jid else 'joe')
        bare = jid.split(':', 1)[1] if ':' in jid else jid
        url = (f'https://www.aeaweb.org/joe/listing.php?JOE_ID=2026-02_{bare}' if src == 'joe'
               else f'https://econjobmarket.org/positions/{bare}')
        withdrawn.append(dict(id=jid, inst=was.get('inst', ''), title=was.get('title', ''),
                              dl=was.get('deadline', '')[:10], src=src, url=url))

soon = sorted((brief(j) for j, r in rows.items()
               if r.get('eligible') and r.get('days') is not None and 0 <= r['days'] <= 14),
              key=lambda d: d['days'])

added.sort(key=lambda d: (d['days'] if d['days'] is not None else 9999))
changed.sort(key=lambda d: (d['days'] if d['days'] is not None else 9999))

digest = {'date': str(TODAY), 'first_run': first_run, 'first_pull': first_pull,
          'unavailable': sorted(unavailable),
          'counts': {'total': len(listings), 'new': len(added), 'changed': len(changed),
                     'withdrawn': len(withdrawn), 'closing_soon': len(soon)},
          'new': added, 'changed': changed, 'withdrawn': withdrawn, 'closing_soon': soon}
json.dump(digest, open('digest.json', 'w'), indent=1)

if first_run:
    print('digest: first run — nothing to compare against')
else:
    for src in sorted(unavailable):
        print(f'digest: {src} contributed nothing this run — its listings are not reported '
              'as withdrawn')
    for src, n in sorted(first_pull.items()):
        print(f'digest: first pull of {src} — {n} listings, not itemised as new')
    print(f"digest: {len(added)} new, {len(changed)} changed, {len(withdrawn)} withdrawn, "
          f"{len(soon)} closing within 14 days")
    for d in added[:10]:
        print(f"  NEW       {d['dl'] or 'no deadline':<12} {d['inst'][:38]:<38} {d['title'][:44]}")
    for d in changed[:10]:
        what = ', '.join(m['field'] for m in d['moved'])
        print(f"  CHANGED   {what:<12} {d['inst'][:38]:<38} {d['title'][:44]}")
    for d in withdrawn[:10]:
        print(f"  WITHDRAWN {'':<12} {d['inst'][:38]:<38} {d['title'][:44]}")
