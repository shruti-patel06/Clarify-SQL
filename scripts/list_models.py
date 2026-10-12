"""Lists every model your Groq API key currently has access to.
Run this (python -m scripts.list_models) if the GROQ_MODEL setting ever stops working — Groq
changes its free-tier lineup fairly often, so this checks the ground
truth instead of guessing a model name.
"""
from groq import Groq

from clarifysql.config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

for model in client.models.list().data:
    print(model.id)
