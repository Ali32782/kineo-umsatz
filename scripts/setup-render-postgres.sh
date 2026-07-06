#!/usr/bin/env bash
# Render PostgreSQL mit bestehendem Web-Service verknüpfen (Free Tier).
# Persistent storage ohne Starter-Upgrade.
set -euo pipefail

cat <<'EOF'
PostgreSQL auf Render einrichten (Free)
=======================================

1. Render Dashboard → New + → PostgreSQL
   - Name: kineo-db
   - Database: kineo
   - User: kineo
   - Plan: Free

2. Nach Erstellung: Datenbank öffnen → «Connections»
   - «Internal Database URL» kopieren
     (Format: postgres://kineo:...@.../kineo)

3. Web-Service «kineo-umsatz» öffnen → Environment
   - Neue Variable: DATABASE_URL = (eingefügte URL)
   - Speichern → Deploy startet automatisch

4. Nach Deploy (2–3 Min.):
   - App öffnen → Login
   - Dashboard: oben rechts «✓ PostgreSQL — Daten persistent»
   - Juni-CSV einmal hochladen → bleibt dauerhaft erhalten

Hinweis: Beim ersten Start mit leerer PostgreSQL-DB werden
Benutzer und MA-Stammdaten automatisch angelegt (wie bei Neuinstallation).

EOF
