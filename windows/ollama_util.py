"""Small helpers for talking to a local Ollama server."""
import json

import requests


def base_url(chat_url: str) -> str:
    return chat_url.split("/api/")[0].rstrip("/")


def ollama_running(base: str) -> bool:
    try:
        return requests.get(base + "/api/tags", timeout=2).ok
    except requests.RequestException:
        return False


def has_model(base: str, model: str) -> bool:
    try:
        r = requests.get(base + "/api/tags", timeout=5)
        r.raise_for_status()
        names = {m.get("name") for m in r.json().get("models", [])}
    except Exception:
        return False
    return model in names or (":" not in model and model + ":latest" in names)


def pull_model(base: str, model: str, progress=None) -> None:
    """Download a model. progress(status, percent_or_None) is called as it streams."""
    with requests.post(base + "/api/pull", json={"model": model, "stream": True},
                       stream=True, timeout=(5, 600)) as r:
        r.raise_for_status()
        for line in r.iter_lines():
            if not line:
                continue
            msg = json.loads(line)
            if "error" in msg:
                raise RuntimeError(msg["error"])
            total, done = msg.get("total"), msg.get("completed")
            pct = int(done * 100 / total) if total and done is not None else None
            if progress:
                progress(msg.get("status", ""), pct)
            if msg.get("status") == "success":
                return
