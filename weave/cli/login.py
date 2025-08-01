"""Weave login functionality."""

from __future__ import annotations

import logging
from typing import Optional

logger = logging.getLogger(__name__)


def weave_login(
    key: Optional[str] = None,
    host: Optional[str] = None,
    relogin: bool = False,
    verify: bool = True,
    timeout: Optional[int] = None,
) -> bool:
    """Login to Weights & Biases for use with Weave.
    
    This function sets up W&B login credentials that will be used by Weave
    for authentication. It stores credentials locally and optionally verifies
    them with the W&B server.
    
    Args:
        key: The API key to use. If not provided, will prompt for input.
        host: The host to connect to. Defaults to W&B cloud.
        relogin: If True, will re-prompt for API key even if already logged in.
        verify: If True, verify the credentials with the W&B server.
        timeout: Number of seconds to wait for user input.
        
    Returns:
        bool: True if login successful, False otherwise.
        
    Examples:
        Login with an API key:
        
        >>> weave_login(key="your-api-key-here")
        True
        
        Login to a custom host:
        
        >>> weave_login(host="https://your-wandb-instance.com")
        True
    """
    # Import the existing wandb login functionality
    from weave.compat.wandb.wandb_thin.login import login as wandb_login
    
    try:
        success = wandb_login(
            key=key,
            host=host,
            relogin=relogin,
            verify=verify,
            timeout=timeout,
            # We explicitly exclude anonymous login as requested
            anonymous="never",
        )
        
        if success:
            logger.info("Successfully logged in to Weights & Biases for Weave")
        else:
            logger.error("Failed to login to Weights & Biases")
            
        return success
        
    except Exception as e:
        logger.error(f"Login failed with error: {e}")
        return False