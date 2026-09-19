#!/usr/bin/env bash
# Serve Resume Factory on the tailnet.
#
# Works out this machine's Tailscale name, exports it so the compiled frontend points
# at an address other devices can reach, and keeps the Mac awake for as long as the
# server runs. Without RF_PUBLIC_HOST the frontend is built against localhost and is
# usable only from this machine.
set -euo pipefail
cd "$(dirname "$0")"

TS=""
for candidate in /usr/local/bin/tailscale /opt/homebrew/bin/tailscale \
                 "/Applications/Tailscale.app/Contents/MacOS/Tailscale" "$(command -v tailscale || true)"; do
  [ -x "$candidate" ] && { TS="$candidate"; break; }
done

if [ -n "$TS" ]; then
  # DNSName comes back fully qualified with a trailing dot.
  HOST="$("$TS" status --json 2>/dev/null \
    | python3 -c 'import json,sys; print(json.load(sys.stdin)["Self"]["DNSName"].rstrip("."))' 2>/dev/null || true)"
  [ -z "$HOST" ] && HOST="$("$TS" ip -4 2>/dev/null | head -1 || true)"
fi

if [ -z "${HOST:-}" ]; then
  echo "Tailscale not found or not running; serving on localhost only."
  echo "Start Tailscale and re-run to reach this from other devices."
  HOST="localhost"
fi

export RF_PUBLIC_HOST="$HOST"
echo "Resume Factory"
echo "  open:    http://$HOST:3210"
echo "  backend: http://$HOST:8210"
[ "$HOST" != "localhost" ] && echo "  reachable from any device signed in to your tailnet"
echo

# The app is useless if the Mac sleeps; -i keeps it awake without keeping the display on.
CAFFEINATE=""
command -v caffeinate >/dev/null && CAFFEINATE="caffeinate -i"

if [ -d .venv ]; then
  exec $CAFFEINATE .venv/bin/reflex run --env prod
fi
exec $CAFFEINATE uv run reflex run --env prod
