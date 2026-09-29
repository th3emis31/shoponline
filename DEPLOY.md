# Put NOVAHAUS online for £0

This puts the shop on a free web address that anyone in the world can open, for example `https://novahaus-shop.onrender.com`.

**What you use (all free):**
- **Render**, for the shop and the backend. Its free plan allows commercial use.
- **Neon**, for the database. Its free plan doesn't expire.
- **Stripe**, for card payments. There's no monthly fee; Stripe only takes a fee per sale.

**One honest limitation of free hosting:** a free Render server goes to sleep after about 15 minutes with no visitors, and the first visitor after that waits about a minute. When sales come in, you can upgrade the shop service (about $7 a month) and it stays awake.

---

## Step 1: GitHub (the shop's code)

1. On https://github.com/th3emis31/shoponline, merge the open pull request into `main`.
2. Recommended: make the repository **Private** under Settings → General → Danger Zone. Render can still read it.

## Step 2: Neon (the database), about 3 minutes

1. Go to https://neon.com and sign up. Using your GitHub account is easiest.
2. Create a project named `novahaus`, and pick a region in Europe (for example London or Frankfurt).
3. On the project dashboard, click **Connect**.
4. Copy the **connection string**. It starts with `postgresql://…` and ends with `?sslmode=require`.
5. Keep it somewhere private. It's a password.

## Step 3: Render (the website), about 10 minutes

1. Go to https://render.com and sign up **with GitHub**.
2. Click **New → Blueprint**, pick the `shoponline` repository, then click **Apply**. Render reads `render.yaml` and creates two services: **novahaus-api** and **novahaus-shop**.
3. Render asks for a few values. For now:

   | Service | Setting | What to enter |
   |---|---|---|
   | novahaus-api | `DATABASE_URL` | the Neon connection string from step 2 |
   | novahaus-api | `PUBLIC_BASE_URL` | leave empty for now |
   | novahaus-api | `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET` | leave empty for now |
   | novahaus-shop | `API_URL` | leave empty for now |
   | novahaus-shop | `SITE_URL` | leave empty for now |
   | novahaus-shop | `SHOP_LEGAL_NAME`, `SHOP_ADDRESS`, `SHOP_EMAIL` | your business name, address and support email (UK law requires these before you sell) |

4. Wait for both services to show **Live**. The first build takes a few minutes.
5. Copy each service's address from the top of its page. It looks like `https://novahaus-api.onrender.com` (yours may have a few extra letters).
6. Fill in the addresses:
   - **novahaus-shop → Environment:**
     - `API_URL` = the **novahaus-api** address
     - `SITE_URL` = the **novahaus-shop** address
   - **novahaus-api → Environment:**
     - `PUBLIC_BASE_URL` = the **novahaus-shop** address
   - Save. Render redeploys automatically.
7. Open the **novahaus-shop** address. Your shop is online, in **preview mode**, collecting waitlist sign-ups.

## Step 4: Your admin login

1. In Render, open **novahaus-api → Environment**, and reveal and copy **`ADMIN_TOKEN`**. It's a one-time setup key.
2. Open `<your shop address>/admin`, click **"Use the shared admin token instead"**, and paste it.
3. Go to the **Team** tab and add **yourself** as **Owner**, with a password of at least 12 characters.
4. Sign out, then sign in with your email and password. From now on the setup key no longer works, which is safer.

## Step 5: Test payments (Stripe test mode, no real money)

1. Sign up at https://stripe.com, and keep the **Test mode** switch on.
2. **Developers → API keys:** copy the **Secret key** (`sk_test_…`), and put it in **novahaus-api → `STRIPE_SECRET_KEY`**.
3. **Developers → Webhooks → Add endpoint:**
   - URL: `<novahaus-api address>/api/webhooks/stripe`
   - Events:
     - `checkout.session.completed`
     - `checkout.session.expired`
     - `checkout.session.async_payment_succeeded`
     - `checkout.session.async_payment_failed`
   - Copy the **Signing secret** (`whsec_…`) into **novahaus-api → `STRIPE_WEBHOOK_SECRET`**.
4. Place a test order in your shop. Pay with card `4242 4242 4242 4242`, any future date and any CVC. The order should show **paid** in Admin → Orders.

## Step 6: Dropshipping (sell without buying stock)

For each product, go to **Admin → Products → "How it's fulfilled" → Dropship** and fill in:
- the supplier name
- the supplier product link
- the supplier's price per unit **including delivery to your customer**
- an **honest** delivery time, for example "7-12 working days"

When a customer pays, **Admin → Supplier orders** shows what to buy, where, the customer's address and your profit. Buy it with the money the customer paid, then record the supplier's order number and tracking.

## Step 7: Open the shop

When you're ready to take real orders:
1. In Stripe, switch to **live** keys and create the live webhook, the same way as step 5.
2. Put the live keys into **novahaus-api**.
3. Set **novahaus-shop → `LAUNCH_READY`** to `true`. The preview banner goes away and search engines may list the shop.

**Before step 7, please make sure:**
- The Privacy, Terms and Cookies pages have been properly written. They're placeholders now.
- Your Returns page matches what you'll actually do. UK customers can cancel within 14 days even when a supplier ships the item.
- You know the delivery times and quality of your suppliers. Order a sample yourself when you can.

---

**Custom domain (optional, later):** a name like `novahaus.co.uk` costs a few pounds a year. In Render: **novahaus-shop → Settings → Custom Domains**. Then update `SITE_URL` and `PUBLIC_BASE_URL`.
