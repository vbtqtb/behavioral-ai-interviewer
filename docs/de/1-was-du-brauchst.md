# 1. Was du brauchst

[← Übersicht](../../README.de.md) · [Weiter: Online stellen →](2-online-stellen.md) · Stand: 18.11.2026

Du brauchst drei kostenlose Konten und einen kostenpflichtigen API-Schlüssel. Plane etwa 15 Minuten ein.

| Konto | Wofür | Kosten |
|---|---|---|
| [GitHub](https://github.com/signup) | Speichert deine Kopie des Codes und deine Interviewdateien. | Kostenlos |
| [Cloudflare](https://dash.cloudflare.com/sign-up) | Stellt den Interviewer ins Internet. | Kostenloser Tarif reicht (100.000 Anfragen pro Tag) |
| [Qualtrics](https://www.qualtrics.com/) | Deine Umfrage. Die meisten Hochschulen haben eine Lizenz. | Über deine Hochschule |
| Ein LLM-Anbieter | Schreibt die Interviewfragen. | Nach Verbrauch, von unter einem Cent bis etwa 30 Cent pro Interview |

## Einen LLM-Anbieter wählen und einen API-Schlüssel holen

Ein API-Schlüssel ist ein langes Passwort, mit dem der Interviewer das Sprachmodell nutzen darf. Du brauchst nur **einen** davon. Folge der Anleitung des Anbieters:

| Anbieter | Wert für `LLM_PROVIDER` | Anleitung | Schlüssel hier anlegen |
|---|---|---|---|
| OpenAI (GPT) | `openai` | [OpenAI Quickstart](https://platform.openai.com/docs/quickstart) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Google Gemini | `gemini` | [Gemini API-Schlüssel](https://ai.google.dev/gemini-api/docs/api-key?hl=de) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| Anthropic Claude | `claude` | [Claude API: Erste Schritte](https://docs.anthropic.com/en/docs/get-started) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |

Welcher?

- **OpenAI** hat die ursprüngliche Studie von Chopra & Haaland verwendet. Nur mit OpenAI läuft auch die zusätzliche Sicherheitsprüfung der erzeugten Fragen (`moderate_questions`).
- **Gemini** ist am günstigsten. Im kostenlosen Kontingent darf Google die Daten zur Verbesserung seiner Produkte nutzen. Aktiviere deshalb die Abrechnung, bevor du echte Daten erhebst.
- **Claude** funktioniert für getippte Interviews. Gesprochene Antworten kann es nicht in Text umwandeln.

> [!IMPORTANT]
> - Speichere den Schlüssel sofort in einem Passwortmanager. Die meisten Anbieter zeigen ihn nur einmal an.
> - Schicke den Schlüssel nie per E-Mail und füge ihn nie in einen Chat ein.
> - Setze in den Abrechnungseinstellungen des Anbieters ein monatliches Ausgabenlimit. Dann kostet ein Fehler nie mehr als dieses Limit.

## ✅ Das solltest du jetzt haben

- ein GitHub-Konto,
- ein Cloudflare-Konto,
- Zugang zu Qualtrics,
- einen API-Schlüssel, gespeichert im Passwortmanager.

[Weiter: Online stellen →](2-online-stellen.md)
