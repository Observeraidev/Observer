import os
import json
import urllib.request
import urllib.error

API_URL = "http://127.0.0.1:8088/v1/brain/plan"
API_KEY = os.getenv("OBSERVER_API_KEY", "devkey_1")
ORG_ID = "org_dev"

INTENTS = [
    "systemd.status:observer-api.service",
    "systemd.status:brain-worker.service",
]


def send_intent(intent: str) -> None:
    payload = {"intent": intent}
    data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=data,
        method="POST",
        headers={
            "Authorization": f"Bearer {API_KEY}",
            "X-Org-Id": ORG_ID,
            "Content-Type": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            print(intent, "→", body)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        print(intent, "HTTPError", e.code, body)
    except Exception as e:
        print(intent, "ERROR", type(e).__name__, e)


def main() -> int:
    for intent in INTENTS:
        send_intent(intent)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
