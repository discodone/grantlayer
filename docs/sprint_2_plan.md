# GrantLayer MVP — Sprint 2 Plan

**Status:** Vorbereitung (Sprint 1 abgeschlossen)  
**Prinzip:** Einen Sub-Sprint nach dem anderen. Kein Big Bang.

---

## Ausgangslage nach Sprint 1

Was funktioniert:
- Grants mit Zeitfenster erstellen, anzeigen, widerrufen
- Policy Engine (fail-closed): Subject, Rolle, Aktion, Resource, Zeit, Revocation
- Audit-Log für jeden Versuch
- Dashboard im Browser
- 12 Tests, alle grün
- Git-Repo mit sauberem Commit

Was noch fehlt (bewusst ausgelassen):
- Kein kryptographischer Beweis für Grants
- Keine Authentifizierung der API-Caller
- Keine Challenge/Proof-Mechanik
- Keine Docker-Verpackung

---

## Sprint 2A — Challenge/Proof Flow *(empfohlener nächster Schritt)*

**Ziel:** Zeigen, dass ein Techniker beweisen muss, dass er einen Grant besitzt — nicht nur seinen Namen nennt.

**Konzept:**
1. Techniker ruft `POST /challenges` auf — bekommt eine einmalige Challenge-UUID zurück
2. Für den Demo-Proof: Techniker sendet Challenge-UUID bei `POST /demo-action` mit
3. Backend prüft: Challenge existiert, noch nicht verwendet (Replay-Schutz), nicht abgelaufen (z.B. 5 Min TTL)
4. Nach Verwendung: Challenge wird als "consumed" markiert
5. Audit-Event enthält Challenge-ID

**Warum zuerst:**
- Kein externes Tool nötig (nur stdlib)
- Macht den Demo-Flow realistischer
- Vorbereitung für echte Signaturen (Sprint 2B)
- Zeigt Replay-Schutz-Konzept ohne Crypto

**Neue Endpunkte:**
```
POST /challenges              → {challengeId, expiresAt}
GET  /challenges/:id          → Status (pending/consumed/expired)
POST /demo-action  +challengeId  → prüft Grant + Challenge
```

**Neue DB-Tabelle:**
```sql
CREATE TABLE challenges (
    id         TEXT PRIMARY KEY,
    subject_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    consumed   INTEGER DEFAULT 0,
    consumed_at TEXT
);
```

**Tests:**
- Challenge erzeugen → ID zurück
- Challenge verwenden → consumed
- Challenge zweimal verwenden → abgelehnt (Replay-Schutz)
- Abgelaufene Challenge → abgelehnt
- Demo-Action ohne Challenge → weiterhin erlaubt (rückwärtskompatibel)

---

## Sprint 2B — Ed25519 Grant-Signaturen *(abgeschlossen 2026-05-02)*

**Status:** Abgeschlossen. Commit: `Sprint 2B: add Ed25519 grant signatures`

Was implementiert wurde:
- `backend/src/crypto_signing.py` — neu: ensure_demo_keypair, sign_grant, verify_grant_signature, canonical_grant_payload
- `backend/src/models.py` — Grant: +signature, +signing_key_id, +payload_hash; AuditEvent: +grant_signature_result
- `backend/src/db.py` — idempotente Migration für neue Spalten
- `backend/src/grants.py` — create_grant() signiert automatisch
- `backend/src/demo_action.py` — Signaturprüfung vor Policy-Entscheidung
- `backend/src/audit_log.py` — grant_signature_result in Audit-Events
- `backend/src/server.py` — signaturePresent, signingKeyId, payloadHash in API-Responses
- `dashboard/index.html` — Signatur-Spalten im Grant- und Audit-Log-Bereich
- 10 neue Tests (30 total, alle grün)

---

## Sprint 2B (Original-Planung — zu Referenz)

**Ziel:** Grants werden vom Admin kryptographisch signiert. Backend verifiziert die Signatur vor jeder Policy-Prüfung.

**Voraussetzung prüfen:**
```bash
python3 -c "from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey; print('OK')"
```

Falls `cryptography` nicht verfügbar:
```bash
python3 -m pip install cryptography  # oder: apt install python3-cryptography
```

**Keine eigene Crypto.** Nur `cryptography`-Bibliothek oder stdlib `hmac` für Demo-HMAC.

**Konzept (Demo-Variante):**
1. Beim Start: Admin-Keypair generieren (privat lokal, pubkey im Backend bekannt)
2. `POST /grants` → Backend signiert Grant-Payload mit Ed25519-Privatkey
3. `POST /demo-action` → Backend verifiziert Grant-Signatur vor Policy-Check
4. Manipulierter Grant → Signaturprüfung schlägt fehl → Zugriff verweigert

**Achtung:** Privatkey nur im Speicher, nie in DB oder Log. Demo-only.

**Neue Felder im Grant:**
```
signature: base64(Ed25519-Signatur über {id, subjectId, role, action, resource, validFrom, validUntil})
```

---

## Sprint 2C — Demo Admin Token

**Ziel:** API mit minimalem Schutz versehen — für Demo-Präsentation vor Dritten.

**Ansatz:** Statischer Token via Umgebungsvariable, nicht hardgecoded.

```bash
GRANTLAYER_ADMIN_TOKEN=demo-token-2026 python3 -m backend
```

**Schutzumfang:**
- `POST /grants` → erfordert `Authorization: Bearer <token>` Header
- `POST /grants/:id/revoke` → erfordert Token
- `GET /grants`, `GET /audit-events`, `POST /demo-action`, `GET /health` → offen

**Explizit NICHT:**
- Kein Passwort-Hashing
- Kein Session-Management
- Kein OAuth
- Kein JWT
- Token nicht in DB, nicht in Logs

**Falls kein Token gesetzt:** Backend startet trotzdem, gibt beim geschützten Aufruf 401 zurück und loggt Warnung.

---

## Sprint 2D — Docker-Packaging

**Ziel:** `docker compose up` startet das Backend inkl. Daten-Volume.

**Dockerfile:**
```dockerfile
FROM python:3.13-slim
WORKDIR /app
COPY . .
RUN mkdir -p /data
ENV GRANTLAYER_DB=/data/grantlayer.db
EXPOSE 8765
CMD ["python3", "-m", "backend"]
```

**docker-compose.yml:**
```yaml
services:
  grantlayer:
    build: .
    ports:
      - "127.0.0.1:8765:8765"
    volumes:
      - grantlayer-data:/data
    environment:
      - GRANTLAYER_ADMIN_TOKEN=${GRANTLAYER_ADMIN_TOKEN:-change-me}
volumes:
  grantlayer-data:
```

**Voraussetzung:** Docker muss auf der VM laufen (ist der Fall — Paperclip läuft als Docker-Container).

**Explizit NICHT:** Kein öffentlicher Port, kein Deployment, kein Registry-Push.

---

## Empfohlene Reihenfolge

```
Sprint 2A  →  Sprint 2B  →  Sprint 2C  →  Sprint 2D
Challenge     Ed25519       Admin-Token    Docker
(kein dep)    (cryptography) (stdlib)     (Docker)
```

Sprint 2A hat keine Abhängigkeiten und zeigt sofort sichtbaren Demo-Mehrwert.
Sprint 2B benötigt `cryptography`-Bibliothek — erst prüfen ob installierbar.
Sprint 2C ist einfach, aber erst sinnvoll wenn man die Demo extern zeigt.
Sprint 2D ist letzter Schritt, setzt 2A–2C voraus.

---

## Was in Sprint 2 NICHT passiert

- Keine echte Authentifizierung für Produktivbetrieb
- Keine Compliance-Garantien
- Kein Mainnet / Testnet
- Keine Windows-Service-Integration
- Keine echten Adminrechte
- Kein Multi-Approver-Workflow (kommt Sprint 3)
- Keine externen Services
- Kein Deployment

---

## Abhängigkeitsprüfung vor Sprint 2B

```bash
# Prüfen ob cryptography verfügbar:
python3 -c "import cryptography; print(cryptography.__version__)"

# Falls nicht: Installation prüfen
python3 -m pip install cryptography 2>&1 | tail -3
# oder: sudo apt install python3-cryptography
```

Falls `cryptography` nicht installierbar: Sprint 2B überspringen, HMAC-basierte Demo-Signatur als Übergangslösung bauen (stdlib `hmac` + `hashlib`).
