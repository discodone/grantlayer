# GrantLayer — Externer Tester-Report

**Tester-Persona:** Python-Backend-Entwickler, erstmals auf dem Repo, keine interne Doku gelesen.  
**Getestet:** 2026-06-09  
**Testgrundlage:** `README.md` + `QUICKSTART.md` (GitHub `main`-Stand)

---

## Schritt-für-Schritt Protokoll

| Schritt | Befehl/Aktion | Ergebnis | Dauer | Anmerkungen |
|---------|---------------|----------|-------|-------------|
| 1 | Repo klonen (bereits vorhanden unter `/home/adminuser/projects/grantlayer-mvp`) | — | 0 s | Am Ende des Tages nur lesen |
| 2 | `README.md` lesen | Verstanden: FastAPI + SQLite/Postgres, Ed25519-Signaturen, JWT-Auth, Operator-Model | 1 min | Erklärung ist klar, "Developer Preview"-Warnung gut sichtbar |
| 3 | `QUICKSTART.md` lesen | Ablauf verstanden: JWT-Secret setzen → Certs → Docker → Health → Token → CRUD → Audit | 1 min | Verspricht "unter 5 Minuten" |
| 4 | `.env` aus `.env.example` kopieren & `GRANTLAYER_JWT_SECRET` setzen | Erfolg | 1 min | `GRANTLAYER_JWT_SECRET` war leer → QUICKSTART warnt ordentlich, dass sonst Legacy-Mode gilt. Aber: `.env` existierte schon im geklonten Repo, daher musste ich editieren statt kopieren. |
| 5 | `./nginx/generate-certs.sh` | "Certs already exist — skipping" | 10 s | Für einen Frisch-Clone ok, aber beim Testen irritierend, weil nicht 100% sicher, ob die Certs valide sind. |
| 6 | `docker compose up -d` | Stack startet sauber, beide Container healthy | 15 s | Sauber. Keine Fehler. |
| 7 | `curl -k https://localhost/health` | `{"status":"ok","service":"grantlayer","checkType":"liveness"}` | 2 s | Funktioniert auf Anhieb. |
| 8 | JWT-Token generieren (`create_dev_token`) | Token erhalten | 5 s | Funktioniert. |
| 9 | `POST /grants` | Grant erstellt, `id`, `signature`, `signatureValid: true` | 3 s | **Response enthält mehr Felder als in QUICKSTART.md dokumentiert** (`signature`, `signingKeyId`, `payloadHash`, `revokedBy`, `revokedReason`, `revokedAt`). Verwirrend, wenn man die Doku als Ground-Truth nimmt. |
| 10 | `GET /grants` | Liste mit 2 Grants (1 aus vorherigem Test-Lauf, 1 frisch) | 2 s | Funktioniert. |
| 11 | `GET /audit-events?limit=20` | `[]` — **leeres Array** | 2 s | ❌ **Erwartet:** Audit-Events vom Grant-Erstellen. **Erhalten:** Nichts. Widerspricht der Kern-Value-Proposition "tamper-evident audit chain". |
| 12 | `POST /grant-requests` (Operator Model) | `{"error":"Operator model is disabled","errorCode":"operator_model_disabled"}` | 2 s | ❌ **Dokumentation sagt:** "`GRANTLAYER_ENABLE_OPERATOR_MODEL=true` must be set in `.env` (it is the default)". **Realität:** `.env.example` + `.env` haben `false`. Docker-Compose fallback ist ebenfalls `false`. Schritt 7 im Quickstart ist damit out-of-the-box kaputt. |
| 13 | `docker compose down` | Stack sauber gestoppt | 5 s | Ok. |

**Gesamtdauer bis erfolgreicher Grant-Create:** ~4 Minuten (stimmt grob mit "under 5" überein).  
**Gesamtdauer inkl. fehlgeschlagener Steps:** ~5 Minuten.

---

## Gesamtbewertung: **6 / 10**

### Was funktioniert gut
1. **Docker-Compose-Setup ist robust.** `docker compose up -d` startet sauber, Healthchecks funktionieren, Nginx-Proxy steht. Für einen Backend-Dev ist das angenehm.
2. **Grant-Erstellung mit Ed25519-Signaturen funktioniert.** Die Response zeigt `signaturePresent: true` und `signatureValid: true` — das ist überzeugend.
3. **JWT-Token-Generierung ist einfach.** Der Python-Snippet aus der Doku funktioniert copy-paste-fähig.
4. **Lokale Dev-Erfahrung.** Kein externes Postgres nötig, SQLite reicht, `./nginx/generate-certs.sh` macht self-signed Certs.

### Was ist kaputt oder unklar
1. **Audit-Log ist nach Grant-Create leer.** Das ist der größte Design-/Implementierungs-Fehler. Ein Audit-Layer, der keine Events beim Erstellen eines Grants schreibt, erfüllt seinen Kernzweck nicht. Ich habe keinen Hinweis gefunden, dass man erst ein Event manuell triggern muss.
2. **Operator Model ist default-mäßig deaktiviert.** QUICKSTART.md behauptet, es sei default `true`. `.env.example`, `.env` und `docker-compose.yml` sagen alle `false`. Das macht Schritt 7 im Quickstart kaputt.
3. **Response-Schemas in Doku nicht aktuell.** `POST /grants` liefert Felder wie `signature`, `signingKeyId`, `payloadHash`, `revokedAt` etc., die in QUICKSTART.md nicht erwähnt sind. Als Tester fragt man sich: "Ist das ein Bug oder ein Feature?"
4. **Gemischte Auth-Modi verwirren.** `.env.example` setzt `GRANTLAYER_REQUIRE_ADMIN_TOKEN=true`, Docker-Compose defaulted auf `false`. Das fühlt sich an, als hätten die Defaults nie abgestimmt worden.
5. **Kein automatisierter Setup-Script.** Ein simples `./scripts/setup.sh`, das `.env` erstellt und ein Secret generiert, würde den Einstieg erheblich beschleunigen.

---

## Top 3 Dinge, die gefixt werden müssen

| # | Problem | Gewichtung | Fix-Vorschlag |
|---|---------|------------|---------------|
| 1 | **Audit-Events sind leer nach Grant-Create** | 🔴 Kritisch | `POST /grants` muss zwingend ein Audit-Event schreiben, oder der Quickstart muss erklären, wie man Audit-Events produziert. Sonst ist das Produktversprechen "tamper-evident" hohl. |
| 2 | **Operator Model default-Wert-Widerspruch** | 🟡 Hoch | `.env.example`, `docker-compose.yml` und `QUICKSTART.md` auf denselben Default (`true` oder `false`) abstimmen. QUICKSTART.md behauptet `true` als Default → mindestens `.env.example` und `docker-compose.yml` müssen das widerspiegeln. |
| 3 | **Response-Schemas in QUICKSTART.md nicht aktuell** | 🟡 Mittel | QUICKSTART.md Schritt 5 (Create Grant) aktualisieren, sodass die gezeigte JSON-Response dem tatsächlichen Response-Body entspricht. Sonst zweifelt der Entwickler an der API-Stabilität. |

---

## Würde ich das Projekt weiterempfehlen?

**Nein — noch nicht.**

Als zynischer externer Entwickler habe ich ein funktionierendes Docker-Setup und eine funktionierende Grant-Erstellung gesehen. Aber:

- Der **Audit-Log ist leer**, obwohl ich gerade einen Grant erstellt habe. Das Produkt nennt sich "GrantLayer" und verspricht "traceable, tamper-evident, independently auditable". Ein leerer Audit-Log nach der ersten Aktion zerstört das Vertrauen in das Kernversprechen.
- **Die Doku lügt über Defaults.** Wenn Schritt 7 im offiziellen Quickstart out-of-the-box mit `operator_model_disabled` scheitert, frage ich mich, wer das zuletzt getestet hat.
- **Entwickler-Preview** ist fair als Label, aber ein Quickstart sollte zumindest die dokumentierten Schritte 1:1 abbilden.

Ich würde es erst weiterempfehlen, wenn:
1. Der Audit-Log nach Grant-Create nicht leer ist.
2. Der Quickstart von A–Z ohne Anpassungen durchläuft.
3. Die Response-Schemas in der Doku mit der API übereinstimmen.

---

*Report erstellt von: OpenCode (Tester-Persona: ext. Python-Dev)*
