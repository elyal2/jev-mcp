"""Servidor MCP para la Decision API de TypeSafe (System One / Jev).

Expone pocas tools de alto nivel, con parámetros tipados y respuestas
compactas, en vez de un espejo 1:1 del endpoint:

  - decide            : una sola pieza de estado, varias preguntas tipadas.
  - classify_batch    : las mismas preguntas aplicadas a muchos elementos.
  - health            : comprueba credenciales/endpoint sin llamar a la API.

La clave y el endpoint se resuelven desde el entorno / .env (ver config.py).
Este proceso corre FUERA del sandbox de la app, por eso sí tiene red.

`decide` deja que DecisionAPIError se propague: MCPServer lo convierte en un
error de tool para el cliente MCP, en vez de devolverlo disfrazado de
resultado normal. `classify_batch` sí captura errores por elemento porque su
contrato es explícitamente de resultados parciales (unos items pueden fallar
sin invalidar el resto del lote).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from mcp.server.mcpserver import MCPServer

from .client import DecisionAPIError, JevClient
from .config import settings as settings
from .logging_config import configure_logging, new_correlation_id
from .models import BatchItem, ChoiceQuestion, JsonState, NoulQuestion, ScoreQuestion

logger = logging.getLogger(__name__)

mcp = MCPServer("jev")
_client = JevClient(settings)

# Una pregunta puede ser cualquiera de los tres primitivos.
QuestionSpec = ChoiceQuestion | ScoreQuestion | NoulQuestion


def _dump_questions(questions: dict[str, QuestionSpec]) -> dict[str, Any]:
    """Convierte los modelos tipados al dict JSON que espera la API."""
    return {qid: q.model_dump() for qid, q in questions.items()}


@mcp.tool()
async def health() -> dict[str, Any]:
    """Comprueba configuración sin llamar a la API.

    Devuelve si hay clave, el endpoint y el modelo. No expone la clave.
    """
    key = settings.api_key
    masked = (key[:4] + "…" + key[-2:]) if len(key) > 6 else ("***" if key else "")
    return {
        "has_key": bool(key),
        "key_hint": masked,
        "endpoint": settings.base_url,
        "model": settings.model,
    }


@mcp.tool()
async def decide(
    state: JsonState,
    questions: dict[str, QuestionSpec],
    model: str | None = None,
) -> dict[str, Any]:
    """Evalúa varias preguntas tipadas sobre UN estado, en una sola llamada.

    Args:
        state: texto u objeto/array de contexto a juzgar.
        questions: mapa id -> pregunta (choice | score | noul). Preguntas
            independientes se evalúan en paralelo y aisladas.
        model: opcional, sobreescribe el modelo por defecto.

    Returns el cuerpo de la API: {"model", "answers": {id: {...}}, "usage"}.
    Lanza DecisionAPIError (fallo permanente, o transitorio tras agotar
    reintentos) — MCPServer lo devuelve al cliente MCP como error de tool.
    """
    new_correlation_id()
    try:
        result = await _client.decide(state, _dump_questions(questions), model)
    except DecisionAPIError:
        logger.exception("decide.failed")
        raise
    logger.info("decide.ok", extra={"usage": result.get("usage")})
    return result


@mcp.tool()
async def classify_batch(
    items: list[BatchItem],
    questions: dict[str, QuestionSpec],
    max_concurrency: int = 8,
    model: str | None = None,
) -> dict[str, Any]:
    """Aplica las MISMAS preguntas a muchos elementos, en paralelo controlado.

    Pensado para triaje/clasificación de volúmenes: documentos, correos,
    filas, o descripciones textuales de imágenes. Devuelve un resultado por
    elemento más un bloque de errores para los que fallaron; el orden de
    ambas listas respeta el orden de `items`.

    Args:
        items: lista de {id, state}.
        questions: mapa id -> pregunta (choice | score | noul).
        max_concurrency: nº máx. de llamadas simultáneas.
        model: opcional, sobreescribe el modelo por defecto.
    """
    new_correlation_id()
    q = _dump_questions(questions)
    sem = asyncio.Semaphore(max(1, max_concurrency))

    async def _one(item: BatchItem) -> dict[str, Any]:
        async with sem:
            try:
                body = await _client.decide(item.state, q, model)
                return {"id": item.id, "answers": body.get("answers", {})}
            except DecisionAPIError as exc:
                logger.warning(
                    "classify_batch.item_failed",
                    extra={"item_id": item.id, "error": str(exc)},
                )
                return {"id": item.id, "error": str(exc)}

    outcomes = await asyncio.gather(*(_one(it) for it in items))
    results = [o for o in outcomes if "error" not in o]
    errors = [{"id": o["id"], "error": o["error"]} for o in outcomes if "error" in o]
    logger.info(
        "classify_batch.done",
        extra={"total": len(items), "ok": len(results), "failed": len(errors)},
    )
    return {"count": len(results), "results": results, "errors": errors}


def main() -> None:
    """Punto de entrada. Transporte según JEV_TRANSPORT (stdio | streamable-http)."""
    configure_logging(settings.log_level)
    if settings.transport == "streamable-http":
        mcp.run(transport="streamable-http", host=settings.http_host, port=settings.http_port)
    else:
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
