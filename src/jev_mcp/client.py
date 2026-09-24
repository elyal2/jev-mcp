"""Cliente HTTP tipado para la Decision API de TypeSafe (System One / Jev).

Contrato (docs oficiales, sep. 2026):
    POST {base_url}
    Authorization: Bearer <key>
    body: {"model": str, "state": str|object|array, "questions": {id: {...}}}
    resp: {"model": str, "answers": {id: {...}}, "usage": {...}}

Los wrappers de terceros pueden variar el path pero mantienen la forma.

Errores de red, timeout, 429 y 5xx son transitorios y se reintentan con
backoff exponencial (ver retry.py); el resto (4xx, JSON inválido, respuesta
sin 'answers') son permanentes y fallan a la primera.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from .config import Settings
from .models import JsonState
from .retry import TransientError, retry_on_exception

logger = logging.getLogger(__name__)

_TRANSIENT_STATUS = {429, 500, 502, 503, 504}


class DecisionAPIError(RuntimeError):
    """Error HTTP o respuesta inesperada de la API. Fallo permanente."""


class _TransientDecisionError(DecisionAPIError, TransientError):
    """Fallo de red o de servidor que vale la pena reintentar."""


class JevClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    async def decide(
        self,
        state: JsonState,
        questions: dict[str, Any],
        model: str | None = None,
    ) -> dict[str, Any]:
        """Envía estado + preguntas tipadas; devuelve el dict completo de la API.

        Reintenta automáticamente fallos transitorios (red, timeout, 429, 5xx)
        con backoff exponencial. Lanza DecisionAPIError ante fallo permanente
        (4xx que no sea 429, JSON inválido, o respuesta sin 'answers') o si se
        agotan los reintentos.
        """
        retrying = retry_on_exception(
            retries=self._settings.retry_max_attempts,
            delay=self._settings.retry_base_delay,
            cap=self._settings.retry_cap_delay,
            exceptions=(TransientError,),
        )(self._decide_once)
        return await retrying(state, questions, model)

    async def _decide_once(
        self,
        state: JsonState,
        questions: dict[str, Any],
        model: str | None,
    ) -> dict[str, Any]:
        key = self._settings.require_key()
        payload: dict[str, Any] = {
            "model": model or self._settings.model,
            "state": state,
            "questions": questions,
        }
        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self._settings.timeout) as http:
                resp = await http.post(self._settings.base_url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            raise _TransientDecisionError(f"Fallo de red: {exc}") from exc

        if resp.status_code >= 400:
            message = f"HTTP {resp.status_code}: {resp.text[:500]}"
            if resp.status_code in _TRANSIENT_STATUS:
                raise _TransientDecisionError(message)
            raise DecisionAPIError(message)

        try:
            body: dict[str, Any] = resp.json()
        except ValueError as exc:
            raise DecisionAPIError(f"Respuesta no-JSON: {resp.text[:300]}") from exc
        if "answers" not in body:
            raise DecisionAPIError(f"Respuesta sin 'answers': {str(body)[:300]}")

        logger.info(
            "decide.usage",
            extra={"model": body.get("model"), "usage": body.get("usage")},
        )
        return body
