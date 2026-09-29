"""AI providers behind one small interface: generate(system, prompt) -> text."""
import json
import re
import time
import urllib.request
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ...config import settings
from ...models import AICall

_EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
_PHONE = re.compile(r"(?:\+?44|0)(?:[\s-]?\d){9,10}")
_POSTCODE = re.compile(r"\b[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b", re.I)


class ProviderError(Exception):
    pass


def redact(text: str) -> str:
    """Remove personal details before text leaves the server for an external AI service."""
    text = _EMAIL.sub("[email]", text)
    text = _PHONE.sub("[phone]", text)
    return _POSTCODE.sub("[postcode]", text)


def name() -> str:
    p = (settings.ai_provider or "rules").lower()
    return p if p in ("rules", "ollama", "api") else "rules"


def calls_today(db: Session) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=1)
    return db.scalar(select(func.count()).select_from(AICall).where(AICall.created_at >= since)) or 0


def _post(url: str, body: dict, headers: dict, timeout: int = 120) -> dict:
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (URL comes from the owner's settings)
        return json.loads(r.read().decode())


def generate(db: Session, system: str, prompt: str, task_id: int | None = None) -> str:
    """Call the configured AI service. Logged, capped per day, personal data redacted for "api"."""
    provider = name()
    if provider == "rules":
        raise ProviderError("rules provider has no model")  # callers use the built-in rules instead
    if calls_today(db) >= settings.ai_max_calls_per_day:
        raise ProviderError(f"Daily AI limit reached ({settings.ai_max_calls_per_day}). Using built-in rules.")
    if provider == "api":
        if not settings.ai_api_key or not settings.ai_model:
            raise ProviderError("AI_API_KEY and AI_MODEL are not set")
        system, prompt = redact(system), redact(prompt)
    model = settings.ollama_model if provider == "ollama" else settings.ai_model
    started = time.monotonic()
    log = AICall(task_id=task_id, provider=provider, model=model, prompt_chars=len(system) + len(prompt))
    try:
        if provider == "ollama":
            data = _post(f"{settings.ollama_url.rstrip('/')}/api/chat",
                         {"model": model, "stream": False, "options": {"temperature": 0.2},
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]}, {})
            text = data["message"]["content"]
        else:
            data = _post(settings.ai_api_url,
                         {"model": model, "temperature": 0.2,
                          "messages": [{"role": "system", "content": system}, {"role": "user", "content": prompt}]},
                         {"Authorization": f"Bearer {settings.ai_api_key}"})
            text = data["choices"][0]["message"]["content"]
        log.output_chars = len(text)
        return text
    except ProviderError:
        raise
    except Exception as exc:
        log.ok, log.error = False, f"{type(exc).__name__}: {str(exc)[:300]}"
        raise ProviderError(log.error) from exc
    finally:
        log.ms = int((time.monotonic() - started) * 1000)
        with db.begin_nested():
            db.add(log)
