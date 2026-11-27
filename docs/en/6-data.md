# 6. Get your data

[← Qualtrics](5-qualtrics.md) · [Overview](../../README.md) · [Next: Help →](7-help.md)

Every interview is saved in two places:

1. **Qualtrics**, next to the respondent's other answers. This is the main copy.
2. **The backup database** in your Cloudflare account. It holds the full history of every turn.

## In Qualtrics

Open your survey, tab **Data & Analysis**, and export as usual (CSV, SPSS, Excel). The interview is in these columns:

| Column | Content |
|---|---|
| `user_id` | The Qualtrics Response ID. The same ID is used in the backup database. |
| `interview_transcript` | The whole conversation as text. |
| `interview_dags` | The cause-and-effect graphs as JSON, if the interview uses `[dag]`. Otherwise `[]`. |
| `interview_done` | `1` if the interview reached its end, `0` if the respondent left early. |
| `first_question` | The opening question the respondent saw. |

### Long interviews

Qualtrics limits how much text fits into one field. If a transcript is longer than about 15,000 characters, `interview_transcript` contains `SPLIT:3` (for example) and the text is in `interview_transcript_1`, `interview_transcript_2` and `interview_transcript_3`. Join them in order:

- Excel: `=B2&C2&D2&E2&F2`, if columns B to F hold the five parts.
- R: `paste0(df$interview_transcript_1, df$interview_transcript_2, df$interview_transcript_3, df$interview_transcript_4, df$interview_transcript_5)`
- Stata: `gen transcript = interview_transcript_1 + interview_transcript_2 + interview_transcript_3 + interview_transcript_4 + interview_transcript_5`

The same applies to `interview_dags`. Five parts hold about 75,000 characters. If even that is too little, the field says `SPLIT:5:TRUNCATED`; the full text is still in the backup database.

## In the backup database

### Download everything as CSV

This needs the `ADMIN_PASSWORD` secret ([chapter 7](7-help.md#change-or-rotate-an-api-key) shows how to add one later). Then open:

```
https://ai-interviewer.YOUR-SUBDOMAIN.workers.dev/export?password=YOUR-PASSWORD
```

The browser downloads `interviews.csv`, one row per message, with the columns `session_id` (the Qualtrics Response ID), `order`, `time`, `type` (question or answer), `content`, and the topic counters.

Without a password, or with a wrong one, the page answers `Not found`. That is on purpose.

### Look at it in Cloudflare

Cloudflare dashboard → **Storage & databases** → **D1 SQL database** → **ai-interviewer**. The table `sessions` has one row per interview, with the full transcript in the column `transcript`.

## ✅ You should now see

After one complete test run, a row in Qualtrics with `interview_done` = `1` and the transcript in `interview_transcript`.

[Next: Help and questions →](7-help.md)
