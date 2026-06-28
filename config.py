"""Configuration for rigel-beta, all driven by env with dev-friendly defaults."""
import os


class Config:
    DB_PATH: str = os.environ.get("BETA_DB_PATH", "./rigel-beta.db")
    RESEND_API_KEY: str = os.environ.get("RESEND_API_KEY", "")  # empty -> DEV mode (no network)
    FROM: str = os.environ.get("BETA_FROM", "Rigel Beta <beta@vivesincables.com>")
    ADMIN_KEY: str = os.environ.get("BETA_ADMIN_KEY", "dev-admin-key")
    BASE_URL: str = os.environ.get("BASE_URL", "http://localhost:9486").rstrip("/")


config = Config()
