# Improved News Feed — Design

**Date:** 2026-09-05
**Status:** Approved, ready for implementation planning
**Builds on:** `docs/superpowers/specs/2026-09-05-smart-watchlist-design.md` (Phase 1, "The Line")

---

## 1. Thesis

Phase 1 answered *what changed?* This answers the question that immediately follows:
**why?**

A price move without its cause is half a fact. The original build had a news
feed, but it was a separate RSS reader that happened to share a page with the
prices — three global editorial buckets, sorted by publish time, with no
connection to what the user actually holds. If RELIANCE broke out and RELIANCE
reported earnings, nothing in the UI joined those two things.

This design makes news part of the product: **news about your symbols, first.**

---

## 2. What is actually wrong today (measured, not assumed)

Checked against the live feeds and the production database on 2026-09-05.

**Four of nine configured feeds are dead or blocking:**

| Feed | Status |
| --- | --- |
| `feeds.reuters.com/reuters/businessNews` | does not resolve |
| `feeds.reuters.com/reuters/energyNews` | does not resolve |
| `moneycontrol.com/rss/business.xml` | 403 against the configured User-Agent |
| `venturebeat.com/category/ai/feed/` | 429 |

That leaves `trading` with one working RSS feed (Economic Times) plus NewsAPI.

**The content that does arrive is poor.** Real sources in the production
`news_cache` right now:

- **energy:** `Bringatrailer.com` (a car auction site), `Naturalnews.com`,
  `Wattsupwiththat.com`, `Dailymail.com`
- **tech:** `CBM (Comic Book Movie)`, `Deadline`, `Newsonjapan.com`

The cause is structural, not bad luck: `_is_trading_relevant` filters the
`trading` category only. **`tech` and `energy` have no relevance filter at
all**, so any NewsAPI keyword hit on "AI" or "energy" is accepted.

**Ordering is wrong for undated articles.** `get_news` orders
`published_at DESC` with no NULLS clause, so Postgres' `NULLS FIRST` default
puts undated articles above fresh ones. Currently latent — NewsAPI supplies
dates — but any RSS entry without `published_parsed` triggers it.

---

## 3. Layout

One main panel, two tabs. **News** is the default. **Changes** keeps the unread
badge so a firing event is visible without leaving News.

```
  Since                                  News  ·  Changes ⑶      [Catch up]
  ────────────────────────────────────────────────────────────────────────
   YOUR SYMBOLS                                                   4 new
   ● Reliance Q2 profit beats estimates on refining margins
     RELIANCE.NS · Economic Times · 2h ago
   ● Nvidia supply commentary lifts AI hardware names
     NVDA · Reuters · 4h ago

  ───────────────  Thursday, 9:42 pm — your last visit  ───────────────

   MARKETS        [Trading] [AI & Tech] [Energy]
   ○ RBI holds rates, signals data-dependent path
     Business Standard · Fri
```

**Your symbols** is a section, not a third tab. It is the differentiating
content and burying it behind another click defeats the point.

The category chips (Trading / AI & Tech / Energy) filter the **Markets**
section only. They do not affect **Your symbols**.

---

## 4. Symbol matching

Matching a headline to a ticker by string comparison is unreliable: `TCS`
occurs inside unrelated words, and `INFY` never appears in prose.

**We do not solve this ourselves.** `routes/ticker.py::_news` already fetches
per-symbol news from Yahoo's search API (`/v1/finance/search?q=<symbol>&
newsCount=8`) and it is proven in production. Yahoo performs the entity
resolution.

So symbol news is fetched per watchlist symbol from that endpoint and stored in
`news_cache` with a `symbol` column set. General category news keeps
`symbol IS NULL`.

**Consequence accepted:** coverage depends on Yahoo's tagging. A symbol Yahoo
tags poorly gets less news. That is a better failure than a fuzzy matcher
confidently attributing the wrong story to a holding.

---

## 5. Quality

Three changes, in the order they matter:

1. **Remove the four dead feeds.** They contribute nothing and cost a
   round trip each on every refresh.
2. **Extend relevance filtering to `tech` and `energy`.** The existing
   `_is_trading_relevant` becomes `_is_relevant(title, category)` driven by a
   per-category allow/block keyword list. `trading`'s existing lists are kept
   verbatim so its behaviour does not change.
3. **Source denylist.** A module-level set of hosts that NewsAPI keeps
   surfacing and that never carry market news: `naturalnews.com`,
   `wattsupwiththat.com`, `bringatrailer.com`, `dailymail.co.uk`,
   `comicbookmovie.com`, `deadline.com`. Matched on the article's `source`
   name, case-insensitively.

---

## 6. Ranking

A small, transparent, integer score computed at write time and stored on the
row. Not machine learning — the same philosophy as the detectors, so it can be
explained and tuned.

```
score = source_weight            # curated tier: 3 (wire/major), 2 (known), 1 (other)
      + 2 if symbol is not null  # it is about something the user holds
      + recency_bucket           # <2h: 3, <12h: 2, <48h: 1, else 0
      + corroboration            # +1 per additional source with a near-identical title
```

`SOURCE_WEIGHTS` is an explicit dict; anything unlisted scores 1. Corroboration
is computed within a single refresh batch by normalised-title grouping — no
cross-batch lookup, so it stays O(n) in the batch.

Markets news is ordered `score DESC, published_at DESC NULLS LAST`. Symbol news
is ordered `published_at DESC NULLS LAST` — for your own holdings, recency
matters more than a score.

---

## 7. Unread

News and Changes keep **separate baselines**. Catching up on news must not
silently mark a `RANGE_BREAK` as read; the two streams carry different stakes.

- Changes: `user_state.last_seen_at` (existing, unchanged)
- News: `user_state.news_last_seen_at` (new)

Unread for news is counted on `published_at` rather than `created_at`: unlike
detector events, a news article's publish time is genuine and does not shift
across intraday re-detections.

---

## 8. Schema

```sql
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS symbol TEXT;
ALTER TABLE news_cache ADD COLUMN IF NOT EXISTS score  INT NOT NULL DEFAULT 0;
CREATE INDEX IF NOT EXISTS news_cache_symbol_idx  ON news_cache (symbol, published_at DESC);
CREATE INDEX IF NOT EXISTS news_cache_ranked_idx  ON news_cache (category, score DESC, published_at DESC);

ALTER TABLE user_state ADD COLUMN IF NOT EXISTS news_last_seen_at TIMESTAMPTZ NOT NULL DEFAULT now();

-- news_cache retention: the table currently grows forever.
DELETE FROM news_cache WHERE published_at < now() - INTERVAL '30 days';
```

Retention is applied as a statement in `schema.sql` and repeated by the refresh
pipeline, so the table stays bounded without a separate job.

---

## 9. API

| Route | Purpose |
| --- | --- |
| `GET /news/symbols` | Articles for the caller's watchlist symbols, newest first, with `unread_count` and `news_last_seen_at` |
| `GET /news?category=` | Markets news for one category, ranked by score |
| `POST /news/seen` | Sets `news_last_seen_at = now()` |

`GET /news/symbols` and `POST /news/seen` require `X-Device-Key` via the
existing `current_user` dependency. `GET /news?category=` stays anonymous —
market news is not user-specific.

---

## 10. Refresh pipeline

`run_news_refresh()` gains a second phase:

```
categories  -> fetch RSS + NewsAPI  -> filter -> score -> upsert (symbol NULL)
watchlist   -> fetch Yahoo per-symbol news -> score -> upsert (symbol set)
            -> prune articles older than 30 days
```

Symbol fetches run through the existing `ThreadPoolExecutor` and are capped per
invocation so a large watchlist cannot exceed the function duration budget.
Both phases write through `insert_news`, which already upserts on
`url` — so the same article arriving from both a category feed and a symbol
lookup collapses to one row.

**Ambiguity resolved — and it requires a code change.** `insert_news` currently
upserts with `ignore_duplicates=True`, so a second arrival of the same url is
discarded entirely. That is correct for the category path (nothing new to
learn) but wrong for the symbol path: an article first seen via a category
feed would never gain its `symbol` tag.

The resolution is NOT to flip `ignore_duplicates` — that would let a
category-path arrival overwrite a good `symbol` with NULL. Instead the symbol
phase performs a targeted follow-up update after its upsert:

```sql
UPDATE news_cache SET symbol = <sym> WHERE url = <url> AND symbol IS NULL
```

So a tag is only ever added, never cleared, and the category path keeps its
cheap ignore-on-conflict behaviour.

---

## 11. Out of scope

- **Sentiment analysis.** Tempting and unreliable at this scale.
- **Article body extraction.** Headline plus the feed's own summary only.
- **Per-symbol news alerts.** News does not create `events` rows; the two
  streams stay separate. Joining them ("this move, this story") is a later
  phase.
- **A third "Your symbols" tab.** It is a section, by decision in §3.
- **Replacing the dead feeds with new sources.** Removing them is in scope;
  curating replacements is a research task, not an engineering one.

---

## 12. Phasing

**Phase A — quality and correctness** (independently shippable)
1. Remove dead feeds; extend relevance filtering to tech and energy; add the
   source denylist
2. `published_at DESC NULLS LAST` everywhere
3. Retention: prune articles older than 30 days

**Phase B — symbol news**
4. Schema: `symbol`, `score`, `news_last_seen_at`, indexes
5. Yahoo per-symbol fetch wired into `run_news_refresh`
6. `GET /news/symbols`, `POST /news/seen`

**Phase C — ranking and UI**
7. Scoring at write time; ranked ordering for markets news
8. Tabs (News / Changes), the Your-symbols section, the news divider

---

## 13. Testing

- **Relevance filter and denylist** — pure functions over titles and source
  names; table-driven tests including the real junk observed in production
  (`Bringatrailer.com`, `CBM (Comic Book Movie)`).
- **Scoring** — pure function over an article dict; tests pin each component
  and the corroboration grouping.
- **Ordering** — a test with a NULL `published_at` row asserting it sorts
  last, not first.
- **Routes** — extend the existing `TestClient` + patched-database pattern;
  cover identity-scoping on `/news/symbols` and the separate news baseline.
- **Symbol fetch** — recorded Yahoo response; assert `symbol` is set and that
  re-running inserts nothing new.

The existing 121 tests must continue to pass.

---

## 14. Risks

| Risk | Mitigation |
| --- | --- |
| Yahoo per-symbol news is rate-limited on a large watchlist | Cap symbols per invocation; results persist, so coverage catches up across refreshes |
| Yahoo tags a symbol poorly, so "Your symbols" looks empty | Section states its own emptiness honestly rather than silently collapsing |
| Denylist becomes a maintenance burden | Keep it small and evidence-based; the relevance filter is the primary defence |
| Corroboration grouping mis-merges distinct stories with similar titles | Normalise conservatively (lowercase, strip punctuation, first 60 chars); it only adds +1 to a score |
