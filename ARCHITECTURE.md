# How this works

Four pieces, each with one job.

| Piece | Job |
|---|---|
| This repository | Source of truth: pipeline scripts, the generated page, and `state/joe_snapshot.json` — yesterday's memory of the board |
| GitHub Actions | The clock and the machine. Runs the pipeline daily and commits the result |
| GitHub Pages | The web server. Serves `index.html` at the repository's Pages URL |
| Each viewer's browser | That viewer's stars, applications, notes and ranking preferences — and nobody else's |

## Layout

```
index.html                     the page Pages serves (generated — do not hand-edit)
state/joe_snapshot.json        one entry per listing: fingerprint, first_seen, posted, deadline
pipeline/
  fetch.sh                     JOE full XML + every listings page
  posted.py                    JOE_ID -> posting date
  score.py                     parse XML, assign field / geography / track tiers
  classify.py                  discipline and rank screens
  merge.py                     join, fingerprint, carry first_seen forward
  dash2.py                     render page_template.html into the finished page
  page_template.html           the page itself: markup, styling and all browser logic
.github/workflows/refresh.yml  the daily job
```

## The daily cycle

1. GitHub starts a fresh runner at 11:00 UTC and checks out the repository.
2. `state/joe_snapshot.json` is copied in as `pipeline/prior_snapshot.json` — yesterday's memory.
3. `fetch.sh` loads the JOE listings page, extracts the site's **own** query token, and downloads the
   full XML plus every listings page. Both are needed: the XML carries the content, and only the
   listings pages carry posting dates. A hand-built query token returns HTTP 500.
4. `posted.py` maps each listing to its posting date and **exits non-zero if it cannot date 95% of
   them** — that means JOE changed its markup, and a half-dated feed would mis-sort a page that opens
   newest-first.
5. `score.py`, `classify.py`, `merge.py` parse, screen, join and fingerprint.
6. `dash2.py` renders the page.
7. A guard aborts the run if the board came back with under 80% of yesterday's listings.
8. `index.html` and the snapshot are committed **only if they changed**, then pushed.
9. Pages sees the push and redeploys, usually within a minute.

## How "new" is known

Each listing gets a fingerprint: a hash of title, institution, deadline, section, JEL codes, location,
salary and text length. Days-remaining is deliberately excluded, so the passage of time never looks
like a change. Each run compares against the committed snapshot — an unknown id is new, a changed
fingerprint is an edit, an id missing from JOE has been withdrawn. Because the snapshot is committed
every day, the repository's history doubles as a record of how the board moved all season.

`first_seen` (when this pipeline first saw a listing) and `posted` (the date JOE published it) are
different things and must not be substituted for one another. Only `posted` is shown to viewers.

## Privacy model

Nobody's personal data is in this repository or in the published page. The page ships with an empty
`picks` object; every viewer's stars, application stages, notes and preferences are written to their
own browser's local storage, and never leave it. That is also why one file ranks differently for each
person: the fit score is computed in the browser against whatever preferences that viewer set.

Consequences worth knowing: clearing site data or switching machines starts a viewer from nothing, so
the page has a **Back up or restore** panel; and nothing outside the browser can read a viewer's list,
including whoever maintains this repository.

Never commit a backup file. `.gitignore` covers the usual names, but the rule matters more than the
list: one pasted backup makes one person's shortlist public.

## Failure modes

Every guard fails the same way — don't commit. The URL keeps serving the last good page, and GitHub
emails the repository owner when a scheduled run fails. A stale page announces itself: the header
shows the date of the pull it was built from.

## Operational notes

- **Daylight saving.** The cron is UTC. `0 11 * * *` is 07:00 in New York under EDT and 06:00 once EST
  begins on 2 November 2026. Change it to `0 12 * * *` then.
- **Paused schedules.** GitHub pauses scheduled workflows in repositories that go quiet for a long
  stretch. If refreshes stop, check the Actions tab before assuming something broke.
- **Running it by hand.** Actions tab -> "Refresh JOE listings" -> Run workflow.

## Changing the page

All markup, styling and browser logic live in `pipeline/page_template.html`. `dash2.py` renders it
twice from one `__MODE__` placeholder: `shared` (what gets published) and `personal` (an older edition
whose state lived in the page — kept only as a fallback, and only built when a `prior_picks.json` is
present). One template means a change reaches both and they cannot drift apart.

To work on it locally, from `pipeline/`:

```
sh fetch.sh && python3 posted.py && python3 score.py && python3 classify.py \
  && python3 merge.py && python3 dash2.py
open site/index.html
```

Commit `index.html` along with the template change, or the published page stays on the old render
until the next scheduled run.
