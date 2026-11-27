# 1. What you need

[← Overview](../../README.md) · [Next: Deploy →](2-deploy.md)

You need three free accounts and one paid API key. Plan about 15 minutes.

| Account | What it is for | Cost |
|---|---|---|
| [GitHub](https://github.com/signup) | Stores your copy of the code and your interview files. | Free |
| [Cloudflare](https://dash.cloudflare.com/sign-up) | Runs the interviewer on the internet. | Free plan is enough (100,000 requests per day) |
| [Qualtrics](https://www.qualtrics.com/) | Your survey. Most universities have a licence. | Through your university |
| One LLM provider | Writes the interview questions. | Pay per use, from under one cent to about 30 cents per interview |

## Pick one LLM provider and get an API key

An API key is a long password that lets the interviewer use the language model. You only need **one** of these. Follow the provider's own guide:

| Provider | Value for `LLM_PROVIDER` | Guide | Create the key here |
|---|---|---|---|
| OpenAI (GPT) | `openai` | [OpenAI quickstart](https://platform.openai.com/docs/quickstart) | [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| Google Gemini | `gemini` | [Gemini API key guide](https://ai.google.dev/gemini-api/docs/api-key) | [aistudio.google.com/apikey](https://aistudio.google.com/apikey) |
| Anthropic Claude | `claude` | [Claude API getting started](https://docs.anthropic.com/en/docs/get-started) | [console.anthropic.com/settings/keys](https://console.anthropic.com/settings/keys) |

Which one?

- **OpenAI** is what the original study by Chopra & Haaland used. It is the only provider that also runs the extra safety check on generated questions (`moderate_questions`).
- **Gemini** is the cheapest. Google may use data from the free tier to improve its products, so turn on billing before you collect real data.
- **Claude** works for text interviews. It cannot transcribe voice answers.

> [!IMPORTANT]
> - Copy the key into a password manager right away. Most providers show it only once.
> - Never send the key by e-mail or paste it into a chat.
> - Set a monthly spending limit in the provider's billing settings. Then a mistake can never cost more than that limit.

## ✅ You should now have

- a GitHub account,
- a Cloudflare account,
- access to Qualtrics,
- one API key, saved in your password manager.

[Next: Deploy →](2-deploy.md)
