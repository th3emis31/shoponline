from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./novahaus.db"
    admin_token: str = ""
    # Shipping in pence. ASSUMPTION until carrier rates are confirmed.
    shipping_fee: int = 395
    free_shipping_threshold: int = 5000
    max_qty_per_item: int = 99
    # Stripe (use TEST keys until launch gate 3). Payments are off while empty.
    stripe_secret_key: str = ""
    stripe_webhook_secret: str = ""
    public_base_url: str = "http://localhost:3000"
    checkout_expiry_minutes: int = 30  # Stripe minimum is 30


settings = Settings()
