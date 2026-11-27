# 4. Write your own interview

[← Test](3-test.md) · [Overview](../../README.md) · [Next: Qualtrics →](5-qualtrics.md)

Each interview is one text file in the folder `src/interviews/` of **your** GitHub repository (the one Cloudflare created, `YOUR-GITHUB-NAME/ai-interviewer`). The file name is the interview's ID: `MY_STUDY.toml` becomes `MY_STUDY`.

You edit the file on github.com. When you save it, Cloudflare puts the new version online within a few minutes.

## Step 1: Copy the template

1. Open your repository on github.com and go to `src/interviews/`.
2. Click `_TEMPLATE.toml`, then the **Copy raw file** button (two squares, top right of the file).
3. Go back to `src/interviews/` and click **Add file → Create new file**.
4. Name the file, for example `MY_STUDY.toml`. Use only letters, digits and `_`. Do not start the name with `_`: files starting with `_` are ignored.
5. Paste the template.

## Step 2: Edit the text

The template explains every line. Lines starting with `#` are comments. These are the parts most studies change:

| Setting | What it does |
|---|---|
| `first_question` | The opening question. Shown exactly as written. |
| `interview_plan` | The topics, in order. `length` is how many questions each topic gets. |
| `closing_questions` | Fixed questions at the end. Can be empty: `[]`. |
| `[probe] prompt` | Instructions for follow-up questions inside a topic. |
| `[transition] prompt` | Instructions for the question that opens the next topic. |
| `moderate_answers` | `true` checks every answer for off-topic text. Off-topic answers are not stored. |
| `[dag]` | Remove the `#` in front of `[dag]` to draw a cause-and-effect graph after each topic. The respondent can accept or correct it. |

The two examples, `STOCK_MARKET.toml` and `HOMELESS_BERLIN.toml`, are complete interviews you can copy instead of the template.

Rules that cause errors:

- Keep the `{placeholders}` in the prompts exactly as they are, braces included. Do not invent new ones.
- Text that spans several lines must be inside `"""` ... `"""`.
- A `model` you set must belong to your provider. A Gemini setup needs a Gemini model name. If unsure, leave `model` out.

## Step 3: Save

Click **Commit changes**, keep **Commit directly to the main branch**, and click **Commit changes** again.

Cloudflare now builds the new version. That takes 2 to 4 minutes.

## ✅ You should now see

- `MY_STUDY` in the list at `https://ai-interviewer.YOUR-SUBDOMAIN.workers.dev/interviews`.
- Your opening question at `https://ai-interviewer.YOUR-SUBDOMAIN.workers.dev/test/MY_STUDY`.

## Something went wrong?

If the file has a mistake, the new version does not start. **Cloudflare keeps the old version online**, so a running study is not interrupted.

1. Open the worker in Cloudflare, tab **Deployments**, and open the newest build log.
2. The error names the file and the problem, for example `MY_STUDY.toml: invalid TOML: ...` or a missing prompt.
3. Fix the file on GitHub and commit again.

Avoid changing an interview while people are taking it. Someone in the middle of an interview gets the rest of it from the new version. For a new study, create a new file with a new name instead.

[Next: Put it into Qualtrics →](5-qualtrics.md)
