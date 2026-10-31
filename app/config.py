from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Subscription Management System"
    company_name: str = "Brightloop Billing"
    database_url: str = "postgresql+psycopg://subs:subs@localhost:5432/subscriptions"

    jwt_secret: str = "dev-only-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_minutes: int = 60
    reset_token_minutes: int = 30

    frontend_url: str = "http://localhost:3000"
    smtp_host: str = "localhost"
    smtp_port: int = 1025
    smtp_from: str = "billing@brightloop.com"

    default_payment_terms_days: int = 14
    billing_auto_run: bool = False
    billing_interval_seconds: int = 86400

    bootstrap_admin_email: str = "admin@brightloop.com"
    bootstrap_admin_password: str = "Admin@12345"


settings = Settings()
