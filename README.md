# Tap Payments take-home: saved card and recurring payment

A small Flask app that takes a card payment with Tap's Web Card SDK v2, saves the card, and then charges the saved card again without 3DS.

The page is deliberately basic. My focus was the payment flow.

## How the flow works

### 1. First payment (customer-initiated, with 3DS)

1. The Card SDK draws the card form using the public key. When the customer clicks **Pay**, Tap turns the card into a token.
2. The browser sends only the token ID to `POST /pay`.
3. The server creates a charge with `save_card: true`, `customer_initiated: true` and `threeDSecure: true`, along with the customer's name, email and phone.
4. The customer is sent to the 3DS page from `transaction.url`.
5. Tap sends them back to `/redirect?tap_id=...`. The server calls Retrieve Charge and only accepts `CAPTURED`.
6. From that response it stores `customer.id`, `card.id` and `payment_agreement.id`, plus the card brand and last 4 digits.

### 2. Saved card

The home page shows the saved card's brand and last 4 digits. The customer selects it and clicks **Pay with saved card**.

### 3. Recurring payment (merchant-initiated, no 3DS)

1. `POST /pay-saved` creates a new token from the card ID and customer ID. Tokens are single-use and expire after 5 minutes, so each payment gets its own.
2. The server creates a charge with `customer_initiated: false`, `threeDSecure: false`, `save_card: false`, `customer.id` and `payment_agreement.id`.
3. It calls Retrieve Charge and again only accepts `CAPTURED`.

The payment agreement comes from the first, authenticated payment. It is what allows the later charge to go through without 3DS.

In this demo the customer starts the second payment with a button, and it is sent as merchant-initiated as the task describes. In a real subscription, the merchant's system would trigger it on a schedule.

## Charge IDs (sandbox, from a local run)

| Payment | Charge ID |
|---|---|
| First payment (CIT) | `chg_TS06A4720261825Xt4s2511035` |
| Recurring payment (MIT) | `chg_TS06A3720261838p4J42511446` |

## Run it locally

You need Python 3 and Tap test keys. Commands are for Windows PowerShell.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
copy .env.example .env
```

Fill in `.env`:

| Variable | What it is |
|---|---|
| `TAP_SECRET_KEY` | Secret test key, used only by the server |
| `TAP_PUBLIC_KEY` | Public test key, used by the card form |
| `TAP_MERCHANT_ID` | Your merchant ID |
| `TAP_BASE_URL` | `https://api.tap.company/v2` |
| `BASE_URL` | Where the app is reachable, for example `http://localhost:5000`, with no slash at the end |
| `FLASK_DEBUG` | `1` on your own computer, `0` on a host |

Then start it and open http://localhost:5000:

```powershell
.venv\Scripts\python app.py
```

## Test cards

Use any future expiry (for example `01/39`) and CVC `100`.

| Card | Result |
|---|---|
| Mastercard `5123450000000008` | Succeeds after 3DS and saves the card |
| Visa `4508750015741019` | Declined, shows the failure message |

## Files

| File | Purpose |
|---|---|
| `app.py` | Routes, success check, failure message and storage |
| `tap_client.py` | All calls to Tap's API |
| `templates/index.html` | The page |
| `static/app.js` | Card SDK setup and sending the token |

## How I handled the important parts

- **Secret key:** it stays on the server. The page only receives the public key and merchant ID.
- **Card details:** they go straight to Tap. My server only sees token and card IDs, the brand and the last 4 digits.
- **Success:** coming back to the redirect page proves nothing. A payment counts only if Retrieve Charge says `CAPTURED` with the expected amount and currency.
- **Redirect:** the server only accepts the charge ID it created itself.
- **Amount:** set on the server. The browser sends only a token or a card ID.
- **References:** every charge gets a new `reference.transaction` and `reference.order`.
- **Errors:** failed payments show a plain message with Tap's code and description. A failed payment never replaces the saved card.
- **Keys:** loaded from `.env`, which is not in Git.

## Issues I ran into

**The card form was blank.** The SDK threw `Cannot read properties of undefined (reading 'theme')`. The docs list `interface` as optional, but SDK 1.0.2 crashed without it. I found it in the browser console and fixed it by passing `interface`.

## Limitations

- Storage is a single `data.json` file with one saved card. Everyone who opens the page sees the same card, and a redeploy clears it. A real merchant would use a database tied to logged-in users.
- The customer's details are fixed demo values.
- Clicking **Pay with saved card** twice quickly could charge twice. Tap's `reference.idempotent` field is one way to prevent that.
