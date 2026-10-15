#!/bin/bash
# smoke.sh FILE.rvt : headless demo check (no browser). 1) standalone server: page, status, doc.json, cache.json, first sheet SVG;
# 2) the viewer demo command with --no-browser: main page, /sheets/ page, the sheets API under the viewer's model id. Exit 0 = OK.
f=$(readlink -f "$1"); here=$(dirname "$(readlink -f "$0")")/..; fail=0; tmp=$(mktemp -d)
ok() { echo "  ok   $*"; }; bad() { echo "  FAIL $*"; fail=1; }
wait_ready() { for i in $(seq 1 600); do s=$(curl -s "$1/status"); case $s in *'"ready"'*) return 0;; *'"error"'*) echo "$s"; return 1;; esac; sleep 1; done; return 1; }
check() { # base mid
  code=$(curl -s -o "$tmp/p.html" -w '%{http_code}' "$1/"); [ "$code" = 200 ] && grep -q rvt-sheets "$tmp/p.html" && ok "page /sheets/" || bad "page /sheets/ ($code)"
  wait_ready "$1/api/$2" && ok "model ready" || bad "model not ready"
  curl -s "$1/api/$2/doc.json" > "$tmp/doc.json"; python3 -c "import json,sys; d=json.load(open('$tmp/doc.json')); print('  ok   doc.json: %d sheets, %d views' % (len(d['sheets']), len(d['views'])))" || bad doc.json
  curl -s "$1/api/$2/cache.json" | python3 -c "
import json,sys; d=json.load(sys.stdin); print('  ok   cache.json', d)
sys.exit(1 if d.get('failed') else 0)" || bad "cache.json (failed drawings reported by warm)"
  sid=$(python3 -c "import json; d=json.load(open('$tmp/doc.json')); x=(d['sheets'] or d['views'])[0]; print(('sheet/' if d['sheets'] else 'view/')+str(x['id']))")
  if [ "${sid%%/*}" = sheet ]; then pc=$(curl -s -o "$tmp/s.pdf" -w '%{http_code} %{time_total}s' "$1/api/$2/${sid}.pdf"); head -c 5 "$tmp/s.pdf" | grep -q '%PDF' && ok "${sid}.pdf $pc" || bad "${sid}.pdf $pc"; fi
  t=$(curl -s -o "$tmp/s.svg" -w '%{http_code} %{time_total}s' -D "$tmp/h" "$1/api/$2/$sid.svg"); grep -q '<svg' "$tmp/s.svg" && ! grep -q 'could not draw' "$tmp/s.svg" && ok "$sid.svg $t $(grep -i x-rvt-cache "$tmp/h" | tr -d '\r')" || bad "$sid.svg $t"
}
port=$((20000 + RANDOM % 20000))
echo "standalone (port $port)"
"$here/rvt-sheets" serve "$f" --port $port > "$tmp/s.log" 2>&1 & pid=$!
sleep 2; check "http://127.0.0.1:$port/sheets" local; kill $pid; wait $pid 2>/dev/null
port=$((port + 1))
echo "viewer demo command (--sheets --no-browser, port $port)"
~/src/rvt-viewer/bin/rvt-view "$f" --sheets --no-browser --port $port > "$tmp/v.log" 2>&1 & pid=$!
for i in $(seq 1 120); do grep -q serving "$tmp/v.log" && break; sleep 1; done
url=$(grep -o 'http://[^ ]*' "$tmp/v.log" | head -1); mid=${url##*#}
code=$(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:$port/"); [ "$code" = 200 ] && ok "viewer main page" || bad "viewer main page ($code)"
check "http://127.0.0.1:$port/sheets" "$mid"
kill $pid; wait $pid 2>/dev/null
[ $fail = 0 ] && echo "SMOKE OK" || { echo "SMOKE FAILED (logs in $tmp)"; exit 1; }
