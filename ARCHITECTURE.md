# How this works

Four pieces, each with one job.

| Piece | Job |
|---|---|
| This repository | Source of truth: pipeline scripts, the generated page, and `state/joe_snapshot.json` — yesterday's memory of the boards |
| GitHub Actions | The clock and the machine. Runs the pipeline daily and commits the result |
| GitHub Pages | The web server. Serves `index.html` at the repository's Pages URL |
| Each viewer's browser | That viewer's stars, applications, notes and ranking preferences — and nobody else's |

The page has five tabs: Applications, Shortlist, All listings, Preferences and Backup. There
is no "Screened out" tab, because nothing is screened out any more — see below.

## Layout

```
index.html                     the page Pages serves (generated — do not hand-edit)
state/joe_snapshot.json        one entry per listing: fingerprint, first_seen, posted, deadline, src
state/digest.json              what changed on the last run: new, changed, withdrawn
pipeline/
  screens.py                   shared by every board: what reads as economics, what is above
                               assistant level, which employers are policy, the owner's default tiers
  snapshot.py                  reads the prior snapshot and migrates pre-namespace ids
  places.py                    the geography picker, built from the day's own listings
  metro.py + metros.txt        is this job in or near a major metro — an editable judgement list
  fetch.sh                     JOE full XML + every listings page
  posted.py                    JOE_ID -> posting date
  score.py                     parse JOE XML, assign field / geography / track tiers -> joe_rows.json
  classify.py                  discipline and rank screens for JOE -> flags.json
  ejm_fetch.sh                 every EconJobMarket listings page
  ejm_parse.py                 parse those pages (+ detail pages for location) -> ejm_rows.json
  merge.py                     join every board, namespace ids, fingerprint, carry first_seen forward
  digest.py                    diff against yesterday's snapshot -> digest.json
  dash2.py                     render page_template.html into the finished page
  page_template.html           the page itself: markup, styling and all browser logic
.github/workflows/refresh.yml  the daily job
```

## The boards

| Source | id prefix | Where the dates come from |
|---|---|---|
| AEA JOE | `joe:` | Deadline from the XML; **posting date only from the paginated listings pages** |
| EconJobMarket | `ejm:` | All three dates on the listing itself, told apart by CSS class: `bg-info` posted, `negative` deadline, grey expiry |

Ids are namespaced because the two boards number their listings independently, and a collision
would silently attach somebody's star to the wrong job. Stars saved before namespacing existed
carry bare ids; `snapshot.py` and the page both read those as JOE.

A job advertised on both boards is kept twice, deliberately. Seeing a job twice costs a few
seconds; hiding one costs a job.

## The contract a board must meet

Adding board #3 means writing one fetch script and one parse script. Nothing else in the pipeline
should need to change. The parse script writes `<board>_rows.json`: a list of objects carrying at
minimum

```
id  src  inst  unit  title  section  srank  deadline  days  posted  jel  jtier
loc  country  state  city  gtier  salary  discipline  rank_fit  adlen  url
```

and four rules:

1. **Use `screens.py`.** Discipline, rank and the owner's default tiers come from there, never from
   a board's own copy. The failure that matters is a listing screened out on one board and kept on
   another for no reason anybody can see.
2. **`posted` is the board's publication date.** Never `first_seen`, which is when *we* first saw
   it. Only `posted` is shown to viewers, and conflating the two makes a six-week-old job look new.
3. **All or nothing.** Write no output file unless the whole parse succeeded. A half-parsed board is
   worse than a missing one, because a missing one announces itself and a half-parsed one does not.
4. **Cheap on reruns.** `ejm_parse.py` fetches a detail page only for listings the prior snapshot
   has never seen — the location it found is cached in the snapshot. A board that re-fetches every
   detail page every day will eventually get itself blocked.

Then add one `continue-on-error: true` step to the workflow, between JOE and the merge. `merge.py`
picks the file up if it is there and says so if it is not.

## The daily cycle

1. GitHub starts a fresh runner at 11:00 UTC and checks out the repository.
2. `state/joe_snapshot.json` is copied in as `pipeline/prior_snapshot.json` — yesterday's memory.
3. `fetch.sh` loads the JOE listings page, extracts the site's **own** query token, and downloads the
   full XML plus every listings page. Both are needed: the XML carries the content, and only the
   listings pages carry posting dates. A hand-built query token returns HTTP 500.
4. `posted.py` maps each listing to its posting date and **exits non-zero if it cannot date 95% of
   them** — that means JOE changed its markup, and a half-dated feed would mis-sort a page that opens
   newest-first.
5. `score.py` and `classify.py` parse and screen JOE.
6. `ejm_fetch.sh` and `ejm_parse.py` do the same for EconJobMarket. **This step is allowed to fail**
   without failing the run.
7. `merge.py` joins whatever boards produced output, namespaces the ids, fingerprints every listing
   and writes the snapshot — including a `sources` block recording each board's count and the last
   date it was seen.
8. `digest.py` diffs the new snapshot against yesterday's and writes `digest.json`.
9. `dash2.py` renders the page, embedding the digest and the sources block.
10. A guard aborts the run if **any board** came back with under 80% of yesterday's listings.
11. `index.html`, the snapshot and the digest are committed **only if they changed**, then pushed.
12. Pages sees the push and redeploys, usually within a minute.

## When a board fails

This is the case worth understanding, because it is the one that will actually happen.

If EconJobMarket is down or changes its markup, `ejm_parse.py` writes nothing, the step is marked
failed but the run continues, and `merge.py` builds from JOE alone. Three things then hold:

- The snapshot's `sources` block records `ejm` with a count of 0 and the date it was last seen, so
  the page can say "EconJobMarket could not be read today — showing the other boards" instead of
  quietly shrinking by a third.
- `digest.py` does **not** report that board's listings as withdrawn. Calling 97 live jobs withdrawn
  would be the most alarming possible way to report a failed fetch.
- The collapse guard is checked per board, so a missing board does not block the others from
  publishing — but a board that returns 37 listings where it returned 97 yesterday does, because
  that is a broken parse rather than news.

Nobody's stars are affected either way: they live in the browser, keyed by id, and reattach when the
board comes back.

## The screens flag; they do not remove

`screens.py` decides whether a listing reads as economics and whether it is advertised above
assistant level. Until September 2026 a listing that failed either test was pulled out of the
feed into a separate tab. It is not any more, and the reason is worth keeping written down:
the screen was wrong often enough to matter — it dropped assistant professorships at Berkeley
as "not economics" — and a listing nobody can see is a listing nobody can correct.

So every listing goes in the one table, carrying a flag:

| flag | means |
|---|---|
| *(none)* | reads as an economics job at a rank you could hold |
| `check` | field or rank is ambiguous — the ad is worth reading |
| `senior` | advertised above assistant level |
| `not-econ` | department and title do not read as economics or econ-adjacent |

`senior` and `not-econ` add 1000 to the fit score, so they lose every tie and sit at the
bottom of a fit-sorted list. They are never filtered, never hidden, and never excluded from
a count. The default sort is newest-posted-first, so in normal use they appear in date order
wearing their label.

## Where I would go

Each viewer's places are stored as three kinds of token: `c:<continent>` for a whole
continent, `k:<COUNTRY>` for one country, `s:<State>` for one US state. US regions
(Northeast, Midwest) tick nine states at once and are never stored themselves, so a region
cannot come to mean something different from the states inside it.

Scoring is: a place you ticked is tier 1; anywhere on a continent where you ticked something
is tier 2; the rest of the world is tier 3. The rule this replaced read "elsewhere in the US"
as tier 2, which made no sense for anyone whose whole list was European.

`places.py` builds the picker from the day's listings with a count beside every country, so
the options are places that actually have jobs. Two consequences: the picker changes as the
feed changes, and a country a viewer ticked is **never** dropped from their saved preferences
just because it has no listing this morning — it is shown separately as "also ticked, nothing
advertised there today". A preference set in September still means something in November.

## How "new" is known

Each listing gets a fingerprint: a hash of title, institution, deadline, section, JEL codes, location,
salary and text length. Days-remaining is deliberately excluded, so the passage of time never looks
like a change. Each run compares against the committed snapshot — an unknown id is new, a changed
fingerprint is an edit, an id missing from a board that *did* report is withdrawn. Because the
snapshot is committed every day, the repository's history doubles as a record of how the boards moved
all season.

The first run of a newly added board is an exception: every one of its listings is unknown, and
itemising 97 of them as "new" is noise. `digest.py` counts that once and names the board instead.

## Since yesterday

`digest.py` turns the snapshot comparison into `state/digest.json`: listings that are new, ones whose
fingerprint moved (naming the field when it is the deadline, title or institution, and saying
"details" honestly when the change was elsewhere), and ones that have left a board. `dash2.py` embeds
it, and the page shows it as a panel at the top of All listings — hidden entirely on a quiet day,
because an empty panel is worse than no panel.

Anything that wants the summary without opening the page — a notifier, a weekly mail — should read
`state/digest.json` from the repository rather than re-deriving it.

## Privacy model

Nobody's personal data is in this repository or in the published page. The page ships with an empty
`picks` object; every viewer's stars, application stages, notes and preferences are written to their
own browser's local storage, and never leave it. That is also why one file ranks differently for each
person: the fit score is computed in the browser against whatever preferences that viewer set. The
tiers in `screens.py` are only the defaults the pipeline sorts by before anyone sets preferences.

Consequences worth knowing: clearing site data or switching machines starts a viewer from nothing, so
the page has a **Back up or restore** panel; and nothing outside the browser can read a viewer's list,
including whoever maintains this repository.

Never commit a backup file. `.gitignore` covers the usual names, but the rule matters more than the
list: one pasted backup makes one person's shortlist public.

## Failure modes

Every guard fails the same way — don't commit. The URL keeps serving the last good page, and GitHub
emails the repository owner when a scheduled run fails. A stale page announces itself: the header
shows the date of the pull it was built from, and which boards it was built from.

## Operational notes

- **Daylight saving.** The cron is UTC. `0 11 * * *` is 07:00 in New York under EDT and 06:00 once EST
  begins on 2 November 2026. Change it to `0 12 * * *` then.
- **Paused schedules.** GitHub pauses scheduled workflows in repositories that go quiet for a long
  stretch. If refreshes stop, check the Actions tab before assuming something broke.
- **Running it by hand.** Actions tab -> "Refresh JOE listings" -> Run workflow.
- **Rebasing.** The Action commits `index.html` and `state/` on its own. Hand commits should touch
  source only, or every `git pull --rebase` fights the runner over a generated file.

## Changing the page

All markup, styling and browser logic live in `pipeline/page_template.html`. `dash2.py` renders it
twice from one `__MODE__` placeholder: `shared` (what gets published) and `personal` (an older edition
whose state lived in the page — kept only as a fallback, and only built when a `prior_picks.json` is
present). One template means a change reaches both and they cannot drift apart.

To work on it locally, from `pipeline/`:

```
sh fetch.sh && python3 posted.py && python3 score.py && python3 classify.py \
  && sh ejm_fetch.sh && python3 ejm_parse.py \
  && python3 merge.py && python3 digest.py && python3 dash2.py
open site/index.html
```

Drop the two `ejm_` lines to rebuild from JOE alone; `merge.py` will say it is building from JOE only.

Commit `index.html` along with the template change, or the published page stays on the old render
until the next scheduled run.
