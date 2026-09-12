import json, re, html, hashlib, datetime, os
import xml.etree.ElementTree as ET

rows  = json.load(open('rows.json'))
flags = json.load(open('flags.json'))

def clean(v):
    v = html.unescape(html.unescape(v or ''))
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', v)).strip()

ft, kws = {}, {}
for p in ET.parse('joe_full.xml').getroot().findall('.//position'):
    ft[p.get('jp_id')]  = clean(p.findtext('jp_full_text'))
    kws[p.get('jp_id')] = ', '.join(x.strip() for x in re.split(r'[\n\r]+',
        html.unescape(p.findtext('jp_keywords') or '')) if x.strip())

MATS = [('CV', r'curriculum vitae|\bC\.?V\.?\b|resume'),
        ('Cover ltr', r'cover letter|letter of (application|interest)'),
        ('Refs/letters', r'letters? of (reference|recommendation)|\breferences\b|referees'),
        ('JMP/sample', r'job market paper|writing sample|research paper'),
        ('Research stmt', r'research statement|statement of research|research agenda'),
        ('Teaching stmt', r'teaching statement|statement of teaching|teaching philosophy|teaching portfolio'),
        ('Teaching evals', r'teaching evaluation|evidence of teaching effectiveness'),
        ('Transcripts', r'transcript')]

TRACK_RANK = {'Academic TT':1, 'Postdoc/Visiting':2, 'Policy/Gov':3,
              'Private sector':4, 'Nonacademic other':5, 'Adjunct':6}

for r in rows:
    for k in ('inst','title','loc','jel','section'):
        r[k] = clean(r[k])
    f = flags[r['id']]
    r['discipline'] = f['discipline']
    r['rank_fit']   = f['rank']
    r['unit']       = f['unit']
    t = ft[r['id']]
    r['materials'] = ', '.join(n for n, pat in MATS if re.search(pat, t, re.I))
    r['keywords']  = kws[r['id']]
    r['eligible']  = f['discipline'] != 'Non-econ' and f['rank'] != 'Senior only'
    r['exclude_why'] = ('Not economics or econ-adjacent' if f['discipline'] == 'Non-econ'
                        else 'Rank above assistant level' if f['rank'] == 'Senior only' else '')
    r['srank'] = TRACK_RANK.get(r['section'], 9)
    r['score'] = r['jtier']*100 + r['gtier']*10 + r['srank'] + (0 if r['eligible'] else 1000)
    # change-detection fingerprint
    r['fingerprint'] = hashlib.sha256('|'.join([
        r['title'], r['inst'], r['deadline'], r['section'], r['jel'], r['loc'], r['salary'],
        str(len(t))]).encode()).hexdigest()[:16]

rows.sort(key=lambda r: (r['score'], r['days'] if r['days'] is not None else 9999))
json.dump(rows, open('rows.json','w'), indent=1)

TODAY = (datetime.date.fromisoformat(os.environ['JOE_TODAY'])
         if os.environ.get('JOE_TODAY') else datetime.date.today())
TODAY = str(TODAY)

# carry first_seen forward from the previous snapshot when we have one; the daily
# run writes the live dashboard's snapshot to prior_snapshot.json before calling this.
prior = {}
if os.path.exists('prior_snapshot.json'):
    p = json.load(open('prior_snapshot.json'))
    prior = p.get('listings', p)

# JOE's posting date comes from the listings pages, not the XML (see posted.py).
# Preference: this run's parse -> the date already carried on the dashboard -> none.
# Never fall back to first_seen: that is when WE first saw it, not when JOE posted it,
# and quietly mixing the two would make the sort lie.
posted = json.load(open('posted.json')) if os.path.exists('posted.json') else {}
for r in rows:
    r['posted'] = posted.get(r['id']) or (prior.get(r['id']) or {}).get('posted') or ''
no_posted = [r['id'] for r in rows if not r['posted']]
if no_posted:
    print(f'NOTE: {len(no_posted)} listing(s) with no posting date:', no_posted[:8])
json.dump(rows, open('rows.json','w'), indent=1)   # re-dump: posted is added after the sort above

snap = {r['id']: {'fingerprint': r['fingerprint'],
                  'first_seen': (prior.get(r['id']) or {}).get('first_seen', TODAY),
                  'last_seen': TODAY, 'deadline': r['deadline'],
                  'posted': r['posted'],
                  'title': r['title'], 'inst': r['inst']} for r in rows}
json.dump({'cycle':'2026-02','pulled':TODAY,'listings':snap}, open('joe_snapshot.json','w'), indent=1)

el = [r for r in rows if r['eligible']]
print(f"eligible {len(el)} / {len(rows)}   excluded {len(rows)-len(el)}")
import collections
print('excluded reasons:', dict(collections.Counter(r['exclude_why'] for r in rows if not r['eligible'])))
print('eligible + field tier 1:', sum(1 for r in el if r['jtier']==1))
print('eligible + tier1 field + geo 1-2:', sum(1 for r in el if r['jtier']==1 and r['gtier']<=2))
print('\nTop 12 by priority:')
for r in rows[:12]:
    print(f"  {r['score']:>4} {r['section'][:16]:<16} {r['discipline'][:8]:<8} {r['deadline'][:10]:<10} {r['inst'][:34]:<34} {r['title'][:38]}")
