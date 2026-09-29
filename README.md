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

```bash
cd backend
python -m venv .venv && .venv\Scripts\activate      # Windows (macOS/Linux: source .venv/bin/activate)
pip install -r requirements.txt
copy .env.example .env                                 # then edit DATABASE_URL / ADMIN_TOKEN
python -m app.seed                                     # creates tables and adds the 5 products
uvicorn app.main:app --reload                          # http://localhost:8000/docs
python -m pytest -q                                    # tests (set TEST_DATABASE_URL to run them on PostgreSQL)
```

CI (`.github/workflows/ci.yml`) runs the Node tests and the backend tests on SQLite and on PostgreSQL 16 for every push.

## Next steps (pending blueprint approval)
- Pick the stack: Blueprint section K recommends FastAPI + PostgreSQL + Next.js; Shopify is the faster alternative
- Stripe hosted checkout with verified webhooks
- Alembic migrations (tables are created by `app.seed` for now)
- Next.js storefront on top of the backend API
- Launch pages: About, Contact, FAQ, Shipping, Returns, Legal
