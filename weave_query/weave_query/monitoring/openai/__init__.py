"""
This module provides callback support for OpenAI's Chat API.  Users can define custom behaviour at various stages of the API call lifecycle (e.g. after yield streaming chunk, before return)

We provide simple patch and unpatch functions to enable or disable these features.

By default, the patch method will provide goodies like auto-collecting streaming completions and logging results to StreamTable
"""

__all__ = ["patch", "unpatch"]

from .openai import patch, unpatch
