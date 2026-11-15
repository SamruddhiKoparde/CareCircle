
import os
from pathlib import Path

from dotenv import load_dotenv

# Locate the project root (CareCircle/)
BASE_DIR = Path(__file__).resolve().parents[2]

# Load environment variables from the root .env file
load_dotenv(BASE_DIR / ".env")

APP_NAME = os.getenv("APP_NAME", "CareCircle")
APP_ENV = os.getenv("APP_ENV", "development")

SECRET_KEY = os.getenv("SECRET_KEY", "development-only-change-before-deployment")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"sqlite:///{BASE_DIR / 'data' / 'carecircle.db'}"
)

SESSION_EXPIRE_MINUTES = int(
    os.getenv("SESSION_EXPIRE_MINUTES", "60")
)

DATABASE_DIR = BASE_DIR / "data"
DATABASE_DIR.mkdir(parents=True, exist_ok=True)
