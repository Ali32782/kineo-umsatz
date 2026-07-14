#!/usr/bin/env bash
# Persistent Disk für Kineo auf Render anlegen (einmalig).
# Voraussetzung:
#   - RENDER_API_KEY (Dashboard → Account Settings → API Keys)
#   - Web-Service mindestens Starter (Free hat keine Disks)
set -euo pipefail

if [ -z "${RENDER_API_KEY:-}" ]; then
  echo "Fehler: RENDER_API_KEY nicht gesetzt."
  echo "  1) Render Dashboard → Account Settings → API Keys → Create API Key"
  echo "  2) export RENDER_API_KEY=rnd_..."
  echo "  3) ./scripts/ensure-render-disk.sh"
  exit 1
fi

API="https://api.render.com/v1"
AUTH="Authorization: Bearer $RENDER_API_KEY"
MOUNT_PATH="${DISK_MOUNT_PATH:-/app/data}"
DISK_NAME="${DISK_NAME:-kineo-data}"
DISK_SIZE_GB="${DISK_SIZE_GB:-1}"

echo "→ Suche Kineo-Service…"
SERVICES=$(curl -sS -H "$AUTH" -H "Accept: application/json" "$API/services?limit=50")
SERVICE_ID=$(SERVICE_ID_OVERRIDE="${SERVICE_ID:-}" echo "$SERVICES" | python3 -c "
import json, sys, os
override = os.environ.get('SERVICE_ID_OVERRIDE', '').strip()
data = json.load(sys.stdin)
if override:
    print(override)
    raise SystemExit
items = []
for item in data:
    s = item.get('service') or item
    items.append(s)
    name = (s.get('name') or '').lower()
    stype = (s.get('type') or s.get('serviceType') or '').lower()
    if stype and stype not in ('web_service', 'web', ''):
        continue
    if 'frontend' in name or 'static' in name:
        continue
    if 'kineo' in name and 'backend' in name:
        print(s['id']); raise SystemExit
for s in items:
    name = (s.get('name') or '').lower()
    if 'kineo' in name and 'frontend' not in name and 'static' not in name:
        print(s['id']); raise SystemExit
")

if [ -z "$SERVICE_ID" ]; then
  echo "Kein passender Service gefunden. Verfügbare Services:"
  echo "$SERVICES" | python3 -c "
import json,sys
for i in json.load(sys.stdin):
    s=i.get('service')or i
    print('-', s.get('name'), s.get('id'), s.get('type') or s.get('serviceType'))
"
  echo "Manuell: SERVICE_ID=srv-... ./scripts/ensure-render-disk.sh"
  exit 1
fi

SERVICE_META=$(echo "$SERVICES" | python3 -c "
import json,sys,os
sid=os.environ['SID']
for i in json.load(sys.stdin):
    s=i.get('service')or i
    if s.get('id')==sid:
        print(s.get('name',''), '|', s.get('plan') or s.get('serviceDetails',{}).get('plan',''))
        break
" SID="$SERVICE_ID")
echo "  Service: $SERVICE_ID ($SERVICE_META)"

echo "→ Prüfe vorhandene Disks…"
DISKS=$(curl -sS -H "$AUTH" -H "Accept: application/json" "$API/services/$SERVICE_ID/disks" 2>/dev/null || echo "[]")
HAS_DISK=$(echo "$DISKS" | python3 -c "
import json, sys, os
mount = os.environ.get('MOUNT','/app/data')
try:
    data = json.load(sys.stdin)
except json.JSONDecodeError:
    data = []
items = data if isinstance(data, list) else data.get('disks', [])
for d in items:
    disk = d.get('disk') or d
    if disk.get('mountPath') == mount:
        print(disk.get('id') or 'yes')
        break
" MOUNT="$MOUNT_PATH" || true)

if [ -n "$HAS_DISK" ] && [ "$HAS_DISK" != "" ]; then
  echo "✓ Disk an $MOUNT_PATH ist bereits vorhanden ($HAS_DISK)."
else
  echo "→ Lege Disk an (${DISK_SIZE_GB} GB, $MOUNT_PATH)…"
  RESP=$(curl -sS -w "\n%{http_code}" -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"name\":\"$DISK_NAME\",\"sizeGB\":$DISK_SIZE_GB,\"mountPath\":\"$MOUNT_PATH\",\"serviceId\":\"$SERVICE_ID\"}" \
    "$API/disks")
  BODY=$(echo "$RESP" | sed '$d')
  CODE=$(echo "$RESP" | tail -n1)
  echo "$BODY" | python3 -m json.tool 2>/dev/null || echo "$BODY"
  if [ "$CODE" != "201" ] && [ "$CODE" != "200" ]; then
    echo ""
    echo "✗ Disk-Anlage fehlgeschlagen (HTTP $CODE)."
    echo "  Häufige Ursache: Service ist Free-Plan — Disks brauchen mind. Starter."
    echo "  Dashboard → Service → Settings → Instance Type → Starter, dann Script erneut."
    exit 1
  fi
  echo "✓ Disk erstellt."
fi

echo "→ Setze DATA_DIR=$MOUNT_PATH und EXPORTS_DIR=$MOUNT_PATH/exports …"
# Render env-var API: PUT /v1/services/{id}/env-vars (bulk) varies; use per-key upsert if available
for PAIR in "DATA_DIR=$MOUNT_PATH" "EXPORTS_DIR=$MOUNT_PATH/exports"; do
  KEY="${PAIR%%=*}"
  VAL="${PAIR#*=}"
  curl -sS -X PUT -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"value\":\"$VAL\"}" \
    "$API/services/$SERVICE_ID/env-vars/$KEY" >/dev/null || \
  curl -sS -X POST -H "$AUTH" -H "Content-Type: application/json" \
    -d "{\"key\":\"$KEY\",\"value\":\"$VAL\"}" \
    "$API/services/$SERVICE_ID/env-vars" >/dev/null || true
done

echo ""
echo "Fertig. Render deployt ggf. neu."
echo "  Ablage-PDFs liegen dann unter $MOUNT_PATH/documents/…"
echo "  In der App: storage.disk_configured sollte true sein (DATA_DIR=/app/data)."
