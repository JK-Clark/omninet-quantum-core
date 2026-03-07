# © 2021-2026 Jonathan Kamu / Genio Elite. All rights reserved.
# Proprietary and confidential. Unauthorized reproduction or distribution is strictly prohibited.
"""
Audit logging module — structured event logging for AAA compliance.
"""

import datetime
import json
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("omninet.audit")


def log_action(
    action: str,
    user: Optional[str] = None,
    resource: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
    success: bool = True,
) -> None:
    """Write a structured audit log entry."""
    entry = {
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "action": action,
        "user": user,
        "resource": resource,
        "success": success,
        "details": details or {},
    }
    logger.info(json.dumps(entry))

