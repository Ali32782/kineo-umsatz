#!/usr/bin/env bash
# Persistent Disk für kineo-backend auf Render anlegen (einmalig).
# Voraussetzung: RENDER_API_KEY in der Umgebung (Render Dashboard → Account → API Keys)
set -euo pipefail

if [ -z "${RENDER_API_KEY:-}" ]; then
  echo "Fehler: RENDER_API_KEY nicht gesetzt."
  echo "  export RENDER_API_KEY=rnd_..."
  exit 1
fi

API="https://api.render.com/v1"
AUTH="Authorization: Bearer $RENDER_API_KEY"

echo "→ Suche Backend-Service…"
SERVICES=$(curl -sS -H "$AUTH" -H "Accept: application/json" "$API/services?limit=50")
SERVICE_ID=$(echo "$SERVICES" | python3 -c "
import json, sys
data = json.load(sys.stdin)
for item in data:
    s = item.get('service') or item
    name = (s.get('name') or '').lower()
    if 'kineo' in name and 'backend' in name:
        print(s['id'])
        break
else:
  for item in data:
    s = item.get('service') or item
    name = (s.get('name') or '').lower()
    if 'kineo' in name and 'frontend' not in name:
        print(s['id'])
        break
")

if [ -z "$SERVICE_ID" ]; then
  echo "Kein kineo-backend Service gefunden. Bitte serviceId manuell setzen:"
  echo "$SERVICES" | python3 -c "import json,sys; [print((i.get('service')or i).get('name'), (i.get('service')or i).get('id')) for i in json.load(sys.stdin)]"
  exit 1
fi

echo "  Service: $SERVICE_ID"

echo "→ Prüfe vorhandene Disks…"
DISKS=$(curl -sS -H "$AUTH" -H "Accept: application/json" "$API/services/$SERVICE_ID/disks" 2>/dev/null || echo "[]")
HAS_DISK=$(echo "$DISKS" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    data = []
items = data if isinstance(data, list) else data.get('disks', [])
for d in items:
    disk = d.get('disk') or d
    if disk.get('mountPath') == '/app/data':
        print('yes')
        break
" || true)

if [ "$HAS_DISK" = "yes" ]; then
  echo "✓ Disk an /app/data ist bereits vorhanden."
  exit 0
fi

echo "→ Lege Disk an (1 GB, /app/data)…"
curl -sS -X POST -H "$AUTH" -H "Content-Type: application/json" \
  -d "{\"name\":\"kineo-data\",\"sizeGB\":1,\"mountPath\":\"/app/data\",\"serviceId\":\"$SERVICE_ID\"}" \
  "$API/disks"

echo ""
echo "✓ Disk erstellt — Render startet automatisch einen neuen Deploy."
echo "  Prüfe danach in der App: Dashboard → «Gespeicherte Daten» (Juni sollte nach Upload erhalten bleiben)."
