import xml.etree.ElementTree as ET, html, re, json, collections

def clean(v):
    v = html.unescape(html.unescape(v or ''))
    return re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', v)).strip()

# judged on DIVISION + DEPARTMENT + TITLE only -- institution and keyword fields are too noisy
CORE_ECON = re.compile(r'econom|agribusiness|agricultural and applied', re.I)
ADJACENT  = re.compile(r'public policy|public affairs|policy school|policy analysis|'
                       r'\bfinance\b|financial|health polic|labor|industrial relations|'
                       r'business analytics|statistic|data science|management science|'
                       r'decision science|operations research|international affairs|'
                       r'political economy|business school|school of business|\bbusiness\b', re.I)
NONECON   = re.compile(r'communication|marketing|accountanc|accounting|\bnursing\b|social work|'
                       r'anthropolog|organizational behav|human resource|supply chain|hospitality|'
                       r'criminal justice|information systems|philosoph|theolog|religio|'
                       r'engineering|architecture|kinesiolog|journalis|\benglish\b|linguistic|'
                       r'korean studies|western civilization|school of law|'
                       r'literature|classics|\bmusic\b|\bart history\b', re.I)

SENIOR = re.compile(r'\bfull professor\b|professor \(full\)|chair professor|distinguished professor|'
                    r'\bendowed\b|\bassociate professor\b|associate/full|advanced associate|'
                    r'^director\b|director of|\bdean\b|\bhead of\b|senior lecturer|\breader\b', re.I)
JUNIOR = re.compile(r'assistant professor|\bassistant\b|open rank|tenure[- ]track|entry[- ]level|junior', re.I)
NONACAD_SENIOR = re.compile(r'\bsenior\b|\blead\b|\bprincipal\b|\bchief\b|\bdirector\b|\bhead\b|\badvisor\b', re.I)

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
    if CORE_ECON.search(unit):   disc = 'Econ'
    elif NONECON.search(unit):   disc = 'Non-econ'
    elif ADJACENT.search(unit):  disc = 'Adjacent'
    elif nonacad:                disc = 'Adjacent'      # employer-level econ roles w/ no dept field
    else:                        disc = 'Check'

    if sec in ACADEMIC_TT:
        if JUNIOR.search(title):    rank = 'Eligible'
        elif SENIOR.search(title):  rank = 'Senior only'
        elif re.search(r'\bprofessor\b', title, re.I): rank = 'Check rank'
        else:                       rank = 'Eligible'
    elif sec in TEMP:               rank = 'Eligible'
    else:
        rank = 'Check rank' if NONACAD_SENIOR.search(title) else 'Eligible'

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
