from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./novahaus.db"
    admin_token: str = ""
    # By default the shared token stops working once a personal owner login exists.
    admin_token_always: bool = False
    # Shipping in pence. ASSUMPTION until carrier rates are confirmed.
    shipping_fee: int = 395
    free_shipping_threshold: int = 5000
    max_qty_per_item: int = 99
    # Stripe (use TEST keys until launch gate 3). Payments are off while empty.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    public_base_url: str = "http://localhost:3000"
    checkout_expiry_minutes: int = 30  # Stripe minimum is 30

    # --- Automation (runs inside the backend; see app/services/automation.py) ---
    automation_enabled: bool = True
    # Limits for acting WITHOUT asking. Anything above waits in Admin > Approvals.
    auto_reorder_max: int = 10000          # pence per purchase order (GBP 100)
    auto_reorder_weekly_max: int = 30000   # pence of auto-approved reorders per 7 days (GBP 300)
    auto_price_max_pct: float = 5.0        # max automatic price RISE in %; never lowers prices
    # Blueprint gate 2: contribution before ads >= 35% of ex-VAT price.
    min_contribution_margin: float = 0.35
    # Unpaid checkouts older than this are checked with Stripe and closed.
    pending_payment_timeout_minutes: int = 90
    # Daily jobs, hour of day in UTC.
    backup_hour: int = 2
    report_hour: int = 6
    # The automatic nightly backup keeps this many newest backups (0 = keep all).
    # Manual backups (backup.cmd) never delete anything.
    backup_keep: int = 60
    # Carts nobody has touched for this many days are removed by the cleanup job.
    cart_ttl_days: int = 30

    # --- Email ---
    # "outbox": emails are only stored (visible in Admin > Emails), nothing is sent.
    # "smtp": sent through any SMTP service (e.g. Brevo/Resend free plans, or Gmail app password).
    email_mode: str = "outbox"
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    email_from: str = "NOVAHAUS <hello@example.com>"
    # Signs links in emails (unsubscribe, reviews). Set a long random value in production.
    secret_key: str = ""
    # Business details required in marketing emails (UK: identify the sender).
    shop_legal_name: str = "NOVAHAUS"
    shop_address: str = ""

    # "production" turns on fail-safe behaviour: checkout refuses to run without
    # Stripe, and the API docs pages are hidden.
    environment: str = "development"

    # Test runs only (ignored in production): multiplies every rate limit.
    rate_limit_multiplier: int = 1

    @property
    def is_production(self) -> bool:
        return self.environment.lower() == "production"

    @field_validator("database_url")
    @classmethod
    def use_psycopg_driver(cls, v: str) -> str:
        """Hosted databases (Neon, Render, Heroku...) give postgres:// or postgresql:// URLs;
        this app talks to PostgreSQL through psycopg 3."""
        v = v.strip()
        for prefix in ("postgres://", "postgresql://"):
            if v.startswith(prefix):
                return "postgresql+psycopg://" + v[len(prefix):]
        return v


settings = Settings()
