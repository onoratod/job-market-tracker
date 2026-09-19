"""Join every board into one feed: screens, fingerprints, and the snapshot.

Ids are namespaced by source — joe:111477639, ejm:12639 — because the two boards
number their listings independently and a collision would silently attach somebody's
star to the wrong job. Picks saved before namespacing existed carry bare ids and are
read as JOE, both here and in the page.

Listings that appear on both boards are kept twice, deliberately. Seeing a job twice
costs a few seconds; hiding one costs a job.
"""
import json, re, html, hashlib, datetime, os, collections
import xml.etree.ElementTree as ET
from screens import track_rank
from snapshot import load_prior, sources_in
from metro import metro_of

def clean(v):
    v = html.unescape(html.unescape(v or ''))
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', v)).strip()

MATS = [('CV', r'curriculum vitae|\bC\.?V\.?\b|resume'),
        ('Cover ltr', r'cover letter|letter of (application|interest)'),
        ('Refs/letters', r'letters? of (reference|recommendation)|\breferences\b|referees'),
        ('JMP/sample', r'job market paper|writing sample|research paper'),
        ('Research stmt', r'research statement|statement of research|research agenda'),
        ('Teaching stmt', r'teaching statement|statement of teaching|teaching philosophy|teaching portfolio'),
        ('Teaching evals', r'teaching evaluation|evidence of teaching effectiveness'),
        ('Transcripts', r'transcript')]

TODAY = str(datetime.date.fromisoformat(os.environ['JOE_TODAY'])
            if os.environ.get('JOE_TODAY') else datetime.date.today())

# ---------------------------------------------------------------- JOE
# Each board writes its own file; merge.py is the only thing that writes rows.json.
# (It used to read and rewrite rows.json, so re-running it without re-running
# score.py failed on ids it had already namespaced.)
rows = json.load(open('joe_rows.json'))
flags = json.load(open('flags.json'))

ft, kws = {}, {}
for p in ET.parse('joe_full.xml').getroot().findall('.//position'):
    ft[p.get('jp_id')] = clean(p.findtext('jp_full_text'))
    kws[p.get('jp_id')] = ', '.join(x.strip() for x in re.split(r'[\n\r]+',
        html.unescape(p.findtext('jp_keywords') or '')) if x.strip())

posted = json.load(open('posted.json')) if os.path.exists('posted.json') else {}

for r in rows:
    for k in ('inst', 'title', 'loc', 'jel', 'section'):
        r[k] = clean(r[k])
    f = flags[r['id']]
    t = ft[r['id']]
    r.update(src='joe', discipline=f['discipline'], rank_fit=f['rank'], unit=f['unit'],
             materials=', '.join(n for n, pat in MATS if re.search(pat, t, re.I)),
             keywords=kws[r['id']], adlen=len(t),
             posted_raw=posted.get(r['id'], ''))

# ---------------------------------------------------------------- other boards
ejm = json.load(open('ejm_rows.json')) if os.path.exists('ejm_rows.json') else []
for r in ejm:
    t = r.pop('adtext', '')
    r.update(materials=', '.join(n for n, pat in MATS if re.search(pat, t, re.I)),
             keywords=', '.join(r.get('fields_native', [])),
             posted_raw=r.get('posted', ''))
if not ejm:
    print('NOTE: no ejm_rows.json — building from JOE alone')

rows = rows + ejm

# ---------------------------------------------------------------- one feed
prior = load_prior()

for r in rows:
    if ':' not in r['id']:
        if r['src'] == 'joe':
            r['url'] = f"https://www.aeaweb.org/joe/listing.php?JOE_ID=2026-02_{r['id']}"
        r['id'] = f"{r['src']}:{r['id']}"
    was = prior.get(r['id']) or {}
    # The screens no longer remove anything. A listing the screen dislikes is flagged and
    # sorted lower, but stays in the table — the screen is wrong sometimes, and a listing
    # nobody can see is a listing nobody can correct.
    r['flag'] = ('not-econ' if r['discipline'] == 'Non-econ'
                 else 'senior' if r['rank_fit'] == 'Senior only'
                 else 'check' if (r['discipline'] == 'Check' or r['rank_fit'] == 'Check rank')
                 else '')
    r['flag_why'] = {
        'not-econ': 'Department and title do not read as economics or econ-adjacent',
        'senior': 'Advertised above assistant level',
        'check': 'Field or rank is ambiguous here — worth reading the ad'}.get(r['flag'], '')
    r['srank'] = track_rank(r['section'])
    r['score'] = (r['jtier'] * 100 + r['gtier'] * 10 + r['srank']
                  + (1000 if r['flag'] in ('not-econ', 'senior') else 0))
    r['city'] = r.get('city') or ''
    r['metro'] = metro_of(r['loc'], r.get('country', ''), r['city'])
    # Posting date: this run's parse first, then the date already carried in the snapshot.
    # Never first_seen — that is when WE saw it, not when the board posted it.
    r['posted'] = r.get('posted_raw') or was.get('posted') or ''
    r.pop('posted_raw', None)
    r['fingerprint'] = hashlib.sha256('|'.join([
        r['title'], r['inst'], r['deadline'], r['section'], r['jel'], r['loc'], r['salary'],
        str(r.get('adlen', 0))]).encode()).hexdigest()[:16]

rows.sort(key=lambda r: (r['score'], r['days'] if r['days'] is not None else 9999))
json.dump(rows, open('rows.json', 'w'), indent=1)

no_posted = [r['id'] for r in rows if not r['posted']]
if no_posted:
    print(f'NOTE: {len(no_posted)} listing(s) with no posting date:', no_posted[:8])

snap = {}
for r in rows:
    was = prior.get(r['id']) or {}
    entry = {'fingerprint': r['fingerprint'], 'src': r['src'],
             'first_seen': was.get('first_seen', TODAY), 'last_seen': TODAY,
             'deadline': r['deadline'], 'posted': r['posted'],
             'title': r['title'], 'inst': r['inst']}
    if r['src'] != 'joe':
        # The location lookup that cost a request per listing — cached so tomorrow's run
        # only fetches detail pages for listings it has never seen.
        entry.update(cc=r.get('country', ''), st=r.get('state', ''),
                     city=r.get('city', ''), start=r.get('start', ''))
    snap[r['id']] = entry
# Which boards are in this feed, and when each was last seen. A board that fails its
# parse contributes nothing rather than something half-right, so the page needs to say
# it is missing — otherwise the feed just quietly shrinks by a third.
sources = {}
for src in sorted({r['src'] for r in rows}):
    sources[src] = {'count': sum(1 for r in rows if r['src'] == src), 'last_seen': TODAY}
for src in sources_in(prior):
    if src not in sources:
        last = max((v.get('last_seen', '') for v in prior.values()
                    if (v.get('src') or 'joe') == src), default='')
        sources[src] = {'count': 0, 'last_seen': last}
        print(f'WARNING: no listings from {src} this run — last seen {last or "unknown"}')

json.dump({'cycle': '2026-02', 'pulled': TODAY, 'sources': sources, 'listings': snap},
          open('joe_snapshot.json', 'w'), indent=1)

by_src = collections.Counter(r['src'] for r in rows)
flags = collections.Counter(r['flag'] for r in rows if r['flag'])
print(f"merged {len(rows)} listings {dict(by_src)} | flagged {dict(flags)} (none removed)")
print('field tier 1:', sum(1 for r in rows if r['jtier'] == 1))
print('tier1 field + geo 1-2:', sum(1 for r in rows if r['jtier'] == 1 and r['gtier'] <= 2))
no_city = sum(1 for r in rows if not r['city'] and ',' not in (r['loc'] or ''))
print(f"in a major metro: {sum(1 for r in rows if r['metro'])} "
      f"| {no_city} listing(s) name no city, so metro is unknown for them")
print('\nTop 12 by priority:')
for r in rows[:12]:
    print(f"  {r['score']:>4} {r['src']:<4} {r['section'][:16]:<16} {r['deadline'][:10]:<10} "
          f"{r['inst'][:32]:<32} {r['title'][:34]}")
