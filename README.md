# jev-mcp

Servidor MCP para la **Decision API de TypeSafe** (modelo System One / Jev): expone juicios tipados (Choice, Score, Noul) como tools que un agente puede llamar directamente.

Se creó porque las *skills* de Amazon Quick corren dentro de un sandbox **sin red y sin acceso a **`~/.config`, así que no pueden llamar a la API. Un servidor MCP corre como proceso aparte, con red y acceso al entorno, y se invoca por el protocolo MCP (mismo patrón que `mcp-crawl4ai`).

## Stack

Python 3.12+, `mcp>=2.2,<3` (`MCPServer`, antes `FastMCP` en mcp 1.x), `httpx`, `pydantic` / `pydantic-settings`. Tipado para `mypy --strict`, linteado con `ruff`. Gestionado con `uv`.

## Instalación

```bash
cd /Users/install4/_code/jev-mcp
make install                 # uv sync: crea el entorno e instala dependencias
cp .env.example .env         # y rellena JEV_API_KEY
uv run pre-commit install    # opcional pero recomendado: hooks de lint/tipos/secretos

```

## Desarrollo

```bash
make run           # arranca en stdio
make run-http      # arranca en streamable-http (para el conector de este chat)
make test          # pytest (unit + integration), con cobertura
make test-unit     # solo tests marcados @pytest.mark.unit
make lint          # ruff check
make format        # ruff format
make type-check     # mypy --strict
make check          # lint + type-check + test, todo junto
make docker-up      # docker compose up -d --build
make docker-down    # docker compose down --remove-orphans

```

## Configuración

Variables (en `.env` o en el entorno). La clave se acepta como `JEV_API_KEY` o `TYPESAFE_API_KEY`.

| Variable | Por defecto | Para qué |
| --- | --- | --- |
| `JEV_API_KEY` | (vacío) | Clave de API (o `TYPESAFE_API_KEY`) |
| `JEV_BASE_URL` | `https://api.typesafe.ai/v1/systemone` | Endpoint (cámbialo si usas un wrapper) |
| `JEV_MODEL` | `jev-latest` | Modelo |
| `JEV_TIMEOUT` | `30` | Timeout en segundos |
| `JEV_TRANSPORT` | `stdio` | `stdio` o `streamable-http` |
| `JEV_LOG_LEVEL` | `INFO` | Nivel de log (JSON estructurado, a stderr) |
| `JEV_RETRY_MAX_ATTEMPTS` | `5` | Reintentos ante fallo transitorio (red/timeout/429/5xx) |
| `JEV_RETRY_BASE_DELAY` | `2.0` | Backoff base en segundos (exponencial) |
| `JEV_RETRY_CAP_DELAY` | `32.0` | Techo del backoff en segundos |

## Comprobar que arranca

```bash
make run              # arranca en stdio; Ctrl-C para salir

```

Para verificar credenciales sin llamar a la API, usa la tool `health` desde el cliente MCP.

## Tools

- `health()` — ¿hay clave?, endpoint y modelo. No expone la clave.
- `decide(state, questions, model?)` — varias preguntas tipadas sobre un estado, en una llamada. `state` puede ser texto u objeto/array. Ante fallo (permanente, o transitorio tras agotar reintentos) la tool devuelve un error MCP — no un dict `{"error": ...}` disfrazado de éxito.
- `classify_batch(items, questions, max_concurrency=8, model?)` — las mismas preguntas sobre muchos elementos, en paralelo controlado. Para triaje/clasificación de volúmenes. Este sí es un contrato de resultados parciales: `results` trae los elementos que funcionaron y `errors` los que fallaron, ambos en el mismo orden que `items`; un fallo individual no tumba el lote.

Fallos de red, timeout, `429` y `5xx` se reintentan solos con backoff exponencial (ver `JEV_RETRY_*` arriba); el resto de errores (4xx, JSON inválido) fallan a la primera.

Cada pregunta es uno de tres tipos:

```jsonc
// choice: elegir una opción
{"type": "choice", "instructions": "¿Qué equipo?", "criteria": {"billing": "...", "technical": "...", "none": "..."}}
// score: grado en dimensión ordenada
{"type": "score", "instructions": "Prioridad", "criteria": {"low": "...", "medium": "...", "high": "..."}}
// noul: probabilidad de que una condición sea cierta
{"type": "noul", "instructions": "El documento trata datos personales de residentes UE"}

```

## Registro

### Claude Code / Desktop / OpenCode (stdio)

Equivalente al bloque de `crawl4ai`, pero con `uv run`:

```jsonc
"jev": {
  "type": "local",
  "command": ["uv", "run", "--directory", "/Users/install4/_code/jev-mcp", "jev-mcp"],
  "enabled": true
}

```

(Si prefieres no fijar el directorio en el comando, usa `"command": ["uvx", "--from", "/Users/install4/_code/jev-mcp", "jev-mcp"]`.)

### Conector HTTP (este chat)

Este chat consume conectores por HTTP, no por stdio. Arranca en modo HTTP:

```bash
JEV_TRANSPORT=streamable-http uv run jev-mcp
# o con Docker:
docker compose up -d

```

y registra la URL `http://127.0.0.1:8787/mcp` como conector MCP personalizado en Ajustes.

## Notas

- El `health` y el manejo de errores no requieren clave; las llamadas reales sí.
- Los contratos de la API pueden cambiar: la fuente de verdad es [https://docs.typesafe.ai](https://docs.typesafe.ai).
