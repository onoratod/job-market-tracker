import xml.etree.ElementTree as ET, html, re, json, collections
from screens import discipline_of, rank_of   # shared with every other board

def clean(v):
    v = html.unescape(html.unescape(v or ''))
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', v)).strip()

ACADEMIC_TT = ('US: Full-Time Academic (Permanent, Tenure Track or Tenured)',
               'International: Full-Time Academic (Permanent, Tenure Track or Tenured)')
TEMP = ('US: Other Academic (Visiting or Temporary)',
        'International: Other Academic (Visiting or Temporary)')

out = {}
for p in ET.parse('joe_full.xml').getroot().findall('.//position'):
    g = lambda k: clean(p.findtext(k))
    title, sec = g('jp_title'), g('jp_section')
    unit = ' | '.join([g('jp_division'), g('jp_department'), title])
    nonacad = sec not in ACADEMIC_TT + TEMP + ('US: Other Academic (Part-time or Adjunct)',
                                               'International: Other Academic (Part-time or Adjunct)')
    disc = discipline_of(unit, nonacademic=nonacad)
    kind = 'tt' if sec in ACADEMIC_TT else 'temp' if sec in TEMP else 'nonacad'
    rank = rank_of(title, kind)

    out[p.get('jp_id')] = dict(discipline=disc, rank=rank, title=title, sec=sec,
                               inst=g('jp_institution'), unit=(g('jp_department') or g('jp_division')))
json.dump(out, open('flags.json','w'), indent=1)

print('discipline:', dict(collections.Counter(v['discipline'] for v in out.values())))
print('rank      :', dict(collections.Counter(v['rank'] for v in out.values())))
for label, test in [('NON-ECON', lambda v: v['discipline']=='Non-econ'),
                    ('SENIOR ONLY', lambda v: v['rank']=='Senior only'),
                    ('CHECK (discipline unclear)', lambda v: v['discipline']=='Check'),
                    ('CHECK RANK', lambda v: v['rank']=='Check rank')]:
    print(f'\n=== {label} ===')
    for v in out.values():
        if test(v): print(f"  {v['inst'][:32]:<32} | {v['unit'][:26]:<26} | {v['title'][:44]}")
