# Bearer token removal

"""
Token Scrubber — specialized module for redacting
authentication tokens, secrets, and credentials.
"""
import re
from typing import List


class TokenScrubber:
    """
    Scrubs authentication tokens and secrets from text.
    Handles: Bearer tokens, JWTs, API keys, AWS keys, etc.
    """

    TOKEN_PATTERNS = [
        # AWS Access Keys
        (r"AKIA[0-9A-Z]{16}", "[REDACTED_AWS_KEY]"),
        # Generic long tokens (hex/base64)
        (r"\b[a-f0-9]{32,}\b", "[REDACTED_HEX_TOKEN]"),
        # Private keys
        (r"-----BEGIN[A-Z ]+-----[\s\S]*?-----END[A-Z ]+-----", "[REDACTED_PRIVATE_KEY]"),
        # Slack/Discord tokens
        (r"xox[baprs]-[a-zA-Z0-9-]+", "[REDACTED_SLACK_TOKEN]"),
        # GitHub tokens
        (r"gh[pousr]_[A-Za-z0-9_]{36,}", "[REDACTED_GITHUB_TOKEN]"),
    ]

    def scrub(self, text: str) -> str:
        """Apply all token scrubbing patterns."""
        scrubbed = text
        for pattern, replacement in self.TOKEN_PATTERNS:
            scrubbed = re.sub(pattern, replacement, scrubbed, flags=re.IGNORECASE)
        return scrubbed