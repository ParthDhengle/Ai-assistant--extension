import asyncio

def estimate_tokens(text: str) -> int:
    """Roughly estimate the number of tokens (assuming 4 chars per token)."""
    return len(text) // 4 + 1

async def async_estimate_tokens(text: str) -> int:
    """Async version of token estimation."""
    return estimate_tokens(text)