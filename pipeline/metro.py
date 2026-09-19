"""Is this job in or near a major metropolitan area?

Reads metros.txt, which is a hand-kept judgement list rather than a dataset — see the
comments at the top of that file. This module only does the matching.

The boards do not agree on how they give a location. EconJobMarket gives a city field.
JOE gives one string, "Cambridge, Massachusetts", and sometimes several separated by
semicolons when an employer is hiring into more than one office. A multi-location ad
counts as a metro listing if ANY of its locations is one, which is the answer a reader
wants: the job is available in a big city, whatever else it is also available in.
"""
import os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))


def _key(s):
    """Fold to something two spellings of the same city both land on."""
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9 ]', '', s.lower()).strip()


def _load(path=None):
    """{country key: {city key: metro name}} — first listing of a city wins."""
    table = {}
    with open(path or os.path.join(HERE, 'metros.txt'), encoding='utf-8') as fh:
        for raw in fh:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue
            parts = [p.strip() for p in line.split('|')]
            if len(parts) != 3:
                raise ValueError(f'metros.txt: expected "COUNTRY | Metro | cities", got: {raw!r}')
            country, metro, cities = parts
            bucket = table.setdefault(_key(country), {})
            for city in cities.split(';'):
                k = _key(city)
                if k:
                    bucket.setdefault(k, metro)
    return table


METROS = _load()


def cities_in(loc, city=''):
    """Every city named by a listing's location, best effort.

    A board's own city field is trusted when it has one. Otherwise the location string
    is split on semicolons and the part before the last comma is taken as the city:
    "Cambridge, Massachusetts" -> Cambridge, "Washington, D.C., District of Columbia"
    -> "Washington, D.C.". A bare state with no comma yields nothing, which is correct —
    "California" does not tell us whether the job is in Los Angeles or Davis.
    """
    if city:
        return [city]
    out = []
    for piece in str(loc or '').split(';'):
        piece = piece.strip()
        if ',' not in piece:
            continue
        out.append(piece.rsplit(',', 1)[0].strip())
    return out


def metro_of(loc, country, city=''):
    """The metro this listing sits in, or '' — the first one found among its locations."""
    bucket = METROS.get(_key(country))
    if not bucket:
        return ''
    for c in cities_in(loc, city):
        hit = bucket.get(_key(c))
        if hit:
            return hit
    return ''


if __name__ == '__main__':          # sanity check: python3 metro.py
    cases = [('Cambridge, Massachusetts', 'UNITED STATES', '', 'Boston'),
             ('Evanston, Illinois', 'UNITED STATES', '', 'Chicago'),
             ('Palo Alto, California', 'UNITED STATES', '', 'San Francisco Bay Area'),
             ('Ithaca, New York', 'UNITED STATES', '', ''),
             ('Ann Arbor, Michigan', 'UNITED STATES', '', 'Detroit'),
             ('California', 'UNITED STATES', '', ''),
             ('Palo Alto, California; Heidelberg, Baden-Württemberg', 'UNITED STATES', '',
              'San Francisco Bay Area'),
             ('', 'CANADA', 'Burnaby', 'Vancouver'),
             ('', 'UNITED KINGDOM', 'Cambridge', '')]   # not Boston: wrong country
    bad = 0
    for loc, cc, city, want in cases:
        got = metro_of(loc, cc, city)
        flag = 'ok ' if got == want else 'BAD'
        bad += got != want
        print(f'{flag} {loc or city!r:52} -> {got!r:26} (want {want!r})')
    print(f'{len(METROS)} countries, '
          f'{sum(len(v) for v in METROS.values())} cities, {bad} failure(s)')
    raise SystemExit(1 if bad else 0)
