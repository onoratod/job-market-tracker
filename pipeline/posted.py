"""Parse JOE_ID -> Date Posted from the paginated JOE listings HTML.

JOE's full_xml export carries no posting date, but every listings page prints
"Date Posted: MM/DD/YYYY" directly under each listing's link. Reads every
joe_listings_p*.html in the working directory and writes posted.json
({jp_id: "YYYY-MM-DD"}). Fails loudly rather than emitting a partial map.
"""
import re, json, glob, sys
import xml.etree.ElementTree as ET

PAT = re.compile(
    r'JOE_ID=(?:\d{4}-\d{2})_(\d+).*?listing-item-header-date-posted"\s*>\s*'
    r'Date Posted:\s*(\d{2})/(\d{2})/(\d{4})', re.S)

posted, conflicts = {}, []
files = sorted(glob.glob('joe_listings_p*.html')) or sorted(glob.glob('joe_listings.html'))
if not files:
    sys.exit('FATAL posted.py: no joe_listings_p*.html in the working directory')

for f in files:
    h = open(f, encoding='utf-8', errors='replace').read()
    for jid, mm, dd, yy in PAT.findall(h):
        iso = f'{yy}-{mm}-{dd}'
        if jid in posted and posted[jid] != iso:
            conflicts.append((jid, posted[jid], iso))
        posted[jid] = iso

ids = [p.get('jp_id') for p in ET.parse('joe_full.xml').getroot().findall('.//position')]
missing = [i for i in ids if i not in posted]
cover = (len(ids) - len(missing)) / len(ids) if ids else 0

print(f'posted.py: {len(files)} page(s), {len(posted)} dates parsed, '
      f'{len(ids)} listings in XML, coverage {cover:.1%}')
if conflicts:
    print('  WARNING conflicting dates for', conflicts[:5])
if missing:
    print('  missing posting date for', missing[:10])

json.dump(posted, open('posted.json', 'w'), indent=1)

# Loud failure: a half-parsed map would silently mis-sort the whole feed.
if cover < 0.95:
    sys.exit(f'FATAL posted.py: only {cover:.1%} of listings got a posting date — '
             'the listings-page markup probably changed. Do not publish this run; '
             'the dashboard keeps the dates it already has.')
