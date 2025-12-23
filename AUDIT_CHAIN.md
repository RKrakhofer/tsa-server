# TSA Audit Chain - Vertrauenswürdigkeitsnachweis

## Überblick

Die TSA Audit Chain erstellt einen verifizierbaren Nachweis der Vertrauenswürdigkeit Ihres TSA-Servers durch:

1. **Regelmäßige Selbst-Audits**: Ihr TSA-Server erstellt stündlich Zeitstempel
2. **Externe Verifizierung**: Diese werden sofort von freetsa.org (oder anderen vertrauenswürdigen TSAs) gegensigniert
3. **Unveränderliche Audit-Kette**: Alle Audits werden in einer SQLite-Datenbank gespeichert
4. **Unabhängige Verifizierung**: Jeder kann die Audit-Kette validieren

## Konzept

```
┌─────────────────────────────────────────────────────────────┐
│  Ihr TSA-Server                                             │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  1. Erstellt Test-Timestamp                          │  │
│  │     "TSA-AUDIT-2025-12-23T10:00:00Z"                 │  │
│  │                                                       │  │
│  │  2. Hash des Timestamps                              │  │
│  │     → a3f5c8e9...                                    │  │
│  └──────────────────────────────────────────────────────┘  │
│                           │                                 │
│                           ▼                                 │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  3. Sendet an freetsa.org                            │  │
│  │     POST https://freetsa.org/tsr                     │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  FreeTSA.org (Externe TSA)                                  │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  4. Erstellt RFC 3161 Timestamp Response             │  │
│  │     - Signiert mit FreeTSA-Zertifikat                │  │
│  │     - Enthält genaue Zeit                            │  │
│  │     - Hash des Original-Timestamps                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│  Audit-Datenbank (audit_chain.db)                          │
│  ┌──────────────────────────────────────────────────────┐  │
│  │  Eintrag #1234:                                      │  │
│  │  - Zeitstempel: 2025-12-23T10:00:00Z                 │  │
│  │  - Lokaler Token Hash: a3f5c8e9...                   │  │
│  │  - Externes TSR: (signiertes Binär-Dokument)         │  │
│  │  - TSA URL: https://freetsa.org/tsr                  │  │
│  │  - Status: success                                   │  │
│  └──────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

## Installation & Setup

### 1. Abhängigkeiten installieren

```bash
# Falls noch nicht geschehen
pip install -r requirements.txt
```

### 2. Manueller Test

Testen Sie die Audit-Funktionalität manuell:

```bash
# Terminal 1: TSA-Server starten
python -m tsa.server --host 127.0.0.1 --port 5000

# Terminal 2: Einmaligen Audit-Timestamp erstellen
python -c "
from pathlib import Path
from tsa.audit_chain import AuditChain

ac = AuditChain(Path('audit_chain.db'))
record = ac.create_audit_timestamp('http://127.0.0.1:5000/tsa')
print(f'Status: {record.status}')
print(f'Hash: {record.local_token_hash}')
print(f'TSA: {record.external_tsa_url}')
"
```

### 3. Automatischen Scheduler starten

```bash
# Scheduler mit Standard-Einstellungen (stündlich)
python -m tsa.audit_scheduler

# Custom Intervall (z.B. alle 30 Minuten)
python -m tsa.audit_scheduler --interval 1800

# Mit mehreren Backup-TSAs
python -m tsa.audit_scheduler \
  --external-tsa https://freetsa.org/tsr \
  --external-tsa https://zeitstempel.dfn.de \
  --interval 3600
```

### 4. Docker-Deployment (Empfohlen)

Für Produktions-Umgebungen verwenden Sie Docker Compose mit Registry-Images:

```bash
# .env Datei erstellen und konfigurieren
cp .env.example .env
# Editieren: GITHUB_REPOSITORY=your-username/tsa-server

# Images aus Registry ziehen
docker compose -f docker-compose.audit.yml pull

# TSA-Server UND Audit-Scheduler zusammen starten
docker compose -f docker-compose.audit.yml up -d

# Logs anzeigen
docker compose -f docker-compose.audit.yml logs -f audit-scheduler

# Status prüfen
docker compose -f docker-compose.audit.yml ps
```

**Lokale Entwicklung (Images lokal bauen):**

```bash
docker compose -f docker-compose.local.yml up -d
```

## Verwendung

### Audit-Statistiken abrufen

```python
from pathlib import Path
from tsa.audit_chain import AuditChain

ac = AuditChain(Path('audit_chain.db'))
stats = ac.get_statistics()

print(f"Gesamt-Audits: {stats['total_audits']}")
print(f"Erfolgsquote: {stats['success_rate']:.1f}%")
print(f"Letzter Audit: {stats['last_audit_time']}")
```

### Audit-Historie exportieren

```bash
python -c "
from pathlib import Path
from tsa.audit_chain import AuditChain

ac = AuditChain(Path('audit_chain.db'))
ac.export_audit_proof(Path('audit_proof.json'), limit=100)
print('Audit-Nachweis exportiert nach audit_proof.json')
"
```

### Audit-Kette verifizieren

```bash
# Einfache Verifizierung
python tools/verify_audit_chain.py audit_chain.db

# Detaillierte Verifizierung
python tools/verify_audit_chain.py audit_chain.db --verbose

# Mit JSON-Export
python tools/verify_audit_chain.py audit_chain.db --export-json verification_results.json
```

## Vertrauenswürdigkeitsnachweis

### Für Kunden/Partner

Um die Vertrauenswürdigkeit Ihres TSA-Servers nachzuweisen:

1. **Exportieren Sie die Audit-Kette**:
   ```bash
   python -c "from pathlib import Path; from tsa.audit_chain import AuditChain; \
              AuditChain(Path('audit_chain.db')).export_audit_proof(Path('proof.json'))"
   ```

2. **Teilen Sie `proof.json`** mit Ihren Kunden

3. **Kunden können verifizieren**:
   ```bash
   python tools/verify_audit_chain.py audit_chain.db --verbose
   ```

### Was beweist die Audit-Kette?

✓ **Zeitliche Kontinuität**: Regelmäßige Audits beweisen kontinuierlichen Betrieb  
✓ **Externe Validierung**: FreeTSA bestätigt unabhängig jeden Audit  
✓ **Unveränderbarkeit**: Externe TSR können nicht rückdatiert werden  
✓ **Transparenz**: Jeder kann die Kette verifizieren  

### Beispiel-Nachweis

```json
{
  "export_date": "2025-12-23T15:30:00Z",
  "statistics": {
    "total_audits": 720,
    "successful_audits": 718,
    "success_rate": 99.7,
    "last_audit_time": "2025-12-23T15:00:00Z"
  },
  "records": [
    {
      "timestamp": "2025-12-23T15:00:00Z",
      "local_token_hash": "a3f5c8e9...",
      "external_tsr_hex": "3082...",
      "external_tsa_url": "https://freetsa.org/tsr",
      "status": "success"
    }
  ]
}
```

## Konfiguration

### Audit-Intervalle

| Intervall | Sekunden | Empfehlung |
|-----------|----------|------------|
| 5 Minuten | 300 | Hochsicherheit, häufige Validierung |
| 30 Minuten | 1800 | Ausgewogen |
| 1 Stunde | 3600 | **Standard** - gute Balance |
| 6 Stunden | 21600 | Niedrige Frequenz, weniger Netzwerk-Last |
| 24 Stunden | 86400 | Minimum für Compliance |

### Externe TSAs

Verfügbare öffentliche TSAs:

- **freetsa.org**: `https://freetsa.org/tsr` (kostenlos, gut etabliert)
- **DFN**: `https://zeitstempel.dfn.de` (deutsch, akademisch)

### Fehlerbehandlung

Der Scheduler verwendet automatisch Backup-TSAs:

```python
external_tsas = [
    'https://freetsa.org/tsr',      # Primär
    'https://zeitstempel.dfn.de',   # Backup #1
]
```

Falls die primäre TSA nicht verfügbar ist, wird automatisch die nächste verwendet.

## Monitoring & Wartung

### Systemd Service (Linux)

```ini
# /etc/systemd/system/tsa-audit.service
[Unit]
Description=TSA Audit Scheduler
After=network.target

[Service]
Type=simple
User=tsa
WorkingDirectory=/opt/tsa-server
ExecStart=/opt/tsa-server/.venv/bin/python -m tsa.audit_scheduler \
  --db /var/lib/tsa/audit_chain.db \
  --local-tsa http://127.0.0.1:5000/tsa \
  --interval 3600
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable tsa-audit
sudo systemctl start tsa-audit
sudo systemctl status tsa-audit
```

### Log-Monitoring

```bash
# Echtzeit-Logs
journalctl -u tsa-audit -f

# Fehler der letzten Stunde
journalctl -u tsa-audit --since "1 hour ago" -p err
```

### Datenbank-Wartung

```bash
# Datenbank-Größe prüfen
du -h audit_chain.db

# Alte Einträge löschen (älter als 1 Jahr)
sqlite3 audit_chain.db "DELETE FROM audit_records WHERE created_at < strftime('%s', 'now', '-1 year')"

# Datenbank optimieren
sqlite3 audit_chain.db "VACUUM"
```

## Best Practices

1. **Backup der Audit-Datenbank**:
   ```bash
   # Tägliches Backup
   cp audit_chain.db "audit_chain_$(date +%Y%m%d).db"
   ```

2. **Redundante Speicherung**: Speichern Sie Backups extern

3. **Regelmäßige Verifizierung**: 
   ```bash
   # Wöchentlicher Cron-Job
   0 0 * * 0 python tools/verify_audit_chain.py /var/lib/tsa/audit_chain.db
   ```

4. **Monitoring-Alerts**: Benachrichtigung bei Fehlschlägen

5. **Dokumentation**: Teilen Sie `proof.json` regelmäßig mit Stakeholdern

## Compliance & Rechtliches

Die Audit-Kette hilft bei:

- **eIDAS-Konformität**: Nachweis der Zuverlässigkeit
- **ISO 27001**: Audit-Trail für Informationssicherheit
- **SOC 2**: Kontinuierliches Monitoring
- **DSGVO**: Transparenz und Nachvollziehbarkeit

## Troubleshooting

### Problem: Alle Audits schlagen fehl

```bash
# Netzwerk-Konnektivität prüfen
curl -X POST https://freetsa.org/tsr --data-binary "test"

# TSA-Server erreichbar?
curl http://127.0.0.1:5000/health
```

### Problem: Datenbank-Fehler

```bash
# Datenbank-Integrität prüfen
sqlite3 audit_chain.db "PRAGMA integrity_check"

# Neu initialisieren (VORSICHT: Löscht Daten!)
rm audit_chain.db
python -m tsa.audit_scheduler --interval 60  # Startet neu
```

### Problem: Hohe Fehlerrate

- Prüfen Sie externe TSA-Verfügbarkeit
- Erhöhen Sie Timeout-Werte
- Fügen Sie mehr Backup-TSAs hinzu

## Weitere Ressourcen

- RFC 3161: https://tools.ietf.org/html/rfc3161
- FreeTSA Dokumentation: https://freetsa.org/docs
- eIDAS Verordnung: https://ec.europa.eu/digital-building-blocks/wikis/display/DIGITAL/eIDAS

## Support

Bei Fragen oder Problemen:
1. Prüfen Sie die Logs: `journalctl -u tsa-audit`
2. Verifizieren Sie die Audit-Kette: `python tools/verify_audit_chain.py`
3. Erstellen Sie ein Issue auf GitHub
