from datetime import datetime, timezone

import redis

from app.core.config import settings
from app.rag.embeddings import EmbeddingBudgetExceeded

_RESERVE_TOKENS = """
local current = tonumber(redis.call('GET', KEYS[1]) or '0')
local requested = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
if current + requested > limit then return 0 end
redis.call('INCRBY', KEYS[1], requested)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[3]))
return 1
"""


def reserve_embedding_tokens(client: redis.Redis, tokens: int) -> None:
    """Conservatively reserve tokens against the configured monthly usage ceiling."""
    limit = settings.embedding_monthly_token_limit
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    key = f"securedocs:embedding-budget:{settings.embedding_provider}:{settings.embedding_model}:{month}"
    if not client.eval(_RESERVE_TOKENS, 1, key, tokens, limit, 40 * 24 * 60 * 60):
        raise EmbeddingBudgetExceeded("Monthly embedding token limit reached. Try again next month.")
