#!/bin/sh
# Fetch the JOE feed: full XML + every listings page (the pages carry the posting
# dates, which the XML does not). Run from the pipeline working directory.
set -e
BASE=https://www.aeaweb.org
REF=$BASE/joe/listings

curl -s -c cookies.txt -o joe_listings_p1.html "$REF"

# Use the site's OWN q parameter. A hand-built one returns HTTP 500.
Q=$(grep -o "/joe/resultset_output.php?mode=full_xml&q=[^\"' ]*" joe_listings_p1.html | head -1)
[ -n "$Q" ] || { echo "FATAL fetch.sh: no full_xml link on the listings page"; exit 1; }
curl -s -b cookies.txt -e "$REF" -o joe_full.xml "$BASE$Q"
head -c 20 joe_full.xml | grep -q "JOE_EXPORT" || {
  echo "FATAL fetch.sh: full_xml did not return XML (got HTML — session/cookie problem)"; exit 1; }

# Listings pages are 50 per listing-group page; a page past the end has no links.
p=2
while [ "$p" -le 40 ]; do
  curl -s -b cookies.txt -e "$REF" -o "joe_listings_p$p.html" "$BASE/joe/listings?page=$p"
  n=$(grep -c "JOE_ID=" "joe_listings_p$p.html" || true)
  [ "$n" -gt 0 ] || { rm -f "joe_listings_p$p.html"; break; }
  p=$((p + 1))
done

echo "fetch.sh: $(grep -c '<position ' joe_full.xml) positions in XML, $((p - 1)) listings page(s)"
