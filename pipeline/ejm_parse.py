"""EconJobMarket -> rows in the same shape score.py produces for JOE.

Two tiers, for the same reason JOE needs two: the cheap page has most of what we want
and is missing one thing we cannot do without.

  LIST PAGES  (2-3 requests) give every listing's id, title, department, institution,
              position types, fields, posted date, deadline, expiry and the full ad text.
  DETAIL PAGE (one request per listing, once ever) gives the full street address, which
              is the only place a US state appears. Without it every US listing is
              "United States" with no region, and the region preference cannot rank it.

Detail results are cached in the snapshot the previous run committed, so a normal day
fetches a handful of pages, not the whole board.

Writes ejm_rows.json only on success. A partial parse writes nothing: one broken board
must never quietly shrink the other one's feed.
"""
import re, json, os, sys, html, time, datetime, urllib.request, glob
from screens import discipline_of, rank_of, track_rank, jel_tier, geo_tier, POLICY

TODAY = (datetime.date.fromisoformat(os.environ['JOE_TODAY'])
         if os.environ.get('JOE_TODAY') else datetime.date.today())
UA = 'job-market-tracker (+https://github.com/onoratod/job-market-tracker)'
BASE = 'https://econjobmarket.org'

# --- their vocabulary -> the buckets the preferences panel offers ----------------
# EconJobMarket has no JEL codes. The panel's buckets are semantic categories with
# human labels, so mapping "Labor; Demographic Economics" to the labour bucket is a
# translation, not a fudge. Their own field names are kept on the row and shown when
# a listing is expanded, so nobody has to trust this table blindly.
FIELD_BUCKET = {
    'Any field':                        ['00'],
    'Applied microeconomics':           ['D', '00'],   # broad applied search
    'Labor; Demographic Economics':     ['J'],
    'Economic History':                 ['N'],
    'Macroeconomics; Monetary':         ['E'],
    'International Finance/Macro':      ['F'],
    'International Trade':              ['F'],
    'Finance':                          ['G'],
    'Insurance':                        ['G'],
    'Public Economics':                 ['H'],
    'Health; Education; Welfare':       ['I'],
    'Law and Economics':                ['K'],
    'Industrial Organization':          ['L'],
    'Development; Growth':              ['O'],
    'Environmental; Ag. Econ.':         ['Q'],
    'Urban; Rural; Regional Economics': ['R'],
    'Real Estate':                      ['R'],
    'Econometrics':                     ['C'],
    'Statistics':                       ['C'],
    'Computational Economics':          ['C'],
    'Operations Research':              ['C'],
    'Experimental Economics':           ['C'],
    'Microeconomic theory':             ['D'],
    'Behavioral Economics':             ['D'],
    'Decision Sciences':                ['D'],
    'Political Economy':                ['D'],
    'Business Economics':               ['M'],
    'Management, Information Technology': ['M'],
    'Management, General':              ['M'],
    'Marketing':                        ['M'],
    'Accounting':                       ['M'],
    'Organizational Behavior':          ['M'],
    'Other':                            [],            # genuinely unclassified — say nothing
}
# "Various fields" is the collapsed heading above a field list, not a field.
FIELD_SKIP = {'Various fields'}

TYPE_TRACK = {
    'Assistant Professor':          'Academic TT',
    'Associate Professor':          'Academic TT',
    'Full Professor':               'Academic TT',
    'Tenured Professor':            'Academic TT',
    'Untenured Professor':          'Academic TT',
    'Lecturer':                     'Lecturer',
    'Senior Lecturer':              'Lecturer',
    'Visiting Assistant Professor': 'Postdoc/Visiting',
    'Visiting Associate Professor': 'Postdoc/Visiting',
    'Visiting Professor':           'Postdoc/Visiting',
    'Postdoctoral Scholar':         'Postdoc/Visiting',
    'Other academic':               'Postdoc/Visiting',
    'Research Assistant':           'Nonacademic other',   # the pre-doc market
    'Consultant':                   'Private sector',
    'Other nonacademic':            'Private sector',      # POLICY employers reassigned below
}
TYPE_SKIP = {'Various position types'}

# Their address field is free text: "Providence, RI" and "Providence, Rhode Island" both
# occur, sometimes on two ads for the same job. Everything downstream matches on the full
# name, so two identical jobs would otherwise land in different geography tiers.
US_STATES = {
    'AL': 'Alabama', 'AK': 'Alaska', 'AZ': 'Arizona', 'AR': 'Arkansas', 'CA': 'California',
    'CO': 'Colorado', 'CT': 'Connecticut', 'DE': 'Delaware', 'DC': 'District of Columbia',
    'FL': 'Florida', 'GA': 'Georgia', 'HI': 'Hawaii', 'ID': 'Idaho', 'IL': 'Illinois',
    'IN': 'Indiana', 'IA': 'Iowa', 'KS': 'Kansas', 'KY': 'Kentucky', 'LA': 'Louisiana',
    'ME': 'Maine', 'MD': 'Maryland', 'MA': 'Massachusetts', 'MI': 'Michigan',
    'MN': 'Minnesota', 'MS': 'Mississippi', 'MO': 'Missouri', 'MT': 'Montana',
    'NE': 'Nebraska', 'NV': 'Nevada', 'NH': 'New Hampshire', 'NJ': 'New Jersey',
    'NM': 'New Mexico', 'NY': 'New York', 'NC': 'North Carolina', 'ND': 'North Dakota',
    'OH': 'Ohio', 'OK': 'Oklahoma', 'OR': 'Oregon', 'PA': 'Pennsylvania',
    'RI': 'Rhode Island', 'SC': 'South Carolina', 'SD': 'South Dakota', 'TN': 'Tennessee',
    'TX': 'Texas', 'UT': 'Utah', 'VT': 'Vermont', 'VA': 'Virginia', 'WA': 'Washington',
    'WV': 'West Virginia', 'WI': 'Wisconsin', 'WY': 'Wyoming',
}
FULL_STATES = {v.lower(): v for v in US_STATES.values()}


def norm_state(s):
    s = (s or '').strip()
    if not s:
        return ''
    if len(s) == 2 and s.upper() in US_STATES:
        return US_STATES[s.upper()]
    return FULL_STATES.get(s.lower(), s)


MONTHS = {m: i for i, m in enumerate(
    ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'], 1)}


def iso(datestr):
    """'16 Nov 2026' -> '2026-11-16'. Returns '' for anything unexpected."""
    m = re.match(r'(\d{1,2})\s+([A-Za-z]{3})[a-z]*\s+(\d{4})', (datestr or '').strip())
    if not m:
        return ''
    d, mon, y = m.groups()
    if mon[:3].title() not in MONTHS:
        return ''
    return f'{y}-{MONTHS[mon[:3].title()]:02d}-{int(d):02d}'


def text(fragment):
    fragment = re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', fragment, flags=re.S)
    fragment = re.sub(r'<br\s*/?>', '\n', fragment)
    fragment = re.sub(r'<[^>]+>', ' ', fragment)
    return [l.strip() for l in html.unescape(fragment).split('\n') if l.strip()]


def bullets(fragment):
    return [x.strip() for x in ' '.join(text(fragment)).split('•') if x.strip()]


def parse_list_pages():
    rows = []
    for fn in sorted(glob.glob('ejm_p*.html')):
        h = open(fn, encoding='utf-8', errors='replace').read()
        h = re.sub(r'<!--\[if (BLOCK|ENDBLOCK)\]><!\[endif\]-->', '', h)
        anchors = [(m.start(), m.group(1)) for m in re.finditer(r'<a name="position(\d+)">', h)]
        for i, (start, jid) in enumerate(anchors):
            end = anchors[i + 1][0] if i + 1 < len(anchors) else len(h)
            seg = h[start:end]
            cols4 = [m.start() for m in re.finditer(r'<div class="col-md-4">', seg)]
            cols2 = [m.start() for m in re.finditer(r'<div class="col-md-2">', seg)]
            if len(cols4) < 2 or len(cols2) < 2:
                continue   # not a listing panel

            title_m = re.search(r'class="adBody"[^>]*>\s*(.*?)</a>', seg, re.S)
            title = html.unescape(re.sub(r'<[^>]+>', '', title_m.group(1))).strip() if title_m else ''

            loc_m = re.search(r'</button>\s*<br\s*/?>\s*(.*?)\s*(?:\(<a href="[^"]*mapPosition|\.<)',
                              seg, re.S)
            loc = html.unescape(re.sub(r'<[^>]+>', '', loc_m.group(1))).strip().rstrip('.,') if loc_m else ''

            org = text(seg[cols4[1]:cols2[0]])
            dept = org[0] if org else ''
            inst = org[1] if len(org) > 1 else (org[0] if org else '')

            tf = seg[cols2[0]:cols2[1]]
            halves = re.split(r'<hr class="type-field-separator">', tf)
            types = [t for t in bullets(halves[0]) if t not in TYPE_SKIP]
            # A listing with several fields collapses them behind a "Various fields" link;
            # the real list is inside #cats-<id>. A single-field listing prints the field
            # itself with no wrapper. Reading the text flow blindly glues the heading onto
            # the first field ("Various fields Econometrics") and loses that field.
            cats = re.search(r'<div id="cats-' + jid + r'"[^>]*>(.*?)</div>', tf, re.S)
            if cats:
                fields = [f for f in bullets(cats.group(1)) if f not in FIELD_SKIP]
            elif len(halves) > 1:
                fields = [f for f in bullets(halves[1]) if f not in FIELD_SKIP]
            else:
                fields = []

            dates = seg[cols2[1]:]
            def span(pat):
                m = re.search(pat, dates)
                return html.unescape(m.group(1)).strip() if m else ''
            posted   = iso(span(r'<span class="bg-info">([^<]+)</span>'))
            deadline = iso(span(r'<span class="negative">([^<]+)</span>'))
            expires  = iso(span(r'<span style="background-color: #cccccc;">([^<]+)</span>'))

            body_m = re.search(r'<div id="ad-' + jid + r'"[^>]*>(.*?)</div>\s*</div>', seg, re.S)
            adtext = ' '.join(text(body_m.group(1))) if body_m else ''

            rows.append(dict(id=jid, title=title, loc_short=loc, dept=dept, inst=inst,
                             types=types, fields=fields, posted=posted, deadline=deadline,
                             expires=expires, adtext=adtext,
                             featured='Featured advertisement' in seg[:900]))
    return rows


def fetch_detail(jid):
    """The listing's own page. Labelled fields, and the only place a US state appears."""
    req = urllib.request.Request(f'{BASE}/positions/{jid}', headers={'User-Agent': UA})
    with urllib.request.urlopen(req, timeout=45) as r:
        h = r.read().decode('utf-8', 'replace')
    lines = text(re.sub(r'<(script|style)[^>]*>.*?</\1>', ' ', h, flags=re.S))
    out = {}
    for i, l in enumerate(lines):
        if l.rstrip(':').strip() in ('Location of job', 'Degree required', 'Job start date',
                                     'Job duration', 'Letters of reference required'):
            key = l.rstrip(':').strip()
            if i + 1 < len(lines):
                out[key] = lines[i + 1]
    return out


def split_address(addr):
    """'... Detroit, Michigan, 48202, United States' -> ('UNITED STATES', 'Michigan', 'Detroit')."""
    parts = [p.strip() for p in (addr or '').split(',') if p.strip()]
    if not parts:
        return ('', '', '')
    country = parts[-1].upper()
    state = city = ''
    if country == 'UNITED STATES':
        # ..., City, State, ZIP, United States   (ZIP optional)
        rest = parts[:-1]
        if rest and re.fullmatch(r'\d{5}(-\d{4})?', rest[-1]):
            rest = rest[:-1]
        if rest:
            state = norm_state(rest[-1])
            if len(rest) > 1:
                city = rest[-2]
    else:
        # Outside the US the second-to-last piece is often a postcode ("V5A 1S6"),
        # so the list page's own city is the better source; the caller passes it in.
        city = parts[-2] if len(parts) > 1 else ''
        if re.fullmatch(r'[\dA-Z][\dA-Z \-]{2,9}', city or ''):
            city = ''
    return (country, state, city)


def main():
    listings = parse_list_pages()
    if not listings:
        sys.exit('FATAL ejm_parse.py: no listings parsed from the saved pages')

    ids = [r['id'] for r in listings]
    if len(set(ids)) != len(ids):
        sys.exit(f'FATAL ejm_parse.py: duplicate ids in one pull ({len(ids) - len(set(ids))})')

    dated = sum(1 for r in listings if r['deadline'] or r['posted'])
    if dated < 0.9 * len(listings):
        sys.exit(f'FATAL ejm_parse.py: only {dated}/{len(listings)} listings carried dates — '
                 'the markup changed; publishing nothing from this board')

    # location cache: what the previous run already looked up
    cache = {}
    if os.path.exists('prior_snapshot.json'):
        prior = json.load(open('prior_snapshot.json'))
        prior = prior.get('listings', prior)
        for k, v in prior.items():
            if k.startswith('ejm:') and v.get('cc'):
                cache[k[4:]] = {'cc': v.get('cc', ''), 'st': v.get('st', ''),
                                'city': v.get('city', ''), 'start': v.get('start', '')}

    fetched = failed = 0
    for r in listings:
        hit = cache.get(r['id'])
        if hit:
            r.update(hit)
            continue
        try:
            d = fetch_detail(r['id'])
            cc, st, city = split_address(d.get('Location of job', ''))
            if not city:
                city = r['loc_short'].split(',')[0].strip()
            r.update(cc=cc, st=st, city=city, start=d.get('Job start date', ''))
            fetched += 1
            time.sleep(0.6)          # be a polite guest
        except Exception as e:
            # Fall back to the list page's country; the region preference just cannot
            # place it inside the US until a later run picks the detail page up.
            tail = (r['loc_short'].split(',')[-1] or '').strip().upper()
            r.update(cc=tail, st='', city='', start='')
            failed += 1
            if failed <= 3:
                print(f'  note: detail page {r["id"]} failed ({e.__class__.__name__}) — '
                      'country only for now')

    rows = []
    for r in listings:
        buckets, native = [], []
        for f in r['fields']:
            native.append(f)
            for b in FIELD_BUCKET.get(f, []):
                if b not in buckets:
                    buckets.append(b)
        tracks = [TYPE_TRACK.get(t) for t in r['types'] if TYPE_TRACK.get(t)]
        track = min(tracks, key=track_rank) if tracks else 'Nonacademic other'
        # A central bank advertising "Assistant Professor" is still a central bank. EJM's
        # position types are academic-shaped for everyone, so the employer decides here —
        # unless the employer is itself a university (a "School of Government" is academic).
        if POLICY.search(r['inst']) and not re.search(r'universit|college|\bschool\b|institute of technology',
                                                      r['inst'], re.I):
            track = 'Policy/Gov'

        unit = ' | '.join([r['dept'], r['title']])
        nonacad = track in ('Policy/Gov', 'Private sector', 'Nonacademic other')
        kind = ('tt' if track == 'Academic TT' else
                'temp' if track in ('Postdoc/Visiting', 'Lecturer') else 'nonacad')

        dl = r['deadline']
        days = None
        if dl:
            try:
                days = (datetime.date.fromisoformat(dl) - TODAY).days
            except ValueError:
                days = None

        locs = [(r.get('cc', ''), r.get('st', ''), r.get('city', ''))]
        loc_label = ', '.join(x for x in (r.get('city') or r['loc_short'].split(',')[0],
                                          r.get('st', '')) if x) or r['loc_short']
        rows.append(dict(
            id=r['id'], src='ejm', inst=r['inst'], unit=r['dept'], title=r['title'],
            section=track, srank=track_rank(track),
            deadline=dl, days=days, posted=r['posted'], expires=r['expires'],
            jel=';'.join(buckets), jtier=jel_tier(buckets), fields_native=native,
            types_native=r['types'],
            loc=loc_label, country=r.get('cc', ''), state=r.get('st', ''),
            city=r.get('city', ''), gtier=geo_tier(locs), salary='',
            discipline=discipline_of(unit, nonacademic=nonacad),
            rank_fit=rank_of(r['title'], kind),
            adlen=len(r['adtext']), adtext=r['adtext'],
            url=f'{BASE}/positions/{r["id"]}'))

    json.dump(rows, open('ejm_rows.json', 'w'), indent=1)
    import collections
    print(f'ejm_parse.py: {len(rows)} listings | {fetched} detail pages fetched, '
          f'{len(cache)} from cache, {failed} failed')
    print('  tracks    :', dict(collections.Counter(r['section'] for r in rows)))
    print('  countries :', dict(collections.Counter(r['country'] or '?' for r in rows).most_common(6)))
    print('  US without a state:', sum(1 for r in rows if r['country'] == 'UNITED STATES' and not r['state']))
    print('  no field bucket   :', sum(1 for r in rows if not r['jel']))


if __name__ == '__main__':
    main()
