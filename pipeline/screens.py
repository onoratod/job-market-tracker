"""Screens and classifications shared by every job board.

These rules decide what counts as economics, what is above assistant level, and which
employers are policy rather than private sector. They live here so that adding a board
cannot quietly give it different rules from the others — the failure mode that matters
is a listing screened out on one board and kept on another for no reason anybody can see.

Judged on department + division + title only. Institution names and keyword fields are
too noisy: half the ads say "economics" somewhere.
"""
import re

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

# Employers whose "nonacademic" roles are policy work rather than private sector.
POLICY = re.compile(r'federal reserve|council of economic|congressional budget|international monetary|'
                    r'world bank|treasury|bureau of labor|census|inter-american|oecd|'
                    r'brookings|urban institute|rand|mathematica|abdul latif|center for global development|'
                    r'national bureau|department of|ministry|commission|bank of [a-z]+|'
                    r'european central bank|statistics (canada|norway|sweden|denmark)', re.I)

# Ranked best-first. A listing advertising several position types takes the first match:
# an ad open to assistant AND full professor is a tenure-track ad from a candidate's side.
TRACK_ORDER = ['Academic TT', 'Lecturer', 'Postdoc/Visiting', 'Policy/Gov',
               'Private sector', 'Nonacademic other', 'Adjunct']


def discipline_of(unit_text, nonacademic=False):
    """Econ / Adjacent / Non-econ / Check, from department + division + title."""
    if CORE_ECON.search(unit_text):  return 'Econ'
    if NONECON.search(unit_text):    return 'Non-econ'
    if ADJACENT.search(unit_text):   return 'Adjacent'
    if nonacademic:                  return 'Adjacent'   # employer-level econ roles with no department
    return 'Check'


def rank_of(title, kind):
    """Eligible / Senior only / Check rank.

    `kind` is 'tt' for tenure-track academic, 'temp' for visiting and postdoctoral,
    anything else for nonacademic.
    """
    if kind == 'tt':
        if JUNIOR.search(title):                       return 'Eligible'
        if SENIOR.search(title):                       return 'Senior only'
        if re.search(r'\bprofessor\b', title, re.I):   return 'Check rank'
        return 'Eligible'
    if kind == 'temp':
        return 'Eligible'
    return 'Check rank' if NONACAD_SENIOR.search(title) else 'Eligible'


def track_rank(track):
    """Lower is better — drives the third component of the fit score."""
    try:
        return TRACK_ORDER.index(track) + 1
    except ValueError:
        return len(TRACK_ORDER) + 1


# --- the owner's default tiers -------------------------------------------------
# Used for server-side ordering, the digest, and the header counts. Every VIEWER
# scores listings themselves in the browser from their own preferences; these are
# only the defaults the pipeline sorts by. Shared so a second board cannot tier
# differently from the first.

T1_JEL_PREFIX = ('J', 'N')
T1_JEL_EXACT  = {'00'}
T2_JEL        = {'I1', 'I2', 'I3', 'D1', 'R1', 'R2', 'K4', 'O1'}   # Danny's spec, unchanged
T2_JEL_PREFIX = ('H',)

NE_WEST = {'New York', 'New Jersey', 'Pennsylvania', 'District of Columbia', 'Maryland',
           'Virginia', 'Massachusetts', 'Connecticut', 'Rhode Island', 'Delaware',
           'New Hampshire', 'California', 'Washington', 'Oregon'}
EUROPE = {'UNITED KINGDOM', 'GERMANY', 'FRANCE', 'ITALY', 'SPAIN', 'NETHERLANDS', 'SWITZERLAND',
          'SWEDEN', 'NORWAY', 'DENMARK', 'FINLAND', 'BELGIUM', 'AUSTRIA', 'IRELAND', 'PORTUGAL',
          'POLAND', 'CZECH REPUBLIC', 'GREECE', 'HUNGARY', 'LUXEMBOURG'}


def jel_tier(codes):
    """JOE gives two-character codes (J1, I2); boards without JEL give bare letters.
    A bare letter matches tier 2 when any tier-2 code starts with it, so 'I' from
    another board tiers like I1/I2/I3 without loosening what a JOE code means."""
    for c in codes:
        if c in T1_JEL_EXACT or c.startswith(T1_JEL_PREFIX): return 1
    for c in codes:
        if c in T2_JEL or c.startswith(T2_JEL_PREFIX): return 2
        if len(c) == 1 and any(t.startswith(c) for t in T2_JEL): return 2
    return 3


def geo_tier(locs):
    """locs: list of (country, state, city), country upper-cased as the boards give it."""
    best = 4
    for country, state, _city in locs:
        if country == 'UNITED STATES':  best = min(best, 1 if state in NE_WEST else 2)
        elif country == 'CANADA':       best = min(best, 2)
        elif country in EUROPE:         best = min(best, 3)
        else:                           best = min(best, 4)
    return best
