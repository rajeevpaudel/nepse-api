import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL: str = os.environ["DATABASE_URL"]
API_KEY: str = os.environ["API_KEY"]
CACHE_DIR: str = os.getenv("CACHE_DIR", ".cache")
DEBUG_MODE: bool = os.getenv("DEBUG_MODE", "false").lower() == "true"
