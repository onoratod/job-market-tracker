"""Loading the previous run's snapshot, in one place.

Ids were bare before a second board existed. Every reader has to migrate them the same
way or the two disagree about what is new — which is how a routine morning turns into a
briefing claiming the entire board changed overnight.
"""
import json, os


def load_prior(path='prior_snapshot.json'):
    """Returns {namespaced_id: entry}. Empty dict when there is no previous run."""
    if not os.path.exists(path):
        return {}
    blob = json.load(open(path))
    prior = blob.get('listings', blob)
    if prior and not any(':' in k for k in prior):
        prior = {('joe:' + k): v for k, v in prior.items()}
    return prior


def sources_in(snapshot):
    """Which boards the snapshot already knows about."""
    out = set()
    for k, v in snapshot.items():
        out.add(v.get('src') or (k.split(':', 1)[0] if ':' in k else 'joe'))
    return out
