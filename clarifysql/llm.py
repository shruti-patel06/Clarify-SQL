"""One place that talks to the Groq API. Every caller wants the same thing:
send some messages, get back a parsed JSON object.
"""
import json
import time

from groq import Groq, RateLimitError

from clarifysql.config import GROQ_API_KEY, GROQ_MODEL

# The SDK already retries a 429 (rate limit) response a few times after a
# short wait. The free tier's per-minute token limits can outlast that
# during long runs like the evaluation, so chat_json keeps waiting a bit
# longer before giving up.
client = Groq(api_key=GROQ_API_KEY, max_retries=4)
RATE_LIMIT_WAITS = [10, 20, 40]  # seconds


def chat_json(messages: list[dict]) -> dict:
    for wait in RATE_LIMIT_WAITS + [None]:
        try:
            response = client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
            return json.loads(response.choices[0].message.content)
        except RateLimitError:
            if wait is None:
                raise
            time.sleep(wait)
