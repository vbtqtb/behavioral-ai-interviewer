# 6. Deine Daten

[← Qualtrics](5-qualtrics.md) · [Übersicht](../../README.de.md) · [Weiter: Hilfe →](7-hilfe.md) · Stand: 18.11.2026

Jedes Interview wird an zwei Orten gespeichert:

1. **In Qualtrics**, neben den übrigen Antworten der Person. Das ist die Hauptkopie.
2. **In der Sicherungsdatenbank** in deinem Cloudflare-Konto. Sie enthält den vollständigen Verlauf jedes Schritts.

## In Qualtrics

Öffne deine Umfrage, Reiter **Data & Analysis**, und exportiere wie gewohnt (CSV, SPSS, Excel). Das Interview steht in diesen Spalten:

| Spalte | Inhalt |
|---|---|
| `user_id` | Die Qualtrics-Response-ID. Dieselbe ID steht auch in der Sicherungsdatenbank. |
| `interview_transcript` | Das ganze Gespräch als Text. |
| `interview_dags` | Die Ursache-Wirkungs-Graphen als JSON, wenn das Interview `[dag]` nutzt. Sonst `[]`. |
| `interview_done` | `1`, wenn das Interview zu Ende geführt wurde, `0`, wenn die Person vorher aufgehört hat. |
| `first_question` | Die Einstiegsfrage, die die Person gesehen hat. |

### Lange Interviews

Qualtrics begrenzt, wie viel Text in ein Feld passt. Ist ein Transkript länger als etwa 15.000 Zeichen, steht in `interview_transcript` zum Beispiel `SPLIT:3`, und der Text verteilt sich auf `interview_transcript_1`, `interview_transcript_2` und `interview_transcript_3`. Füge die Teile der Reihe nach zusammen:

- Excel: `=B2&C2&D2&E2&F2`, wenn die Spalten B bis F die fünf Teile enthalten.
- R: `paste0(df$interview_transcript_1, df$interview_transcript_2, df$interview_transcript_3, df$interview_transcript_4, df$interview_transcript_5)`
- Stata: `gen transcript = interview_transcript_1 + interview_transcript_2 + interview_transcript_3 + interview_transcript_4 + interview_transcript_5`

Für `interview_dags` gilt dasselbe. Fünf Teile fassen etwa 75.000 Zeichen. Reicht auch das nicht, steht im Feld `SPLIT:5:TRUNCATED`. Der vollständige Text ist dann noch in der Sicherungsdatenbank.

## In der Sicherungsdatenbank

### Alles als CSV herunterladen

Dafür brauchst du das Geheimnis `ADMIN_PASSWORD` ([Kapitel 7](7-hilfe.md#api-schlüssel-ändern-oder-erneuern) zeigt, wie du es nachträglich anlegst). Öffne dann:

```
https://ai-interviewer.DEINE-SUBDOMAIN.workers.dev/export?password=DEIN-PASSWORT
```

Der Browser lädt `interviews.csv` herunter: eine Zeile pro Nachricht, mit den Spalten `session_id` (die Qualtrics-Response-ID), `order`, `time`, `type` (`question` oder `answer`), `content` und den Themenzählern.

Ohne Passwort oder mit falschem Passwort antwortet die Seite `Not found`. Das ist Absicht.

### In Cloudflare ansehen

Cloudflare-Dashboard → **Storage & databases** → **D1 SQL database** → **ai-interviewer**. Die Tabelle `sessions` hat eine Zeile pro Interview, das vollständige Transkript steht in der Spalte `transcript`.

## ✅ Das solltest du jetzt sehen

Nach einem vollständigen Testdurchlauf eine Zeile in Qualtrics mit `interview_done` = `1` und dem Transkript in `interview_transcript`.

[Weiter: Hilfe und Fragen →](7-hilfe.md)
