from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = "sqlite:///./novahaus.db"
    admin_token: str = ""
    # Shipping in pence. ASSUMPTION until carrier rates are confirmed.
    shipping_fee: int = 395
    free_shipping_threshold: int = 5000
    max_qty_per_item: int = 99


settings = Settings()
