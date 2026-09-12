import xml.etree.ElementTree as ET, datetime, json, re

import os as _os
TODAY = (datetime.date.fromisoformat(_os.environ['JOE_TODAY'])
         if _os.environ.get('JOE_TODAY') else datetime.date.today())

T1_JEL_PREFIX = ('J', 'N')
T1_JEL_EXACT  = {'00'}
T2_JEL = {'I1','I2','I3','D1','R1','R2','K4','O1'}
T2_JEL_PREFIX = ('H',)

NE_WEST = {'New York','New Jersey','Pennsylvania','District of Columbia','Maryland','Virginia',
           'Massachusetts','Connecticut','Rhode Island','Delaware','New Hampshire',
           'California','Washington','Oregon'}
EUROPE = {'UNITED KINGDOM','GERMANY','FRANCE','ITALY','SPAIN','NETHERLANDS','SWITZERLAND','SWEDEN',
          'NORWAY','DENMARK','FINLAND','BELGIUM','AUSTRIA','IRELAND','PORTUGAL','POLAND','CZECH REPUBLIC'}

SEC_RANK = {
 'US: Full-Time Academic (Permanent, Tenure Track or Tenured)': (1,'Academic TT'),
 'International: Full-Time Academic (Permanent, Tenure Track or Tenured)': (1,'Academic TT'),
 'US: Other Academic (Visiting or Temporary)': (2,'Postdoc/Visiting'),
 'International: Other Academic (Visiting or Temporary)': (2,'Postdoc/Visiting'),
 'Full-Time Nonacademic': (3,'Nonacademic FT'),
 'Other Nonacademic (Temporary, Part-Time, Non-Salaried, Consulting, Etc.)': (4,'Nonacademic other'),
 'US: Other Academic (Part-time or Adjunct)': (5,'Adjunct'),
 'International: Other Academic (Part-time or Adjunct)': (5,'Adjunct'),
}

POLICY = re.compile(r'federal reserve|council of economic|congressional budget|international monetary|'
                    r'world bank|treasury|bureau of labor|census|inter-american|oecd|'
                    r'brookings|urban institute|rand|mathematica|abdul latif|center for global development|'
                    r'national bureau|department of|ministry|commission', re.I)

def jel_tier(codes):
    for c in codes:
        if c in T1_JEL_EXACT or c.startswith(T1_JEL_PREFIX): return 1
    for c in codes:
        if c in T2_JEL or c.startswith(T2_JEL_PREFIX): return 2
    return 3

def geo_tier(locs):
    best = 4
    for country, state, city in locs:
        if country == 'UNITED STATES':
            best = min(best, 1 if state in NE_WEST else 2)
        elif country == 'CANADA': best = min(best, 2)
        elif country in EUROPE:   best = min(best, 3)
        else:                     best = min(best, 4)
    return best

rows = []
for p in ET.parse('joe_full.xml').getroot().findall('.//position'):
    g = lambda k: (p.findtext(k) or '').strip()
    codes = [(j.findtext('jc_code') or '').strip() for j in p.findall('.//jel_class')]
    codes = [c for c in codes if c]
    locs = [((l.findtext('country') or '').strip(), (l.findtext('state') or '').strip(),
             (l.findtext('city') or '').strip()) for l in p.findall('.//location')]
    raw = g('jp_application_deadline')[:10]
    try: dl = datetime.date.fromisoformat(raw)
    except ValueError: dl = None
    sec = g('jp_section'); srank, slabel = SEC_RANK.get(sec, (6, sec))
    inst = g('jp_institution')
    if srank in (3,4):
        slabel = 'Policy/Gov' if POLICY.search(inst) else 'Private sector'
        srank = 3 if slabel == 'Policy/Gov' else 4
    rows.append(dict(
        id=p.get('jp_id'), inst=inst, title=g('jp_title'), section=slabel, srank=srank,
        deadline=raw or '', days=(dl - TODAY).days if dl else None,
        jel=';'.join(codes), jtier=jel_tier(codes),
        # A listing with a country but no city or state used to render as a bare "; ".
        # Drop the empty pieces, then fall back to the country name.
        loc=('; '.join(dict.fromkeys(p for p in (f"{c}, {s}".strip(', ') for _, s, c in locs) if p))
             or '; '.join(dict.fromkeys(a for a, _, _ in locs if a))),
        country=locs[0][0] if locs else '', state=locs[0][1] if locs else '',
        gtier=geo_tier(locs),
        salary=g('jp_salary_range'),
    ))

for r in rows:
    r['score'] = r['jtier']*100 + r['gtier']*10 + r['srank']

rows.sort(key=lambda r: (r['score'], r['days'] if r['days'] is not None else 999))
json.dump(rows, open('rows.json','w'), indent=1)

core = [r for r in rows if r['jtier'] == 1]
print(f"TOTAL {len(rows)} | Tier-1 JEL match (J / N / 00): {len(core)}")
print(f"  of those, geo Tier 1: {sum(1 for r in core if r['gtier']==1)}, Tier 2: {sum(1 for r in core if r['gtier']==2)}")
print()
print("=== DEADLINES WITHIN 45 DAYS, TIER-1 FIELD MATCH ===")
for r in core:
    if r['days'] is not None and 0 <= r['days'] <= 45:
        print(f"  {r['deadline']}  ({r['days']:>2}d)  G{r['gtier']} {r['section']:<16} {r['inst'][:42]:<42} | {r['title'][:46]}")
print()
past = [r for r in rows if r['days'] is not None and r['days'] < 0]
print(f"=== ALREADY PAST DEADLINE: {len(past)} ===")
for r in past: print(f"  {r['deadline']}  {r['inst'][:45]} | {r['title'][:45]}")
