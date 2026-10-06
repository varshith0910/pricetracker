# Price Tracker

Track Amazon product prices, store price history, and get email alerts when a price hits your target. Users sign in with Google; the API runs on [FastAPI](https://fastapi.tiangolo.com/) with a background job that rechecks prices every 6 hours.

## Features

- Google OAuth sign-in (session cookie)
- Add Amazon product URLs with a target price
- Automatic price checks every 6 hours (APScheduler)
- Manual price check endpoints
- Price history per product
- Email alerts when price drops to or below your target (SMTP)

## Requirements

- Python 3.10+
- Google Cloud OAuth client (Web application) with redirect URI matching `GOOGLE_REDIRECT_URI`
- SMTP credentials if you want email alerts (e.g. Gmail app password)

## Setup

1. Clone the repository and create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate   # Windows
   # source .venv/bin/activate   # macOS/Linux
   pip install -r requirements.txt
   ```

2. Copy environment template and fill in values:

   ```bash
   copy .env.example .env   # Windows
   # cp .env.example .env   # macOS/Linux
   ```

   | Variable | Required | Description |
   |----------|----------|-------------|
   | `SESSION_SECRET` | Yes | Random string for signing session cookies |
   | `GOOGLE_CLIENT_ID` | Yes | Google OAuth client ID |
   | `GOOGLE_CLIENT_SECRET` | Yes | Google OAuth client secret |
   | `GOOGLE_REDIRECT_URI` | Yes | e.g. `http://localhost:8000/auth/google/callback` |
   | `DATABASE_URL` | No | Default: `sqlite:///price_tracker.db` |
   | `EMAIL_ADDRESS` / `EMAIL_PASSWORD` | For alerts | SMTP sender credentials |
   | `SMTP_HOST` / `SMTP_PORT` | No | Default: Gmail SSL on port 465 |
   | `SESSION_HTTPS_ONLY` | No | Set `true` behind HTTPS in production |

3. Run the server from the project root:

   ```bash
   python main.py
   ```

   Or:

   ```bash
   uvicorn api.main:app --reload --host 127.0.0.1 --port 8000
   ```

4. Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## Authentication flow

1. Visit `GET /auth/google` in a browser (or follow the redirect from your frontend).
2. After Google sign-in, you are redirected to `/me` with a session cookie.
3. Use the same browser session (or forward cookies) for protected routes.
4. `POST /auth/logout` clears the session.

## API overview

| Method | Path | Auth | Description |
|--------|------|------|-------------|
| GET | `/` | No | Health message |
| GET | `/auth/google` | No | Start Google login |
| GET | `/auth/google/callback` | No | OAuth callback |
| POST | `/auth/logout` | No | Log out |
| GET | `/me` | Yes | Current user profile |
| POST | `/products` | Yes | Track product (`url`, `target_price`) |
| GET | `/products` or `/trackings` | Yes | List your tracked products |
| GET | `/products/{product_id}` | Yes | One tracked product |
| GET | `/products/{product_id}/history` | Yes | Price history |
| POST | `/products/{product_id}/check` | Yes | Check one product now |
| POST | `/products/check` | Yes | Check all your products now |
| PUT | `/products/{product_id}/target` | Yes | Update target price |
| DELETE | `/products/{product_id}` | Yes | Stop tracking |
| GET/PUT/DELETE | `/trackings/{tracking_id}` | Yes | Same by tracking ID |

**Example — add a product** (after logging in via browser, use cookies or a client that stores the session):

```json
POST /products
{
  "url": "https://www.amazon.in/dp/EXAMPLE",
  "target_price": 999.0
}
```

## Project layout

```
price-tracker/
├── main.py                 # Dev entrypoint (uvicorn)
├── api/main.py             # FastAPI app, routes, auth
├── database/               # SQLAlchemy models and engine
├── scraper/amazon.py       # Amazon page scraper
├── services/
│   ├── price_checker.py    # Scrape, history, alerts
│   ├── scheduler.py        # 6-hour background checks
│   ├── email_service.py    # SMTP price-drop emails
│   └── google_auth.py      # Authlib Google OAuth
└── requirements.txt
```

## How price checks work

1. The scheduler calls `check_all_products()` every 6 hours for all products in the database.
2. Each check scrapes the Amazon URL, compares to the latest stored price, appends a `PriceHistory` row, and updates `Product.current_price`.
3. For each user tracking that product, if the new price is at or below their `target_price` and no alert was sent yet, an email is sent and `alert_sent` is set. If the price rises above the previous check, `alert_sent` resets so a future drop can notify again.

User-triggered checks (`POST /products/check`) only run for products that user is tracking.

## Limitations and notes

- **Amazon only** — the scraper expects Amazon product pages (title/price selectors). Other sites are not supported.
- **Scraping is fragile** — Amazon HTML changes, bot detection, or regional pages can break price extraction or block requests.
- **Email** — alerts fail silently in logs if `EMAIL_ADDRESS` / `EMAIL_PASSWORD` are missing or invalid.
- **Shared products** — the same URL is stored once in `products`; multiple users can track it with different target prices.
- **SQLite** — fine for local use; for production, set `DATABASE_URL` to PostgreSQL or another server-backed database (SQLite-specific migration logic only runs for legacy schemas).

## License

No license file is included; add one if you plan to distribute the project.
