# shoponline — NOVAHAUS store prototype

A small, dependency-free online shop for **NOVAHAUS**, calm small-space organisation for UK flats and home offices. It follows the NOVAHAUS Business Blueprint (draft, awaiting approval).

> Status: **prototype for the "Desk Reset" validation test.** Every price and cost is an ESTIMATE until real supplier quotes replace it. No live payments.

## Run it on your PC (Windows): quick start

1. Install these once, and tick **"Add python.exe to PATH"** when installing Python:
   - [Git](https://git-scm.com/download/win)
   - [Python 3.11+](https://www.python.org/downloads/)
   - [Node.js LTS](https://nodejs.org/)
2. Open **Command Prompt** and run:
   ```bat
   cd %USERPROFILE%
   git clone https://github.com/th3emis31/shoponline.git
   cd shoponline
   run-local.cmd
   ```
3. The first run takes a few minutes, because it installs packages, creates the database and adds the products. Two server windows open, and then your browser opens:
   - Shop: http://localhost:3000
   - Admin: http://localhost:3000/admin
   - API docs: http://localhost:8000/docs
4. Create your personal admin login. In the same folder, run this and type a password (at least 12 characters) when asked:
   ```bat
   admin-user.cmd create you@example.com --role owner
   ```
   Then sign in at http://localhost:3000/admin with that email and password. Use `--role staff` for helpers: staff can only manage orders, and can't see costs, prices, the funnel or the audit log.
5. To stop, run `stop-local.cmd`. It stops **only the shop**: only programs started from the `shoponline` folder. Other programs on your PC are never touched. To start again, run `run-local.cmd`. It's safe to re-run, never deletes your data, and tells you if the shop is already running.
   If another program already uses port 8000 or 3000, the shop leaves it alone and moves to the next free port. It prints the address to use, for example http://localhost:3001.

### Backups

```bat
backup.cmd                          & REM make a backup and check it restores (saved in backend\backups)
backup.cmd --list                   & REM list backups
backup.cmd --restore FILE --yes     & REM put a backup back (stop the shop first; the current data is saved first)
```

To back up automatically every night at 2am, run this once:

```bat
schtasks /Create /SC DAILY /ST 02:00 /TN "NOVAHAUS backup" /TR "\"%USERPROFILE%\shoponline\backup.cmd\""
```

Copy `backend\backups` to an external drive or cloud storage regularly. Backups are never deleted unless you add `--keep N`, which keeps the newest N.

By default it uses a local SQLite file (`backend\novahaus.db`) and payments are off. To use PostgreSQL or Stripe test mode, edit `backend\.env` (see `backend\.env.example`).

## Features (Node prototype, `src/`)
- Catalogue of the 4 shortlisted test products plus the Desk Reset bundle (prices in £, inc. VAT)
- Cart: add or remove items, with stock and quantity limits
- Guest checkout: asks only for name, email and address; the total is shown before ordering
- Order lookup by ID
- Unit-economics model (Blueprint section L): net revenue ex-VAT, Stripe UK fee, returns allowance, contribution before and after ads, break-even ROAS
- Internal cost fields are never exposed through the public API

## Run
Requires Node.js 18+. There is nothing to install.

```bash
npm start      # http://localhost:3000
npm test       # runs the unit and API tests
```

## API
| Method | Path | Body |
|---|---|---|
| GET | `/api/products` | |
| GET | `/api/products/:id` | |
| POST | `/api/carts` | |
| GET | `/api/carts/:id` | |
| POST | `/api/carts/:id/items` | `{ productId, quantity }` |
| DELETE | `/api/carts/:id/items/:productId` | |
| POST | `/api/carts/:id/checkout` | `{ name, email, address }` |
| GET | `/api/orders/:id` | |

## Backend (FastAPI + PostgreSQL), Blueprint section K option C

The `backend/` folder holds the production-track API. It has the same shop features as the prototype, plus:
- Data is kept in a database: PostgreSQL in production, SQLite for quick local runs
- Shipping appears in the cart before checkout (£3.95, free over £50; both are ASSUMPTIONS set in `.env`)
- Checkout is all-or-nothing, and an atomic stock decrement means it never oversells
- Order tracking needs both the order ID and the customer's email
- Admin endpoint `GET /api/admin/products/{id}/economics?cac=` returns the live break-even ROAS. It is protected by `X-Admin-Token`, and it stays disabled until you set `ADMIN_TOKEN`
- Internal cost fields never appear in the public API

### Payments (Stripe hosted Checkout)
- With no `STRIPE_SECRET_KEY` set, checkout places the order without payment. This mode is for development only.
- With a **test** key set, checkout reserves the stock, creates the order as `pending_payment`, and returns a `checkout_url` for Stripe's hosted payment page. Card data never touches our server.
- `POST /api/webhooks/stripe` rejects any request without a valid signature, and it stays disabled until `STRIPE_WEBHOOK_SECRET` is set. Each event is applied only once.
  - A paid order becomes `paid` only if the amount and currency match the order exactly. Otherwise it goes to `payment_review` for a human to check.
  - An expired or failed payment releases the reserved stock. A late event never cancels an order that is already paid.
- If Stripe is down, the order is cancelled and the stock released straight away.
- To test locally: `stripe listen --forward-to localhost:8000/api/webhooks/stripe`, then use card `4242 4242 4242 4242`.

### Database changes
Alembic owns the schema. After you change `app/models.py`, run `alembic revision --autogenerate -m "..."`, review the file it generates, then run `alembic upgrade head`. A test fails if the models and the migrations ever drift apart.

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                                 # then edit DATABASE_URL / ADMIN_TOKEN
alembic upgrade head                                   # creates/updates the database tables
python -m app.seed                                     # adds the 5 products (safe to re-run)
uvicorn app.main:app --reload                          # http://localhost:8000/docs
python -m pytest -q                                    # tests (set TEST_DATABASE_URL to run them on PostgreSQL)
```

CI (`.github/workflows/ci.yml`) runs the Node tests and the backend tests on SQLite and on PostgreSQL 16 for every push.

## Storefront (Next.js), Blueprint section H

The `frontend/` folder holds the customer-facing site. It is rendered on the server, and it talks to the backend through a same-origin `/api` proxy. The proxy reads `API_URL` on each request, so one build works in any environment, and it blocks the admin endpoints.

**Pages:**
- **Shopping:** Home, Shop, Product, Cart with checkout, Order confirmation, Track order
- **Information:** About, Contact, FAQ, Shipping, Returns
- **Legal:** Privacy, Terms, Cookies, plus a 404 page

Checkout follows the blueprint's rules: guest checkout, only name, email and address asked for, delivery cost and total shown before payment, and no marketing box.

Honesty rules from the blueprint are built in. There are no reviews, countdown timers or "only X left" badges. Specs and photos will come from the real sample, never stock images. A "Preview site" banner stays up until `launchReady` is set in `lib/site.ts`.

```bash
cd frontend
npm install
npm run dev            # http://localhost:3000 (backend must run on :8000)
npm run typecheck && npm test                  # type check + unit tests
npm run build && npm run test:e2e              # browser tests, desktop + mobile (these start the backend themselves)
```

**Before launch:** fill in every `TODO` in `frontend/lib/site.ts` and on the Shipping, Returns and legal pages. The legal pages are placeholders that need professional review.

## Automation: automatic within limits (Blueprint section J)

The shop runs these jobs **by itself while it is running**. Admin > Automation shows each job's last result and has a **Run now** button for each one. You can also run them from Command Prompt:

```bat
automation.cmd status              & REM jobs, limits, last runs
automation.cmd run                 & REM run every job now
automation.cmd run low_stock       & REM run one job
automation.cmd report              & REM latest daily report
```

| Job | When | What it does |
|---|---|---|
| close abandoned checkouts | every 15 min | Checks unpaid checkouts older than 90 minutes against Stripe. A payment whose webhook was missed is marked paid. An abandoned checkout is closed at Stripe and its stock released. If Stripe errors, the order is left alone. |
| low stock | every 60 min | When stock reaches a product's reorder point, it suggests a reorder. |
| margin guard | every 6 h | If a product's margin falls below 35% (for example after a cost update), it suggests the lowest price that restores it. |
| backup | daily, after 02:00 UTC | Makes a backup and checks that it restores. |
| daily report | daily, after 06:00 UTC | Yesterday's sales, estimated contribution and funnel, plus what needs attention. |

**Limits**, set in `backend\.env`:
- A reorder runs automatically only up to **£100 each and £300 per week**.
- A price change runs automatically only if it is a **rise of up to 5%**. The automation **never lowers prices**.
- Anything bigger waits in **Admin > Approvals** for one click.
- Every automatic action is in the audit log as `automation`.
- A reorder creates a **purchase order** ("ready to send"). Marking it *received* adds the stock.
- `AUTOMATION_ENABLED=false` turns the schedule off. The Run now buttons and `automation.cmd` still work.

## Dropshipping: sell without buying stock

Each product can be set to **"My own stock"** or **"Dropship"** in Admin > Products. For dropship you enter:
- the supplier's name
- the supplier's product link
- the supplier's price per unit, **including delivery to your customer**
- the delivery time customers see, for example "7-12 working days"

How a dropship order works:
1. The customer pays you, through Stripe.
2. The shop creates a **supplier order** in **Admin > Supplier orders**. It shows what to buy, the supplier link, the customer's delivery address, and your **estimated profit**: sale ex VAT, minus the supplier price, minus the Stripe fee.
3. You buy from the supplier, using the customer's address, **with the money the customer already paid**. Mark it *Ordered* with the supplier's order number, then *Shipped* with the tracking number.

Dropship products need no stock of your own. Cancelling or reversing an unpaid order never creates "phantom" stock. Margin checks and the daily report use the supplier price.

**Be honest with customers.** Show the real delivery time, and remember UK consumer rules (14-day returns) still apply to you as the seller, even if the supplier ships.

## Safety guarantees

These came out of an independent review and are covered by regression tests (`backend/tests/test_review_fixes.py`).

**Orders and stock**
- Every order status change is a single "only if it's still X" database update, so a webhook, the automation and an admin click can't clash.
- Stock is held or given back through a per-order flag, so it can never be released twice.
- Accepting a reviewed late payment takes the stock again, or is refused if there isn't enough.
- Receiving a purchase order adds stock with an atomic increment, so a sale at the same moment is never lost, and a double click can't add stock twice.
- Deactivated products can't be checked out.

**Approvals and automation**
- A recommendation can be approved only once.
- Each automation job runs one copy at a time, whether started by the scheduler, Run now, the CLI or several server processes.

**Payments**
- Unpaid checkouts still being processed by the bank are left alone.
- Cancelling an unpaid order closes its Stripe checkout first.
- If the server stops mid-checkout, the order is recovered later.
- With `ENVIRONMENT=production`, checkout refuses to run without Stripe, and the API docs are hidden.

**Sign-in and roles**
- Staff can only ship orders. Accepting payments and cancelling are for the owner only.
- Sign-in shows one generic message for every failure, and the failed-attempt counter is atomic.
- Sign-in, the waitlist, carts, events and order lookup are rate-limited.
- The shared `ADMIN_TOKEN` stops working once a personal owner login exists.

**Local running**
- The local shop listens only on this PC (127.0.0.1).
- `stop-local` matches the exact shop folder.

## SEO (Blueprint weeks 7-8)

- `/sitemap.xml` lists every page and product. `/robots.txt` points search engines to it.
- Product pages carry schema.org `Product` data: price in GBP and stock status. They deliberately carry **no ratings or reviews**, which the blueprint forbids until real ones exist.
- Each product page has its own title, description, canonical link and social-sharing tags.
- Cart, order, track and admin pages are never indexed.
- **While `launchReady` is `false`** in `frontend/lib/site.ts`, the whole site asks search engines not to index it. At launch, set `launchReady: true` and set `SITE_URL` to your real domain.

## Admin and analytics

- **Admin** is at `/admin`. Each person signs in with their own email and password:
  - **Accounts:** create them with `admin-user.cmd` (Windows) or `python -m app.admin_users`.
  - **Roles:** an *owner* sees everything; *staff* see Orders only.
  - **Security:** passwords are stored hashed (scrypt), 5 wrong attempts lock the account for 15 minutes, and sessions last 8 hours.
  - **Shared token:** the `ADMIN_TOKEN` from `backend/.env` still works as an emergency owner login.
- The admin area has four tabs:
  - **Orders:** mark orders shipped or cancelled. The allowed status changes are enforced, cancelling releases the stock, and paid orders can't be cancelled here (refunds go through Stripe first).
  - **Products:** price, landed cost, stock and visibility, plus each product's live contribution and **break-even ROAS**.
  - **Funnel:** conversion over the last 30 days.
  - **Audit log:** every sign-in and every admin change, with who made it, the before and after values, and the reason given.
- **Funnel tracking:** view product → add to cart → begin checkout → purchase. It stores anonymous counts only: no cookies, no visitor IDs, no personal data. Purchases are recorded by the server, so a browser can't fake them.
- **Safety net:** if a payment arrives for an order that was already cancelled, the order goes to `payment_review` for a human to check, rather than being ignored.

## Next steps (pending blueprint approval)
- Pick the stack: Blueprint section K recommends FastAPI + PostgreSQL + Next.js; Shopify is the faster alternative
- Deploy: production host, domain, live Stripe keys (launch gate, section O)
- Real product specs and photos once samples arrive
