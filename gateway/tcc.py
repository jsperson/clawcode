"""TCC (Transparency, Consent, and Control) permission probes.

Runs diagnostic checks at gateway startup to verify macOS permissions
are in place for TCC-gated services (Calendar, Reminders, etc.).
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def probe_calendar(project_dir: str) -> bool:
    """Check if Calendar access is available via clawcal.

    Returns True if clawcal can list calendars, False otherwise.
    """
    clawcal = Path(project_dir) / "bin" / "clawcal"
    if not clawcal.exists():
        logger.warning("TCC probe: clawcal not found at %s — calendar features unavailable", clawcal)
        return False

    try:
        result = subprocess.run(
            [str(clawcal), "calendars"],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip().startswith("["):
            logger.info("TCC probe: Calendar access OK")
            return True
        else:
            logger.warning(
                "TCC probe: Calendar access denied — grant permission in "
                "System Settings > Privacy & Security > Calendar"
            )
            return False
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as e:
        logger.warning("TCC probe: Calendar check failed: %s", e)
        return False


def run_all_probes(project_dir: str) -> dict[str, bool]:
    """Run all TCC permission probes and return results.

    Returns a dict of {service_name: is_granted}.
    """
    results = {
        "calendar": probe_calendar(project_dir),
    }

    granted = sum(1 for v in results.values() if v)
    total = len(results)
    logger.info("TCC probes complete: %d/%d permissions granted", granted, total)
    return results
