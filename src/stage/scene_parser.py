"""Analisador de Cenas — Serialização e construção de cenas de iluminação.

Este módulo implementa a leitura, gravação e validação de cenas completas de
iluminação em formato JSON. Uma cena (:class:`Scene`) encapsula as definições
de fixtures, a sequência de cues e metadados descritivos (autor, descrição,
data de criação).

O :class:`SceneParser` oferece métodos para conversão entre os formatos
dicionário, JSON e arquivo, além de validação estrutural e construção
automática de :class:`FixtureController` e :class:`CueStack` a partir de
uma cena carregada.

Formato de cena JSON de exemplo:

.. code-block:: json

    {
        "name": "Show de Abertura",
        "metadata": {
            "author": "Maria Silva",
            "description": "Cena principal com PARs e Moving Heads",
            "created_at": "2024-01-15T20:00:00"
        },
        "fixtures": [
            {
                "id": "PAR-001",
                "fixture_type": "PAR_LED",
                "dmx_start_address": 1,
                "channel_count": 4,
                "parameters": {
                    "red": 0, "green": 1, "blue": 2, "intensity": 3
                }
            },
            {
                "id": "MH-001",
                "fixture_type": "MOVING_HEAD",
                "dmx_start_address": 5,
                "channel_count": 6,
                "parameters": {
                    "red": 0, "green": 1, "blue": 2,
                    "intensity": 3, "pan": 4, "tilt": 5
                }
            }
        ],
        "cues": [
            {
                "name": "Blackout",
                "values": {"0": 0.0, "1": 0.0, "2": 0.0, "3": 0.0},
                "fade_in": 0.5, "fade_out": 0.5, "hold": 0.0, "priority": 0
            },
            {
                "name": "Vermelho Total",
                "values": {"0": 1.0, "1": 0.0, "2": 0.0, "3": 1.0},
                "fade_in": 2.0, "fade_out": 1.0, "hold": 5.0, "priority": 1
            }
        ]
    }

Exemplo de uso:
    >>> parser = SceneParser()
    >>> scene = parser.from_file("cena_abertura.json")
    >>> problemas = parser.validate(scene)
    >>> if not problemas:
    ...     ctrl, stack = parser.build_fixture_controller(scene)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .cue_engine import Cue, CueStack
from .fixture_controller import Fixture, FixtureController, FixtureType

logger = logging.getLogger(__name__)


@dataclass
class Scene:
    """Representação completa de uma cena de iluminação.

    Uma cena encapsula todas as informações necessárias para configurar e
    reproduzir um espetáculo: fixtures, cues e metadados.

    Attributes:
        name: Nome descritivo da cena.
        fixtures: Lista de definições de fixtures (dicionários).
        cues: Lista de definições de cues (dicionários).
        metadata: Metadados da cena (autor, descrição, data de criação).
    """

    name: str = ""
    fixtures: list[dict[str, Any]] = field(default_factory=list)
    cues: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Garante que metadata possua campos padrão."""
        defaults = {
            "author": "",
            "description": "",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        for key, default_value in defaults.items():
            if key not in self.metadata:
                self.metadata[key] = default_value


class SceneParser:
    """Analisador e serializador de cenas de iluminação.

    Oferece métodos para converter cenas entre diferentes formatos
    (dicionário, JSON, arquivo) e construir objetos operacionais
    (:class:`FixtureController` e :class:`CueStack`) a partir de uma cena
    carregada.

    Example:
        >>> parser = SceneParser()
        >>> scene = parser.from_json(json_string)
        >>> controller, cue_stack = parser.build_fixture_controller(scene)
    """

    def __init__(self) -> None:
        """Inicializa o analisador de cenas."""
        logger.info("SceneParser inicializado.")

    # ── Leitura / Análise ────────────────────────────────────────────────

    def from_dict(self, data: dict[str, Any]) -> Scene:
        """Analisa um dicionário para um objeto :class:`Scene`.

        Args:
            data: Dicionário com campos da cena. Chaves esperadas:
                  ``name`` (opcional), ``fixtures`` (lista),
                  ``cues`` (lista), ``metadata`` (dicionário, opcional).

        Returns:
            Instância de :class:`Scene` preenchida.
        """
        if not isinstance(data, dict):
            raise TypeError(
                f"Entrada deve ser um dicionário, recebido: {type(data).__name__}"
            )

        scene = Scene(
            name=data.get("name", ""),
            fixtures=data.get("fixtures", []),
            cues=data.get("cues", []),
            metadata=data.get("metadata", {}),
        )

        logger.info(
            "Cena '%s' analisada: %d fixtures, %d cues.",
            scene.name,
            len(scene.fixtures),
            len(scene.cues),
        )
        return scene

    def from_json(self, json_str: str) -> Scene:
        """Analisa uma string JSON para um objeto :class:`Scene`.

        Args:
            json_str: String JSON contendo a definição da cena.

        Returns:
            Instância de :class:`Scene` preenchida.

        Raises:
            json.JSONDecodeError: Se a string não for JSON válido.
            TypeError: Se o JSON decodificado não for um dicionário.
        """
        data = json.loads(json_str)
        return self.from_dict(data)

    def from_file(self, filepath: str) -> Scene:
        """Lê e analisa uma cena a partir de um arquivo JSON.

        Args:
            filepath: Caminho para o arquivo JSON da cena.

        Returns:
            Instância de :class:`Scene` preenchida.

        Raises:
            FileNotFoundError: Se o arquivo não existir.
            json.JSONDecodeError: Se o conteúdo não for JSON válido.
        """
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(
                f"Arquivo de cena não encontrado: {filepath}"
            )

        content = path.read_text(encoding="utf-8")
        logger.info("Cena carregada do arquivo: %s", filepath)
        return self.from_json(content)

    # ── Escrita / Serialização ───────────────────────────────────────────

    def to_dict(self, scene: Scene) -> dict[str, Any]:
        """Serializa um objeto :class:`Scene` para dicionário.

        Args:
            scene: Instância de :class:`Scene` a ser serializada.

        Returns:
            Dicionário com todos os campos da cena.
        """
        return {
            "name": scene.name,
            "fixtures": scene.fixtures,
            "cues": scene.cues,
            "metadata": scene.metadata,
        }

    def to_json(self, scene: Scene) -> str:
        """Serializa um objeto :class:`Scene` para string JSON.

        Args:
            scene: Instância de :class:`Scene` a ser serializada.

        Returns:
            String JSON formatada (indentação de 2 espaços).
        """
        data = self.to_dict(scene)
        return json.dumps(data, ensure_ascii=False, indent=2)

    def to_file(self, scene: Scene, filepath: str) -> None:
        """Grava uma cena em arquivo JSON.

        Cria os diretórios pai se necessário.

        Args:
            scene: Instância de :class:`Scene` a ser gravada.
            filepath: Caminho do arquivo de destino.
        """
        path = Path(filepath)
        path.parent.mkdir(parents=True, exist_ok=True)
        json_str = self.to_json(scene)
        path.write_text(json_str, encoding="utf-8")
        logger.info("Cena '%s' gravada em: %s", scene.name, filepath)

    # ── Validação ────────────────────────────────────────────────────────

    def validate(self, scene: Scene) -> list[str]:
        """Valida a integridade estrutural de uma cena.

        Verifica a presença de campos obrigatórios, tipos de dados,
        consistência de endereços DMX e referências entre fixtures e cues.

        Returns:
            Lista de mensagens de aviso/erro. Lista vazia indica que
            a cena é válida.
        """
        issues: list[str] = []

        # ── Validações do nome ───────────────────────────────────────
        if not scene.name.strip():
            issues.append("AVISO: Nome da cena está vazio.")

        # ── Validações dos fixtures ──────────────────────────────────
        if not isinstance(scene.fixtures, list):
            issues.append("ERRO: 'fixtures' deve ser uma lista.")
        else:
            dmx_addresses_seen: dict[int, str] = {}
            fixture_ids: set[str] = set()

            for idx, fix_def in enumerate(scene.fixtures):
                prefix = f"fixtures[{idx}]"

                if not isinstance(fix_def, dict):
                    issues.append(f"ERRO: {prefix} não é um dicionário.")
                    continue

                # ID obrigatório
                if "id" not in fix_def or not str(fix_def["id"]).strip():
                    issues.append(f"ERRO: {prefix} — campo 'id' ausente ou vazio.")
                    continue

                fix_id = str(fix_def["id"])

                # Verifica duplicidade de ID
                if fix_id in fixture_ids:
                    issues.append(
                        f"ERRO: {prefix} — ID '{fix_id}' duplicado."
                    )
                fixture_ids.add(fix_id)

                # Tipo de fixture
                if "fixture_type" not in fix_def:
                    issues.append(f"ERRO: {prefix} — campo 'fixture_type' ausente.")
                else:
                    try:
                        FixtureType.from_string(str(fix_def["fixture_type"]))
                    except ValueError:
                        issues.append(
                            f"ERRO: {prefix} — tipo '{fix_def['fixture_type']}' "
                            f"inválido. Tipos: {[t.name for t in FixtureType]}"
                        )

                # Endereço DMX
                for addr_field in ("dmx_start_address", "channel_count"):
                    if addr_field not in fix_def:
                        issues.append(
                            f"ERRO: {prefix} — campo '{addr_field}' ausente."
                        )

                if "dmx_start_address" in fix_def and "channel_count" in fix_def:
                    try:
                        start = int(fix_def["dmx_start_address"])
                        count = int(fix_def["channel_count"])
                        end = start + count - 1

                        if not 1 <= start <= 512:
                            issues.append(
                                f"ERRO: {prefix} — endereço DMX {start} "
                                f"fora do intervalo 1–512."
                            )
                        if count < 1:
                            issues.append(
                                f"ERRO: {prefix} — channel_count deve ser ≥ 1."
                            )
                        if end > 512:
                            issues.append(
                                f"ERRO: {prefix} — endereço final {end} "
                                f"excede o limite DMX512."
                            )

                        # Verifica sobreposição de endereços
                        for existing_end, existing_id in dmx_addresses_seen.items():
                            if start <= existing_end and end >= (
                                existing_end - int(
                                    scene.fixtures[
                                        list(dmx_addresses_seen.keys()).index(
                                            existing_end
                                        )
                                    ].get("channel_count", 1)
                                )
                                + 1
                            ):
                                issues.append(
                                    f"AVISO: {prefix} — possível sobreposição "
                                    f"de endereço DMX com '{existing_id}'."
                                )

                        dmx_addresses_seen[end] = fix_id

                    except (ValueError, TypeError):
                        issues.append(
                            f"ERRO: {prefix} — campos de endereço DMX devem "
                            f"ser inteiros."
                        )

        # ── Validações dos cues ──────────────────────────────────────
        if not isinstance(scene.cues, list):
            issues.append("ERRO: 'cues' deve ser uma lista.")
        else:
            for idx, cue_def in enumerate(scene.cues):
                prefix = f"cues[{idx}]"

                if not isinstance(cue_def, dict):
                    issues.append(f"ERRO: {prefix} não é um dicionário.")
                    continue

                if "name" not in cue_def or not str(cue_def.get("name", "")).strip():
                    issues.append(f"AVISO: {prefix} — campo 'name' ausente ou vazio.")

                if "values" not in cue_def:
                    issues.append(f"ERRO: {prefix} — campo 'values' ausente.")
                elif not isinstance(cue_def["values"], dict):
                    issues.append(f"ERRO: {prefix} — 'values' deve ser um dicionário.")
                else:
                    for ch_key, ch_val in cue_def["values"].items():
                        try:
                            val = float(ch_val)
                            if not 0.0 <= val <= 1.0:
                                issues.append(
                                    f"AVISO: {prefix}.values[{ch_key}] = {val} "
                                    f"fora do intervalo [0.0, 1.0]."
                                )
                        except (ValueError, TypeError):
                            issues.append(
                                f"ERRO: {prefix}.values[{ch_key}] = '{ch_val}' "
                                f"não é um número válido."
                            )

                # Validação de tempos
                for time_field in ("fade_in", "fade_out", "hold"):
                    if time_field in cue_def:
                        try:
                            t = float(cue_def[time_field])
                            if t < 0:
                                issues.append(
                                    f"ERRO: {prefix}.{time_field} = {t} "
                                    f"deve ser ≥ 0."
                                )
                        except (ValueError, TypeError):
                            issues.append(
                                f"ERRO: {prefix}.{time_field} deve ser numérico."
                            )

        # ── Validações dos metadados ─────────────────────────────────
        if not isinstance(scene.metadata, dict):
            issues.append("AVISO: 'metadata' deve ser um dicionário.")

        # Resumo
        errors = sum(1 for i in issues if i.startswith("ERRO"))
        warnings = sum(1 for i in issues if i.startswith("AVISO"))
        logger.info(
            "Validação da cena '%s': %d erro(s), %d aviso(s).",
            scene.name,
            errors,
            warnings,
        )
        return issues

    # ── Construção ───────────────────────────────────────────────────────

    def build_fixture_controller(
        self, scene: Scene
    ) -> tuple[FixtureController, CueStack]:
        """Constrói um :class:`FixtureController` e :class:`CueStack` a partir de uma cena.

        Cria fixtures a partir das definições da cena, registra-os no
        controlador e popula a pilha de cues com os cues da cena.

        Args:
            scene: Instância de :class:`Scene` com fixtures e cues.

        Returns:
            Tupla ``(FixtureController, CueStack)`` pronta para uso.

        Raises:
            ValueError: Se houver erros irrecuperáveis na construção.
        """
        controller = FixtureController()
        cue_stack = CueStack()

        # ── Registro das fixtures ────────────────────────────────────
        for fix_def in scene.fixtures:
            try:
                fixture = Fixture.from_dict(fix_def)
                controller.add_fixture(fixture)
            except (ValueError, KeyError) as exc:
                raise ValueError(
                    f"Erro ao construir fixture '{fix_def.get('id', '?')}': {exc}"
                ) from exc

        # ── População da pilha de cues ───────────────────────────────
        for cue_def in scene.cues:
            try:
                cue = Cue.from_dict(cue_def)
                cue_stack.add_cue(cue)
            except (ValueError, KeyError) as exc:
                logger.warning(
                    "Erro ao construir cue '%s': %s — cue ignorado.",
                    cue_def.get("name", "?"),
                    exc,
                )

        logger.info(
            "Cena '%s' construída: %d fixtures registradas, "
            "%d cues na pilha.",
            scene.name,
            controller.fixture_count,
            len(cue_stack),
        )
        return controller, cue_stack
