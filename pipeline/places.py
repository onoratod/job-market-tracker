"""The geography picker, built from the day's feed.

The alternative was a hardcoded list of populous countries, and it would have been
wrong here: this feed is mostly China, Hong Kong, Taiwan, Japan and Singapore, while a
population-ranked Asia list leads with India, Indonesia and Pakistan — which is where
people live, not where economics departments advertise. So the picker lists the
countries that actually have listings, with their counts, and it changes as the feed
changes.

Counts are what make it usable: "Germany 10" tells a reader something, "Germany" does
not. The page adds back any country the VIEWER has ticked even when today's count is
zero, so a preference set in September still means something in November.
"""
import collections

# Continents, in the order the picker shows them. "Habitable" in the sense the user
# meant: Antarctica is not here, and the Middle East is split out from Asia because
# people think of it separately when they think about where they would move.
CONTINENTS = [
    ('na', 'North America'),
    ('eu', 'Europe'),
    ('as', 'Asia & Pacific'),
    ('me', 'Middle East & Africa'),
    ('sa', 'Latin America'),
    ('xx', 'Elsewhere'),
]

CONTINENT_OF = {}
def _put(key, *countries):
    for c in countries:
        CONTINENT_OF[c] = key

_put('na', 'UNITED STATES', 'CANADA', 'MEXICO', 'BERMUDA', 'PUERTO RICO')
_put('eu', 'UNITED KINGDOM', 'IRELAND', 'FRANCE', 'GERMANY', 'ITALY', 'SPAIN', 'PORTUGAL',
     'NETHERLANDS', 'BELGIUM', 'LUXEMBOURG', 'SWITZERLAND', 'AUSTRIA', 'SWEDEN', 'NORWAY',
     'DENMARK', 'FINLAND', 'ICELAND', 'POLAND', 'CZECH REPUBLIC', 'CZECHIA', 'SLOVAKIA',
     'HUNGARY', 'ROMANIA', 'BULGARIA', 'GREECE', 'CROATIA', 'SLOVENIA', 'SERBIA', 'ESTONIA',
     'LATVIA', 'LITHUANIA', 'CYPRUS', 'MALTA', 'UKRAINE', 'RUSSIA', 'RUSSIAN FEDERATION')
_put('as', 'CHINA', 'HONG KONG', 'MACAU', 'TAIWAN', 'JAPAN', 'KOREA, REPUBLIC OF', 'SOUTH KOREA',
     'MACAO', 'SINGAPORE', 'MALAYSIA', 'THAILAND', 'VIETNAM', 'INDONESIA', 'PHILIPPINES', 'INDIA',
     'PAKISTAN', 'BANGLADESH', 'SRI LANKA', 'NEPAL', 'AUSTRALIA', 'NEW ZEALAND', 'FIJI',
     'KAZAKHSTAN', 'MONGOLIA')
_put('me', 'ISRAEL', 'TURKEY', 'TÜRKIYE', 'UNITED ARAB EMIRATES', 'SAUDI ARABIA', 'QATAR',
     'KUWAIT', 'BAHRAIN', 'OMAN', 'JORDAN', 'LEBANON', 'EGYPT', 'MOROCCO', 'TUNISIA', 'ALGERIA',
     'SOUTH AFRICA', 'NIGERIA', 'KENYA', 'GHANA', 'ETHIOPIA', 'TANZANIA', 'UGANDA', 'RWANDA',
     'SENEGAL', 'BOTSWANA', 'ZAMBIA', 'ZIMBABWE', 'NAMIBIA')
_put('sa', 'BRAZIL', 'ARGENTINA', 'CHILE', 'COLOMBIA', 'PERU', 'URUGUAY', 'ECUADOR', 'BOLIVIA',
     'PARAGUAY', 'VENEZUELA', 'COSTA RICA', 'PANAMA', 'GUATEMALA', 'JAMAICA',
     'TRINIDAD AND TOBAGO', 'DOMINICAN REPUBLIC')

# US regions. The page used to carry its own copy of this; it now reads this one, so the
# region a listing falls into cannot differ between the ranking and the picker.
US_REGIONS = [
    ('ne', 'Northeast', ['New York', 'New Jersey', 'Pennsylvania', 'Massachusetts',
                         'Connecticut', 'Rhode Island', 'New Hampshire', 'Vermont', 'Maine']),
    ('dc', 'DC & Mid-Atlantic', ['District of Columbia', 'Maryland', 'Virginia', 'Delaware',
                                 'West Virginia']),
    ('mw', 'Midwest', ['Illinois', 'Michigan', 'Ohio', 'Wisconsin', 'Minnesota', 'Indiana',
                       'Iowa', 'Missouri', 'Kansas', 'Nebraska', 'North Dakota', 'South Dakota']),
    ('so', 'South', ['Florida', 'Georgia', 'North Carolina', 'South Carolina', 'Tennessee',
                     'Alabama', 'Mississippi', 'Louisiana', 'Texas', 'Oklahoma', 'Arkansas',
                     'Kentucky']),
    ('mt', 'Mountain & Southwest', ['Colorado', 'Utah', 'Arizona', 'New Mexico', 'Nevada',
                                    'Idaho', 'Montana', 'Wyoming']),
    ('we', 'West Coast', ['California', 'Washington', 'Oregon', 'Hawaii', 'Alaska']),
]

SMALL = {'and', 'of', 'the', 'de', 'and the'}


def pretty(country):
    """'UNITED STATES' -> 'United States'. Boards shout their country names."""
    if country in ('UNITED STATES', 'USA'):
        return 'United States'
    if country in ('UNITED KINGDOM', 'UK'):
        return 'United Kingdom'
    words = []
    for i, w in enumerate(country.split()):
        lw = w.lower()
        words.append(lw if (i and lw in SMALL) else lw.capitalize())
    return ' '.join(words)


def continent_of(country):
    return CONTINENT_OF.get((country or '').strip().upper(), 'xx')


def places(rows):
    """Continent -> country -> (for the US) region -> state, each with today's count.

    `rows` are packed page rows: they carry cc (country) and st (state).
    """
    region_of_state = {st: key for key, _lab, states in US_REGIONS for st in states}

    by_country = collections.Counter()
    by_state = collections.Counter()
    for d in rows:
        cc = (d.get('cc') or '').strip().upper()
        if not cc:
            continue                     # remote, or a board that gave us nothing
        by_country[cc] += 1
        if cc == 'UNITED STATES' and d.get('st'):
            by_state[d['st']] += 1

    out = []
    for key, label in CONTINENTS:
        countries = []
        for cc, n in by_country.items():
            if continent_of(cc) != key:
                continue
            entry = {'cc': cc, 'name': pretty(cc), 'n': n}
            if cc == 'UNITED STATES':
                regions = []
                for rkey, rlabel, states in US_REGIONS:
                    picked = [{'st': s, 'n': by_state[s]} for s in states if by_state[s]]
                    # Every state stays listed even at zero, because a region you can
                    # only half-open reads like a bug. The count is the honest part.
                    allst = [{'st': s, 'n': by_state.get(s, 0)} for s in states]
                    regions.append({'key': rkey, 'name': rlabel,
                                    'n': sum(x['n'] for x in picked), 'states': allst})
                entry['regions'] = regions
            countries.append(entry)
        if not countries:
            continue
        countries.sort(key=lambda c: (-c['n'], c['name']))
        out.append({'key': key, 'name': label,
                    'n': sum(c['n'] for c in countries), 'countries': countries})
    return {'continents': out, 'regions': [[k, l] for k, l, _ in US_REGIONS],
            'stateRegion': region_of_state}
