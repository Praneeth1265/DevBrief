# ☕ DevBrief

**A personal tech news app for your phone.** Every morning it picks the IT and software stories worth your time and explains each one in a line, plus *why you* should read it. A notification tells you when the brief is ready, and you read everything inside the app, much like Medium.

<p align="center"><i>Dark, distraction-free reading — Today · Reader · Learn · Settings</i></p>

## What you get

| | |
|---|---|
| ☀️ **Today** | A short brief: 🔥 Must-know · 📰 Headlines · 📚 Deep reads · 🛡️ Security watch · 🚀 Release radar. It has a TL;DR, a read-progress bar, and unread dots. **8 stories at most**, and fewer on a slow day. |
| 📖 **Reader** | Each story opens in a clean reading view: a one-line summary, a *Why you should read this* note, tags, read time, **Read full article ↗**, the Hacker News discussion when there is one, Save, Share, and *Up next*. |
| 🧠 **Key points & background** | Every story comes with 2–3 key points and a short background explainer, so you understand it without leaving the app. |
| ✅ **Daily quiz** | 3 questions on that day's stories, with explanations and links back to the story. Your best score is kept. |
| 🧭 **Explore** | **Trending this week** shows topics gaining stories. Tap any topic to follow it across days. Search every past brief. |
| 💼 **Careers & hiring** | A section for Indian and global tech hiring, layoffs, placements and skills in demand. |
| 🎧 **Listen** | The whole brief read aloud on your phone, for your commute. |
| ✍️ **Notes** | Add a note to any story. It's saved automatically and shows under the story in Saved. |
| 📊 **Your progress** | Stories read this week, your streak, quiz accuracy. |
| 🎯 **Learn** | Every day's *Interview angle* concept and *Jargon buster* terms build up into a library, with a **flashcard mode** for revision during placement season. |
| 🗂 **Archive** | Every past brief, searchable, plus the **Sunday week-in-review**. |
| 🔖 **Saved** | Bookmark stories to read later. Saved stories work offline. |
| 🔔 **Notifications** | A real push notification at about 6:30 AM. Security alerts arrive at high priority. Tapping the notification opens the brief, which was already downloaded in the background. |
| ✨ Extras | Reading streak 🔥, dark mode, text size setting, works offline, installs with its own icon and opens full-screen. |

## Why it's a PWA and not a Play Store app

DevBrief is a **Progressive Web App**. You install it from the browser and it behaves like a native app: a home-screen icon, full-screen view, offline reading and push notifications. Compared with a native app it has some clear advantages:

- **Free to run.** It needs no Play Store account (₹2,000 one-time) or Apple developer account ($99/year).
- **One codebase** for Android and iPhone.
- **Updates itself.** Push a change to GitHub and your phone has it the next time you open the app.

If you ever want a real `.apk`, the same app can be wrapped with Capacitor or Bubblewrap without rewriting it.

## How it works

```
GitHub Actions (6:15 IST daily)                         Your phone
┌──────────────────────────────────────────┐            ┌──────────────────────────┐
│ fetch ~25 sources  → filter & dedupe     │  commits   │ DevBrief app (PWA)       │
│ → LLM editor (score ≥ 6, ≤ 8 items)      │ ─────────► │ reads docs/api/*.json    │
│ → write docs/api/*.json (the app's feed) │  Pages     │ from GitHub Pages        │
│ → Web Push ──────────────────────────────┼──────────► │ 🔔 notification          │
└──────────────────────────────────────────┘            └──────────────────────────┘
```
Sources include Hacker News (only stories with 120+ points), Lobsters, InfoQ, Pragmatic Engineer, ByteByteGo, Martin Fowler, Netflix, Cloudflare, Meta and Stripe engineering blogs, GitHub blog, security feeds, Indian tech news (ET Tech, Inc42), and GitHub releases of your stack.

**Cost: ₹0.** It runs on GitHub Actions and GitHub Pages, and uses the Gemini API free tier.

---

## Setup (about 20 minutes, one time)

### 1. Put the code on GitHub
```bash
cd devbrief
git init && git add . && git commit -m "DevBrief"
gh repo create devbrief --public --source . --push
```
A **public** repo gets free Pages and unlimited Actions minutes. The only things published are news headlines and summaries. Your keys stay in encrypted Secrets.

### 2. Turn on GitHub Pages (this hosts the app)
Go to **Settings → Pages → Build and deployment → Deploy from a branch → `main` / `/docs`**.
Your app will be at `https://<username>.github.io/devbrief/`. Put that URL in `config.yaml`:
```yaml
delivery:
  site_url: "https://<username>.github.io/devbrief"
```

### 3. Add the keys as repo secrets
Go to **Settings → Secrets and variables → Actions → New repository secret**.

| Secret | How to get it |
|---|---|
| `GEMINI_API_KEY` | Free from <https://aistudio.google.com/apikey> |
| `VAPID_PUBLIC_KEY`, `VAPID_PRIVATE_KEY` | Run `pip install -r requirements.txt && python -m devbrief keys` once on your laptop, then copy both lines |

Then go to **Actions → DevBrief → Run workflow**, enter `run` and start it. This publishes your first brief and the app's settings.

### 4. Install the app on your phone
- **Android (Chrome):** open your app URL, then tap **Install** on the banner, or ⋮ → *Install app*.
- **iPhone (Safari, iOS 16.4+):** open the URL, then tap **Share → Add to Home Screen**. Open DevBrief from the new home-screen icon. On iPhone, notifications only work from the installed app.

### 5. Turn on notifications
1. In the app, open **⚙︎ Settings → Enable notifications** and allow them.
2. The app shows a **device code**. Tap **Copy code**.
3. On GitHub, add a secret named **`WEBPUSH_SUBSCRIPTION`** and paste the code.
4. Go to **Actions → Run workflow** and enter `test-delivery`. You should get a 🔔 test notification.

Done. From now on, the brief arrives every morning.

> Want it on two devices? Make `WEBPUSH_SUBSCRIPTION` a JSON list holding both codes: `[ {...}, {...} ]`.
> Want an email copy too? Set `email: true` in `config.yaml` and add `GMAIL_ADDRESS` and `GMAIL_APP_PASSWORD` (a Gmail app password).

---

## Tuning (all in `config.yaml`)

| Want | Change |
|---|---|
| Fewer items | `max_items: 5` |
| Stricter quality | `min_score: 7` |
| A topic matters more or less | change its weight (1–3) under `interests` |
| Never see a topic again | add a keyword to `avoid` |
| A new blog | add a line under `sources` with its RSS URL |
| Releases of your stack | edit `release_radar` (GitHub `owner/repo`) |
| A different time | edit the cron in `.github/workflows/daily.yml` (UTC; IST = UTC + 5:30) |

## Running locally
```bash
pip install -r requirements.txt
python scripts/demo_preview.py              # fills a local copy of the app with sample data
python -m http.server -d demo_site 8000     # open http://localhost:8000 (phone-size window)
python -m devbrief run --dry-run            # real fetch + curate, sends nothing
python -m pytest -q
```

## Project layout
```
devbrief/      pipeline: sources → filtering → curate (LLM) → state (app JSON) → deliver (push/email)
docs/          the app (index.html, app.js, app.css, sw.js, manifest) + docs/api/ written by the pipeline
templates/     optional email layout
config.yaml    your interests, sources, limits
```
Safety rails:
- Links always come from the source feeds, never from the LLM.
- If one feed fails, the rest still run.
- If *every* source fails, the run fails, and GitHub emails you about it so you don't get an empty brief.
- If the LLM is unavailable, the app falls back to rule-based ranking.
