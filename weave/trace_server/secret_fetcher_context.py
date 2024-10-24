import contextvars

_secret_fetcher_context = contextvars.ContextVar("secret_fetcher")