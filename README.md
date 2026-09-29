# shoponline — NOVAHAUS store prototype

A small, dependency-free online shop for **NOVAHAUS**, calm small-space organisation for UK flats and home offices. It follows the NOVAHAUS Business Blueprint (draft, awaiting approval).

> Status: **prototype for the "Desk Reset" validation test.** Every price and cost is an ESTIMATE until real supplier quotes replace it. No live payments.

## Features
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

## Next steps (pending blueprint approval)
- Pick the stack: Blueprint section K recommends FastAPI + PostgreSQL + Next.js; Shopify is the faster alternative
- Admin app (orders, stock, live break-even ROAS)
- Analytics funnel events: view → add-to-cart → checkout → purchase
- Real product specs and photos once samples arrive
