"""Esquemas tipados de entrada/salida para las tools MCP."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

# El contrato de la API acepta state/instructions como texto u objeto/array
# estructurado (ver docs.typesafe.ai/api.md). dict/list quedan abiertos a
# JSON arbitrario porque el shape depende del caso de uso del llamante.
JsonState = str | dict[str, object] | list[object]


class ChoiceQuestion(BaseModel):
    """Elegir una opción de un conjunto definido."""

    type: Literal["choice"] = "choice"
    instructions: str = Field(description="La pregunta completa, con todo el sentido.")
    criteria: dict[str, str] = Field(
        description="Mapa opción -> descripción. Incluye 'none' si nada puede encajar."
    )


class ScoreQuestion(BaseModel):
    """Posición en una dimensión ordenada descrita por niveles."""

    type: Literal["score"] = "score"
    instructions: str = Field(description="Qué dimensión se puntúa.")
    criteria: dict[str, str] = Field(
        description="Mapa nivel -> situación concreta (p. ej. low/medium/high)."
    )


class NoulQuestion(BaseModel):
    """Probabilidad (0-1) de que una afirmación sea cierta."""

    type: Literal["noul"] = "noul"
    instructions: str = Field(description="Afirmación a evaluar, con contexto.")


class BatchItem(BaseModel):
    """Un elemento a clasificar dentro de un lote."""

    id: str = Field(description="Identificador estable del elemento.")
    state: JsonState = Field(
        description="Texto u objeto/array de contexto que se evalúa para este elemento."
    )


class ItemResult(BaseModel):
    """Resultado por elemento tras aplicar las preguntas."""

    id: str
    answers: dict[str, object]
