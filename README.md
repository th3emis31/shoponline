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

## Next steps (pending blueprint approval)
- Pick the stack: Blueprint section K recommends FastAPI + PostgreSQL + Next.js; Shopify is the faster alternative
- Stripe hosted checkout with verified webhooks
- Persistent database (the data is in memory for now)
- Launch pages: About, Contact, FAQ, Shipping, Returns, Legal
