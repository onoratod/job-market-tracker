"""Build the dashboard page(s) from rows.json + page_template.html.

Two editions from one template:
  personal — Danny's own tracker. Shortlist and applications live in the published
             page (#joe-state) and are carried forward by the daily run.
  shared   — the edition he sends to classmates. No one's personal data is in the
             page; each viewer's stars, applications and preferences live in their
             own browser. Scoring happens in the browser from each viewer's own
             field/region/track choices, so the same feed sorts differently per person.
"""
import json, datetime, sys, re
import os as _os

rows = json.load(open('rows.json'))
snap = json.load(open('joe_snapshot.json'))
TODAY = (datetime.date.fromisoformat(_os.environ['JOE_TODAY'])
         if _os.environ.get('JOE_TODAY') else datetime.date.today())
CYCLE = '2026-02'

def pack(r):
    screen = 'Eligible' if r['eligible'] else ('Not econ' if r['discipline']=='Non-econ' else 'Senior only')
    if r['eligible'] and (r['discipline']=='Check' or r['rank_fit']=='Check rank'): screen='Check'
    return dict(id=r['id'], inst=r['inst'], unit=r['unit'], title=r['title'], track=r['section'],
                dl=r['deadline'][:10], days=r['days'], posted=(r.get('posted') or None),
                loc=r['loc'], jel=r['jel'], mats=r['materials'],
                kw=r['keywords'], sal=r['salary'], f=r['jtier'], g=r['gtier'], screen=screen,
                ok=r['eligible'], fp=r['fingerprint'],
                # Raw fields the shared edition scores from in the browser. f/g above are
                # Danny's tiers, computed in score.py; a classmate's are computed from these.
                cc=r.get('country',''), st=r.get('state',''),
                src=r.get('src','joe'),
                # The board's own field names, shown on expand so the bucket mapping is
                # visible rather than something a reader has to take on trust.
                nat=r.get('fields_native') or [],
                url=r.get('url',''))

data = [pack(r) for r in rows]
el   = [d for d in data if d['ok']]
out  = [d for d in data if not d['ok']]
soon = sorted([d for d in el if d['days'] is not None and 0 <= d['days'] <= 30], key=lambda d: d['days'])

def j(o): return json.dumps(o, separators=(',',':')).replace('<', '\\u003c')

# The Claude artifact host wraps published pages in a doctype/head/body skeleton.
# Nothing does that on a plain web host, so the GitHub Pages copy ships its own.
FAVICON = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E"
           "%3Ctext y='52' font-size='52'%3E%F0%9F%93%8B%3C/text%3E%3C/svg%3E")
def standalone(fragment):
    title = 'Econ Job Market 2026&ndash;27'
    m = re.match(r'\s*<title>(.*?)</title>\s*', fragment, re.S)
    if m:
        title = m.group(1)
        fragment = fragment[m.end():]
    return ('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width,initial-scale=1">\n'
            '<meta name="color-scheme" content="light dark">\n'
            f'<title>{title}</title>\n'
            f'<link rel="icon" href="{FAVICON}">\n'
            '</head>\n<body>\n' + fragment + '\n</body>\n</html>\n')

# What changed since the last run, written by digest.py. Embedded in the page so a
# reader sees it where they already are, instead of in a notification somewhere else.
DIGEST = json.load(open('digest.json')) if _os.path.exists('digest.json') else {}
SOURCES = snap.get('sources', {})

SRC_LABEL = {'joe': 'AEA JOE', 'ejm': 'EconJobMarket'}
BOARDS = ' + '.join(SRC_LABEL.get(s, s) for s in
                    sorted({r.get('src', 'joe') for r in rows},
                           key=lambda s: 0 if s == 'joe' else 1))


def build(mode, state, outfile):
    TPL = open('page_template.html').read()
    html = (TPL.replace('__MODE__', mode)
               .replace('__DIGEST__', j(DIGEST))
               .replace('__DATA__', j(el)).replace('__OUT__', j(out)).replace('__SOON__', j(soon))
               .replace('__STATE__', j(state)).replace('__PULLED__', TODAY.strftime('%b %-d, %Y'))
               .replace('__BOARDS__', BOARDS).replace('__SOURCES__', j(SOURCES))
               .replace('__NEL__', str(len(el))).replace('__NF1__', str(sum(1 for d in el if d['f']==1)))
               .replace('__NSOON__', str(len(soon))).replace('__NOUT__', str(len(out))))
    open(outfile, 'w').write(html)
    print(f'{mode:8} -> {outfile}  {len(html):,} bytes | {len(el)} eligible | '
          f'{len(soon)} soon | {len(out)} screened')
    return html

# --- personal edition ---------------------------------------------------------
# Danny's shortlist and application state. Write the live artifact's picks to
# prior_picks.json before running this — republishing with an empty picks map
# wipes the shortlist, the notes and every application stage.
# Built only when a prior_picks.json is present. The live tracker is the shared edition,
# so in the normal case there is nothing to build here and nothing to warn about.
if _os.path.exists('prior_picks.json'):
    picks = json.load(open('prior_picks.json'))
    if not picks:
        print('WARNING: prior_picks.json is empty — the personal page would publish an empty shortlist')
    build('personal', {'picks': picks, 'pulled': str(TODAY), 'cycle': CYCLE,
                       'snapshot': snap['listings']}, 'job_market_dashboard.html')

# --- shared edition -----------------------------------------------------------
# Carries NO picks: this page goes to people Danny is competing with, and everything in
# a published page is visible to everyone holding the link. Every viewer's own stars live
# in their browser.
# It DOES carry the snapshot — fingerprints, first_seen and posting dates for each listing,
# which is listing metadata, not anybody's personal data. The daily run reads it back to
# tell new listings from changed ones and to keep posting dates; drop it and every listing
# looks new every morning.
shared_html = build('shared', {'picks': {}, 'pulled': str(TODAY), 'cycle': CYCLE,
                                'snapshot': snap['listings']}, 'job_market_shared.html')

# --- the copy that goes to GitHub Pages ---------------------------------------
_os.makedirs('site', exist_ok=True)
open('site/index.html', 'w').write(standalone(shared_html))
print('site     -> site/index.html  (standalone, for GitHub Pages)')
