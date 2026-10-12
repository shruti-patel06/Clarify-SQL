"""Reads settings from the .env file once, so every other module imports
them from here instead of calling load_dotenv() and os.getenv() itself.
"""
import os

from dotenv import load_dotenv

load_dotenv()

DB_SETTINGS = {
    "dbname": os.getenv("DB_NAME"),
    "user": os.getenv("DB_USER"),
    "password": os.getenv("DB_PASSWORD"),
    "host": os.getenv("DB_HOST", "localhost"),
    "port": os.getenv("DB_PORT", "5432"),
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Groq changes its free-tier model lineup often; override this in .env
# (run `python -m scripts.list_models` to see what your key can use).
GROQ_MODEL = os.getenv("GROQ_MODEL", "qwen/qwen3.8-27b")
