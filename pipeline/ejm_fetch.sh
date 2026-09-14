#!/bin/sh
# Fetch every EconJobMarket listings page. Public, no login, 50 per page; a page past
# the end comes back with no listing anchors, which is the stop condition.
# robots.txt allows everything (checked 2026-09-14).
set -e
BASE=https://econjobmarket.org
UA="job-market-tracker (+https://github.com/onoratod/job-market-tracker)"

rm -f ejm_p*.html
p=1
while [ "$p" -le 40 ]; do
  curl -sS --max-time 60 -A "$UA" -o "ejm_p$p.html" "$BASE/positions?page=$p"
  n=$(grep -c '<a name="position' "ejm_p$p.html" 2>/dev/null || true)
  n=${n:-0}
  if [ "$n" -eq 0 ]; then
    rm -f "ejm_p$p.html"
    break
  fi
  p=$((p + 1))
  sleep 1
done

pages=$((p - 1))
if [ "$pages" -eq 0 ]; then
  echo "FATAL ejm_fetch.sh: no listings on the first page - the site changed or is down"
  exit 1
fi
total=$(cat ejm_p*.html | grep -c '<a name="position' || true)
echo "ejm_fetch.sh: $pages page(s), $total listings"
