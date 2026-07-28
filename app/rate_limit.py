"""
Rate limiting setup using slowapi.

Uses in-memory storage, which is the right choice for a single backend
instance (which is exactly what a free-tier deployment on Render/Railway/
Fly.io looks like). If you ever scale to multiple backend instances, swap
to a Redis-backed storage so all instances share the same counters -
see slowapi docs for storage_uri.

Limits are keyed by IP address by default. This is the simplest effective
protection for a public app - it stops one person/bot from hammering your
free Gemini quota, without needing every request to be authenticated first.
"""
from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)

# Named limit strings, used as decorators on specific routes.
# Adjust these based on your actual Gemini free-tier quota and expected traffic.
CHAT_LIMIT = "10/minute;100/day"   # the expensive, Gemini-calling endpoints
AUTH_LIMIT = "5/minute"            # login/signup - blocks brute-force attempts
