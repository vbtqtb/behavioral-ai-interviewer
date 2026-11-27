# 4. Ein eigenes Interview schreiben

[← Testen](3-testen.md) · [Übersicht](../../README.de.md) · [Weiter: Qualtrics →](5-qualtrics.md) · Stand: 18.11.2026

Jedes Interview ist eine Textdatei im Ordner `src/interviews/` **deines** GitHub-Repositorys (das Cloudflare angelegt hat, `DEIN-GITHUB-NAME/ai-interviewer`). Der Dateiname ist die ID des Interviews: aus `MEINE_STUDIE.toml` wird `MEINE_STUDIE`.

Du bearbeitest die Datei auf github.com. Sobald du speicherst, stellt Cloudflare die neue Version innerhalb weniger Minuten online.

## Schritt 1: Vorlage kopieren

1. Öffne dein Repository auf github.com und gehe zu `src/interviews/`.
2. Klicke auf `_TEMPLATE.toml` und dann auf den Button **Copy raw file** (zwei Quadrate, oben rechts über der Datei).
3. Gehe zurück zu `src/interviews/` und klicke auf **Add file → Create new file**.
4. Gib der Datei einen Namen, zum Beispiel `MEINE_STUDIE.toml`. Nur Buchstaben ohne Umlaute, Ziffern und `_`. Der Name darf nicht mit `_` beginnen, solche Dateien werden ignoriert.
5. Füge die Vorlage ein.

## Schritt 2: Text anpassen

Die Vorlage erklärt jede Zeile (auf Englisch). Zeilen mit `#` am Anfang sind Kommentare. Diese Teile ändern die meisten Studien:

| Einstellung | Was sie bewirkt |
|---|---|
| `first_question` | Die Einstiegsfrage. Wird genau so angezeigt. |
| `interview_plan` | Die Themen in ihrer Reihenfolge. `length` ist die Zahl der Fragen pro Thema. |
| `closing_questions` | Feste Fragen am Ende. Darf leer sein: `[]`. |
| `[probe] prompt` | Anweisungen für Nachfragen innerhalb eines Themas. |
| `[transition] prompt` | Anweisungen für die Frage, die das nächste Thema eröffnet. |
| `moderate_answers` | `true` prüft jede Antwort, ob sie zum Thema passt. Unpassende Antworten werden nicht gespeichert. |
| `[dag]` | Entferne das `#` vor `[dag]`, um nach jedem Thema einen Ursache-Wirkungs-Graphen zu zeichnen. Die Befragten können ihn bestätigen oder korrigieren. |

Die zwei Beispiele `STOCK_MARKET.toml` und `HOMELESS_BERLIN.toml` sind vollständige Interviews. Du kannst auch eines davon statt der Vorlage kopieren.

Diese Regeln verhindern Fehler:

- Lass die `{Platzhalter}` in den Prompts genau so stehen, mit Klammern. Erfinde keine neuen.
- Text über mehrere Zeilen muss zwischen `"""` und `"""` stehen.
- Ein `model`, das du einträgst, muss zu deinem Anbieter gehören. Mit Gemini brauchst du einen Gemini-Modellnamen. Im Zweifel lass `model` weg.

## Schritt 3: Speichern

Klicke auf **Commit changes**, lass **Commit directly to the main branch** ausgewählt und klicke noch einmal auf **Commit changes**.

Cloudflare baut jetzt die neue Version. Das dauert 2 bis 4 Minuten.

## ✅ Das solltest du jetzt sehen

- `MEINE_STUDIE` in der Liste unter `https://ai-interviewer.DEINE-SUBDOMAIN.workers.dev/interviews`.
- Deine Einstiegsfrage unter `https://ai-interviewer.DEINE-SUBDOMAIN.workers.dev/test/MEINE_STUDIE`.

## Klappt nicht?

Wenn die Datei einen Fehler hat, startet die neue Version nicht. **Cloudflare lässt dann die alte Version online**, eine laufende Studie wird also nicht unterbrochen.

1. Öffne den Worker bei Cloudflare, Reiter **Deployments**, und öffne das neueste Build-Log.
2. Die Fehlermeldung nennt Datei und Problem, zum Beispiel `MEINE_STUDIE.toml: invalid TOML: ...` oder einen fehlenden Prompt.
3. Korrigiere die Datei auf GitHub und speichere erneut.

Ändere ein Interview möglichst nicht, während Menschen es gerade ausfüllen. Wer mitten im Interview ist, bekommt den Rest aus der neuen Version. Lege für eine neue Studie lieber eine neue Datei mit neuem Namen an.

[Weiter: In Qualtrics einbauen →](5-qualtrics.md)
