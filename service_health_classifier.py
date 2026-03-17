import re


def classify_systemd_output(output: str) -> dict:
    """
    Classifies systemd service health from `systemctl status` output.
    """

    if not output:
        return {
            "health": "unknown",
            "reason": "no_output"
        }

    text = output.lower()

    if "active: active (running)" in text:
        return {
            "health": "healthy",
            "reason": "active_running"
        }

    if "active: active (exited)" in text:
        return {
            "health": "healthy",
            "reason": "active_exited"
        }

    if "active: activating" in text:
        return {
            "health": "starting",
            "reason": "activating"
        }

    if "active: inactive" in text:
        return {
            "health": "unhealthy",
            "reason": "inactive"
        }

    if "active: failed" in text:
        return {
            "health": "failed",
            "reason": "failed_state"
        }

    return {
        "health": "unknown",
        "reason": "unclassified"
    }
