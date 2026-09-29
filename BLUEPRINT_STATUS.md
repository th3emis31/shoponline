# NOVAHAUS Blueprint: build status

This tracks every section of the NOVAHAUS Business Blueprint against what the code does. Update it with each change.

**Legend:**
- ✅ built and tested
- 🟡 partly built
- ⬜ not built yet
- 👤 needs you (a decision, an account, a supplier, a professional)

| § | Blueprint section | Status | Where / notes |
|---|---|---|---|
| A | Market opportunity | 👤 | Research, not code. The facts are cited in the blueprint. |
| B | Niche (small-space organisation) | ✅ | The catalogue and copy follow option 1. |
| C | Target customers | 🟡 | The copy answers the personas' objections (FAQ, delivery times, returns). Persona testing needs real traffic 👤 |
| D | Product-selection framework | ✅ | Admin shows contribution and break-even ROAS for each product. The margin guard enforces gate 2 (≥35%). |
| E/F | 10 concepts / scorecard / test shortlist | ✅ | The 4 shortlisted products plus the Desk Reset bundle are seeded. Costs are ESTIMATES until supplier quotes 👤 |
| G | Brand positioning | ✅ | Calm, honest copy. There are no fake reviews, timers or "only X left" badges, and illustrations are labelled. |
| H | Website: launch pages | ✅ | Home, Shop, Product, Cart and checkout, About, Contact, FAQ, Shipping, Returns, Track, legal pages, 404 |
| H | Shop "filter by room" | ✅ | `/shop?room=home-office` (also living room and bedroom). Every room page is in the sitemap |
| H | Contact **form** (not only email) | ✅ | `/contact`, with a spam trap and rate limit. The customer gets an automatic acknowledgement |
| H | Buying guides / blog | ✅ | `/guides`: 3 practical guides with no invented statistics (the screen-height guide cites HSE guidance). Each links to the matching products |
| H | Social proof only once real reviews exist | ✅ | Verified-buyer reviews through a signed link (order email and order page). You check them in Admin > Reviews, and negative reviews can't be hidden. The product page and Google rating appear only after the first published review |
| I | Waitlist smoke test | ✅ | "Notify me" with explicit consent, and sign-ups per product in admin |
| I | Email flows: welcome 5, abandoned cart 4, post-purchase 5, win-back 1 | ✅ | `services/emails.py`, plus order confirmation, shipped and the launch email. You read them in Admin > Emails; they're sent once SMTP is set (DEPLOY.md step 6b) |
| I | Consent rules (opt-in, no pre-ticked boxes) | ✅ | Unticked boxes; the waitlist only gets the launch email; consent is re-checked before every send; one-click unsubscribe |
| I | Per-campaign tracking: CTR, CPC, CAC, ROAS, **contribution after ads** | ✅ | Admin > Campaigns. Ad links carry `utm_source` / `utm_campaign`; you type in the ad cost; each campaign gets a plain-English verdict. No visitor tracking; only the campaign name is kept, for that tab |
| I | Google Shopping product feed | ✅ | `/feed/google.xml`. A product appears only once a **real photo** is in `frontend/public/products/` 👤 |
| J | Approval gate + audit log | ✅ | Admin > Approvals, and the audit log with who did what |
| J | Automation within limits | ✅ | Reorders, the margin guard, abandoned checkouts, backups, the daily report |
| J | AI provider interface (local Ollama / external API / future) | ✅ | `services/ai/providers.py`. Built-in rules are free and the default; Ollama runs locally; any OpenAI-compatible API works (personal data removed, daily cap). If the AI service fails, the built-in rules are used |
| J | Agents: Research, Product, Marketing, Analytics, Customer, Inventory, SEO | ✅ | All seven are in Admin > AI assistants. The Customer agent drafts replies inside Support |
| J | FACT / ASSUMPTION / ESTIMATE / HYPOTHESIS labels on every output | ✅ | Enforced in code: an unlabelled AI line becomes an unverified HYPOTHESIS |
| J | AI memory (ai_tasks, ai_memory, business_decisions) + call logging | ✅ | Approved outputs go into memory and the decision log. Every AI call is logged by size, time and result, without storing prompts |
| K | FastAPI + PostgreSQL + Next.js + Stripe hosted checkout | ✅ | |
| K | Admin: separate login, role-based access | ✅ | Owner and staff roles, and the Team tab |
| K | Background jobs | ✅ | Built-in scheduler, one runner per job |
| K | Secrets in `.env`, none in Git | ✅ | |
| K | Backups + restore test | ✅ | `backup.cmd`, and the nightly job |
| K | Tests: unit, API, E2E | ✅ | pytest, Vitest, Playwright |
| L | Unit economics model | ✅ | `services/unit_economics.py`; matches the worked examples |
| M | 90-day roadmap | 👤 | A plan for you to follow |
| N | Risk register | 🟡 | The technical risks are mitigated in code; the business risks are 👤 |
| O | Launch criteria: 14 gates tracked in admin | ✅ | Admin > Launch checklist: all 14 blueprint gates. Automatic checks come from the shop's data, and you confirm the rest with evidence (audited). Your confirmation can't turn a failing check green |
| O | Checkout, payments, webhooks, refunds tested | 🟡 | Test mode is built. Refunds happen in Stripe 👤 |
| O | Analytics funnel | ✅ | |
| O | Customer support: inbox, reply templates, 1-business-day target | ✅ | Admin > Support (owner and staff): 5 reply templates, overdue flags and an on-time rate. The daily report lists messages waiting |
| O | Mobile Lighthouse performance ≥ 90 | ✅ | Measured locally (Lighthouse 12, mobile) on home, shop, product, guides, contact and cart: performance 97–100, accessibility 100, best practices 100. SEO is lower only because the preview blocks indexing on purpose. Re-measure the live shop at pagespeed.web.dev 👤 |
| O | Legal pages professionally reviewed; product safety files | 👤 | |
| + | Dropshipping (added at your request) | ✅ | Supplier orders with profit per order |
| + | Free hosting (Render + Neon) | ✅ | See `DEPLOY.md` |
