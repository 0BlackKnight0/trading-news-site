# Deploying to Vercel

This repo deploys as **two Vercel projects from the same GitHub repo** — one for
the Next.js frontend, one for the FastAPI backend. Vercel gives a project a
single root directory, so a monorepo like this needs one project per app.

| Project | Root Directory | Framework |
| --- | --- | --- |
| `trading-news-site` | `frontend` | Next.js (auto-detected) |
| `trading-news-api` | `backend` | Other / Python (auto-detected from `requirements.txt`) |

Deploy the **backend first** — the frontend needs its URL.

---

## 1. Database migration

Run [`backend/schema.sql`](backend/schema.sql) in the Supabase SQL editor. It is
idempotent, so it is safe to run against the existing database. It adds:

- `refresh_meta` — tracks when each cache was last refreshed (required, see
  "How refresh works" below)
- `news_cache.summary` — the column the code already writes to

---

## 2. Backend project

1. vercel.com/new → import `0BlackKnight0/trading-news-site`
2. **Root Directory: `backend`**
3. Add environment variables:

   | Variable | Required | Notes |
   | --- | --- | --- |
   | `SUPABASE_URL` | yes | |
   | `SUPABASE_KEY` | yes | |
   | `NEWSAPI_KEY` | no | RSS feeds still work without it |
   | `TELEGRAM_BOT_TOKEN` | no | digest + webhook are skipped if unset |
   | `CRON_SECRET` | yes | random 16+ char string; Vercel sends it as `Authorization: Bearer <value>` on cron runs. **Without it `/cron/daily` AND `/admin/refresh` return 401 to everyone**, including Vercel |
   | `TELEGRAM_WEBHOOK_SECRET` | no | if set, must match `secret_token` in `setWebhook` |
   | `CORS_ORIGINS` | no | defaults to `*`; set to the frontend URL once you have it |

4. Deploy, then verify:

   ```bash
   curl https://<your-api>.vercel.app/health
   ```

## 3. Frontend project

1. vercel.com/new → import the **same repo** again
2. **Root Directory: `frontend`**
3. Environment variable: `NEXT_PUBLIC_API_URL` = the backend URL from step 2
   (no trailing slash)
4. Deploy

`NEXT_PUBLIC_*` values are baked in at build time — after changing it, redeploy
rather than just restarting.

## 4. Telegram webhook (optional)

Serverless cannot hold a polling connection, so registration happens by webhook.
Register it once:

```bash
curl -F "url=https://<your-api>.vercel.app/telegram/webhook" -F "secret_token=$TELEGRAM_WEBHOOK_SECRET" "https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/setWebhook"
```

Then send `/start` to the bot to register for the digest.

---

## How refresh works (and why)

The original backend ran a persistent process: APScheduler, Telegram long-polling,
and two `asyncio` loops refreshing market data every 15 min and news every 30 min.
None of that survives on serverless, where each request is an isolated,
short-lived invocation.

Two mechanisms replace it:

**On-read revalidation.** `GET /market` and `GET /news` check how long ago the
cache was refreshed (`refresh_meta`) and refresh inline when it has expired —
15 min for market and news. Fetches run concurrently, so a cold refresh
costs roughly 1–3s.

**A daily cron.** `/cron/daily` refreshes both caches and sends the Telegram
digest.

The cron cannot do the 15-minute cadence: **Vercel Hobby cron jobs run at most
once per day**, and Vercel may fire them anywhere within the scheduled hour.
The schedule is `30 2 * * *` (UTC) — nominally 08:00 IST, in practice landing
between roughly 07:30 and 08:29 IST. Deploying a more frequent expression on
Hobby fails the build outright. Pro removes both limits.

Practical consequence: data refreshes when someone actually loads the page, not
on a fixed clock. For a personal dashboard that is usually what you want — but
if nobody visits for a day, the digest still goes out on whatever the last cron
refresh fetched.

## What changed from the Railway build

- **Dropped `yfinance` and `nsepython`** in favour of calling the Yahoo chart API
  directly (the approach already used by the ticker endpoint). This removes
  pandas/numpy from the bundle and fixed the India/forex/global quotes, which
  were unreliable from datacenter IPs.
- **Dropped `python-telegram-bot`** — outbound messages go to the Bot HTTP API
  directly, and updates arrive by webhook.
- **Dropped `apscheduler`** along with `backend/scheduler.py`.
- **RSS feeds are fetched concurrently** with a real timeout; `feedparser` was
  opening URLs itself with no timeout, which could stall a request.
- `backend/Procfile` and `backend/railway.toml` still work if you ever move the
  API to a persistent host.

---

## Gotchas that cost time (learned the hard way)

- **Do not set `TZ`.** Vercel reserves the name and rejects it. Nothing in the
  code reads it — it is a leftover from the APScheduler build, which no longer
  exists. Serverless runs UTC regardless.
- **Environment variables only reach a deployment that is built after they are
  saved.** Adding them in Settings does nothing to the running deployment. Add,
  then **Deployments → ⋯ → Redeploy** with the build cache **off**. Symptom of
  forgetting: `/health` returns 200, the Yahoo routes (`/search`, `/ticker`)
  return 200, and every Supabase route returns 500 while `/admin/refresh`
  returns 401.
- **In the current Vercel UI, environment variables live under
  Settings → Environments → Production**, not a top-level "Environment
  Variables" page.
- **Root Directory is the step that breaks builds.** Vercel defaults to the repo
  root, which contains no app. Set it explicitly to `backend` or `frontend`. If
  a project ends up named after the repo, that is the tell that Root Directory
  was left at the default.
- **`NEXT_PUBLIC_API_URL` is compiled into the JS bundle.** Changing it requires
  a rebuild, not a restart. Verify what actually shipped by grepping the
  deployed chunks for the URL.
- **Supabase: leave RLS off, or the app reads nothing.** The schema creates
  tables with no policies. Enabling RLS without writing policies makes every
  query silently return empty — it fails quiet, not loud. The key is only ever
  server-side, so this is an accepted trade, not an oversight. Choose
  "Run without RLS" when the SQL editor prompts.
- **The newer `sb_publishable_*` key format works** with supabase-py 2.31.0;
  the older JWT-style anon key is not required.
