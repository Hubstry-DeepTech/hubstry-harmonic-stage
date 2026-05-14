"""Controlador de Fixtures — Registro e controle de dispositivos DMX512.

Este módulo fornece a infraestrutura para gerenciar fixtures de iluminação
conectadas ao sistema DMX512, mapeando seus parâmetros (cor, intensidade,
pan/tilt, etc.) para canais harmônicos HPG.

O :class:`FixtureController` atua como o registro central de todos os
dispositivos, atribuindo automaticamente canais HPG sem conflitos e
fornecendo métodos para controle individual e agregado.

Exemplo de uso:
    >>> ctrl = FixtureController(universe_id=0)
    >>> fixture = Fixture(
    ...     id="MH-001",
    ...     fixture_type=FixtureType.MOVING_HEAD,
    ...     dmx_start_address=1,
    ...     channel_count=6,
    ...     parameters={"red": 0, "green": 1, "blue": 2, "intensity": 3, "pan": 4, "tilt": 5},
    ...     hpg_channels={},
    ... )
    >>> ctrl.add_fixture(fixture)
    >>> updates = ctrl.set_value("MH-001", "red", 1.0)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any

logger = logging.getLogger(__name__)


class FixtureType(Enum):
    """Classificação dos tipos de fixtures de iluminação suportados.

    Cada tipo define uma categoria de dispositivo DMX512 com características
    distintas de controle (canais, resolução, capacidade de movimento).
    """

    MOVING_HEAD = auto()
    """Moving head — fixture com movimento pan/tilt e controle de cor."""

    PAR_LED = auto()
    """PAR LED — fixture estática com controle de cor RGB/RGBW."""

    STRIP_LED = auto()
    """Fita LED — múltiplos pixels endereçáveis em sequência."""

    DIMMER = auto()
    """Dimmer — controle de intensidade para cargas convencionais."""

    STROBE = auto()
    """Strobe — efeito estroboscópico com controle de frequência."""

    FOGGER = auto()
    """Máquina de fumaça — controle de saída e intensidade."""

    def __str__(self) -> str:
        """Retorna nome legível do tipo de fixture."""
        labels = {
            FixtureType.MOVING_HEAD: "Moving Head",
            FixtureType.PAR_LED: "PAR LED",
            FixtureType.STRIP_LED: "Strip LED",
            FixtureType.DIMMER: "Dimmer",
            FixtureType.STROBE: "Strobe",
            FixtureType.FOGGER: "Máquina de Fumaça",
        }
        return labels.get(self, self.name)

    @classmethod
    def from_string(cls, value: str) -> FixtureType:
        """Converte string para FixtureType (case-insensitive).

        Args:
            value: Nome do tipo (ex.: ``"moving_head"``, ``"PAR_LED"``).

        Returns:
            Instância de :class:`FixtureType` correspondente.

        Raises:
            ValueError: Se o nome não corresponder a nenhum tipo conhecido.
        """
        normalized = value.strip().upper().replace(" ", "_")
        for member in cls:
            if member.name == normalized:
                return member
        raise ValueError(
            f"Tipo de fixture desconhecido: '{value}'. "
            f"Tipos válidos: {[t.name for t in cls]}"
        )


@dataclass
class Fixture:
    """Representação de uma fixture de iluminação no sistema.

    Cada fixture possui um endereço inicial DMX a partir do qual seus canais
    são distribuídos sequencialmente. Os parâmetros controláveis (cor,
    intensidade, movimento, etc.) são mapeados para offsets relativos ao
    endereço inicial.

    O dicionário ``hpg_channels`` é preenchido automaticamente pelo
    :class:`FixtureController` durante o registro, associando cada parâmetro
    a um canal HPG exclusivo.

    Args:
        id: Identificador único da fixture (ex.: ``"MH-001"``).
        fixture_type: Tipo classificado da fixture.
        dmx_start_address: Endereço DMX inicial (1–512).
        channel_count: Número total de canais DMX ocupados.
        parameters: Mapa de nomes de parâmetro para offsets DMX relativos.
        hpg_channels: Mapa de nomes de parâmetro para índices HPG
                      (preenchido pelo controlador).
    """

    id: str
    fixture_type: FixtureType
    dmx_start_address: int
    channel_count: int
    parameters: dict[str, int] = field(default_factory=dict)
    hpg_channels: dict[str, int] = field(default_factory=dict)

    # Estado interno atual (não persistido diretamente)
    _state: dict[str, float] = field(default_factory=dict, init=False, repr=False)

    def __post_init__(self) -> None:
        """Valida os campos da fixture após inicialização."""
        if not self.id:
            raise ValueError("Identificador da fixture não pode ser vazio.")
        if not 1 <= self.dmx_start_address <= 512:
            raise ValueError(
                f"Endereço DMX inicial deve estar entre 1 e 512, "
                f"recebido: {self.dmx_start_address}"
            )
        if self.channel_count < 1:
            raise ValueError(
                f"Número de canais deve ser ≥ 1, recebido: {self.channel_count}"
            )
        if self.dmx_start_address + self.channel_count - 1 > 512:
            raise ValueError(
                f"Fixture excede o limite do universo DMX512: "
                f"endereço {self.dmx_start_address} + "
                f"{self.channel_count} canais = "
                f"{self.dmx_start_address + self.channel_count - 1}"
            )
        # Inicializa estado com valores zerados
        self._state = {param: 0.0 for param in self.parameters}

    def set_state(self, parameter: str, value: float) -> None:
        """Atualiza o valor de um parâmetro no estado interno.

        Args:
            parameter: Nome do parâmetro.
            value: Valor normalizado (0.0–1.0).
        """
        clamped = max(0.0, min(1.0, value))
        self._state[parameter] = clamped

    def get_state(self) -> dict[str, float]:
        """Retorna cópia do estado atual da fixture.

        Returns:
            Dicionário ``{parâmetro: valor}`` com valores normalizados.
        """
        return dict(self._state)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a fixture para dicionário."""
        return {
            "id": self.id,
            "fixture_type": self.fixture_type.name,
            "dmx_start_address": self.dmx_start_address,
            "channel_count": self.channel_count,
            "parameters": dict(self.parameters),
            "hpg_channels": dict(self.hpg_channels),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Fixture:
        """Desserializa uma fixture a partir de dicionário.

        Args:
            data: Dicionário com campos da fixture.

        Returns:
            Instância de :class:`Fixture`.
        """
        fixture_type = data.get("fixture_type", "PAR_LED")
        if isinstance(fixture_type, str):
            fixture_type = FixtureType.from_string(fixture_type)

        return cls(
            id=data["id"],
            fixture_type=fixture_type,
            dmx_start_address=data["dmx_start_address"],
            channel_count=data["channel_count"],
            parameters=data.get("parameters", {}),
            hpg_channels=data.get("hpg_channels", {}),
        )


class FixtureController:
    """Controlador central de fixtures de iluminação.

    Gerencia o registro, remoção e controle de todas as fixtures conectadas
    ao sistema. Atribui automaticamente canais HPG a cada parâmetro de cada
    fixture, evitando conflitos de endereçamento.

    O controlador mantém um registro interno que rastreia quais canais HPG
    estão em uso, garantindo que cada parâmetro de cada fixture receba um
    canal exclusivo.

    Args:
        universe_id: Identificador do universo DMX associado.

    Example:
        >>> ctrl = FixtureController(universe_id=0)
        >>> par = Fixture(
        ...     id="PAR-001", fixture_type=FixtureType.PAR_LED,
        ...     dmx_start_address=1, channel_count=4,
        ...     parameters={"red": 0, "green": 1, "blue": 2, "intensity": 3},
        ... )
        >>> ctrl.add_fixture(par)
        >>> ctrl.set_value("PAR-001", "red", 0.8)
        {0: 0.8}
    """

    def __init__(self, universe_id: int = 0) -> None:
        """Inicializa o controlador de fixtures.

        Args:
            universe_id: Identificador do universo DMX associado (0–15).
        """
        self._universe_id: int = universe_id
        self._fixtures: dict[str, Fixture] = {}
        # Conjunto de canais HPG atualmente em uso
        self._used_hpg_channels: set[int] = set()
        # Próximo canal HPG disponível para atribuição automática
        self._next_hpg_channel: int = 0
        logger.info(
            "FixtureController inicializado: universo=%d",
            universe_id,
        )

    def _assign_hpg_channels(self, fixture: Fixture) -> None:
        """Atribui canais HPG exclusivos aos parâmetros de uma fixture.

        Percorre os parâmetros da fixture na ordem de seus offsets DMX e
        atribui o próximo canal HPG disponível a cada um, evitando conflitos
        com canais já em uso por outras fixtures.

        Args:
            fixture: Fixture cujos parâmetros receberão canais HPG.
        """
        # Ordena parâmetros por offset DMX para atribuição determinística
        sorted_params = sorted(
            fixture.parameters.items(),
            key=lambda item: item[1],
        )

        for param_name, _dmx_offset in sorted_params:
            # Pula canais já utilizados
            while self._next_hpg_channel in self._used_hpg_channels:
                self._next_hpg_channel += 1

            assigned_channel = self._next_hpg_channel
            fixture.hpg_channels[param_name] = assigned_channel
            self._used_hpg_channels.add(assigned_channel)
            self._next_hpg_channel += 1

            logger.debug(
                "Canal HPG %d atribuído → %s.%s",
                assigned_channel,
                fixture.id,
                param_name,
            )

    def _release_hpg_channels(self, fixture: Fixture) -> None:
        """Libera os canais HPG atribuídos a uma fixture.

        Remove os canais HPG da fixture do conjunto de canais em uso,
        permitindo sua reutilização por fixtures futuras.

        Args:
            fixture: Fixture cujos canais serão liberados.
        """
        for param_name, hpg_ch in fixture.hpg_channels.items():
            self._used_hpg_channels.discard(hpg_ch)
            logger.debug(
                "Canal HPG %d liberado de %s.%s",
                hpg_ch,
                fixture.id,
                param_name,
            )
        fixture.hpg_channels.clear()

    def _validate_no_overlap(self, fixture: Fixture) -> None:
        """Verifica se o endereço DMX da fixture não conflita com existentes.

        Args:
            fixture: Fixture a ser validada.

        Raises:
            ValueError: Se houver sobreposição de endereços DMX.
        """
        new_start = fixture.dmx_start_address
        new_end = new_start + fixture.channel_count - 1

        for existing in self._fixtures.values():
            ex_start = existing.dmx_start_address
            ex_end = ex_start + existing.channel_count - 1

            if new_start <= ex_end and new_end >= ex_start:
                raise ValueError(
                    f"Conflito de endereço DMX: '{fixture.id}' "
                    f"(endereços {new_start}–{new_end}) conflita com "
                    f"'{existing.id}' (endereços {ex_start}–{ex_end})."
                )

    # ── API Pública ──────────────────────────────────────────────────────

    def add_fixture(self, fixture: Fixture) -> None:
        """Registra uma nova fixture no controlador.

        Valida a ausência de conflitos de endereço DMX e atribui
        automaticamente canais HPG a todos os parâmetros da fixture.

        Args:
            fixture: Instância de :class:`Fixture` a ser registrada.

        Raises:
            ValueError: Se o ID já estiver em uso ou houver conflito DMX.
        """
        if fixture.id in self._fixtures:
            raise ValueError(
                f"Fixture com ID '{fixture.id}' já está registrada."
            )

        self._validate_no_overlap(fixture)
        self._assign_hpg_channels(fixture)
        self._fixtures[fixture.id] = fixture

        logger.info(
            "Fixture '%s' registrada: tipo=%s, DMX=%d–%d, "
            "HPG canais=%d",
            fixture.id,
            fixture.fixture_type,
            fixture.dmx_start_address,
            fixture.dmx_start_address + fixture.channel_count - 1,
            len(fixture.hpg_channels),
        )

    def remove_fixture(self, fixture_id: str) -> None:
        """Remove uma fixture do controlador.

        Libera os canais HPG atribuídos e remove a fixture do registro.

        Args:
            fixture_id: Identificador da fixture a ser removida.

        Raises:
            KeyError: Se a fixture não estiver registrada.
        """
        if fixture_id not in self._fixtures:
            raise KeyError(
                f"Fixture '{fixture_id}' não encontrada no controlador."
            )

        fixture = self._fixtures.pop(fixture_id)
        self._release_hpg_channels(fixture)
        logger.info("Fixture '%s' removida do controlador.", fixture_id)

    def set_value(
        self, fixture_id: str, parameter: str, value: float
    ) -> dict[int, float]:
        """Define o valor de um parâmetro de uma fixture.

        O valor é normalizado para o intervalo [0.0, 1.0] e propagado para
        o estado interno da fixture. Retorna as atualizações de canais HPG
        resultantes.

        Args:
            fixture_id: Identificador da fixture.
            parameter: Nome do parâmetro (ex.: ``"red"``, ``"pan"``).
            value: Valor normalizado (0.0–1.0).

        Returns:
            Dicionário ``{canal_hpg: valor}`` com as atualizações.

        Raises:
            KeyError: Se a fixture ou o parâmetro não existirem.
        """
        fixture = self._fixtures[fixture_id]
        if parameter not in fixture.parameters:
            raise KeyError(
                f"Parâmetro '{parameter}' não existe na fixture '{fixture_id}'. "
                f"Parâmetros disponíveis: {list(fixture.parameters.keys())}"
            )

        clamped = max(0.0, min(1.0, value))
        fixture.set_state(parameter, clamped)
        hpg_channel = fixture.hpg_channels[parameter]

        logger.debug(
            "%s.%s = %.3f (HPG ch %d)",
            fixture_id,
            parameter,
            clamped,
            hpg_channel,
        )
        return {hpg_channel: clamped}

    def set_values(
        self, fixture_id: str, values: dict[str, float]
    ) -> dict[int, float]:
        """Define múltiplos valores de uma fixture de uma vez.

        Equivalente a chamar :meth:`set_value` para cada parâmetro, mas
        retorna todas as atualizações HPG em um único dicionário.

        Args:
            fixture_id: Identificador da fixture.
            values: Dicionário ``{parâmetro: valor}``.

        Returns:
            Dicionário ``{canal_hpg: valor}`` com todas as atualizações.

        Raises:
            KeyError: Se a fixture ou algum parâmetro não existirem.
        """
        result: dict[int, float] = {}
        for parameter, value in values.items():
            updates = self.set_value(fixture_id, parameter, value)
            result.update(updates)
        return result

    def get_fixture_state(self, fixture_id: str) -> dict[str, float]:
        """Retorna o estado atual de uma fixture.

        Args:
            fixture_id: Identificador da fixture.

        Returns:
            Dicionário ``{parâmetro: valor}`` com o estado atual.

        Raises:
            KeyError: Se a fixture não estiver registrada.
        """
        if fixture_id not in self._fixtures:
            raise KeyError(
                f"Fixture '{fixture_id}' não encontrada no controlador."
            )
        return self._fixtures[fixture_id].get_state()

    def all_to_hpg(self) -> dict[int, float]:
        """Agrega o estado de todas as fixtures em um dicionário HPG.

        Percorre todas as fixtures registradas e compila seus estados
        atuais em um único dicionário ``{canal_hpg: valor}``, pronto para
        ser enviado ao sistema harmônico.

        Returns:
            Dicionário com o estado consolidado de todos os canais HPG.
        """
        result: dict[int, float] = {}
        for fixture in self._fixtures.values():
            for param_name, hpg_ch in fixture.hpg_channels.items():
                value = fixture._state.get(param_name, 0.0)
                result[hpg_ch] = value
        logger.debug("all_to_hpg: %d canais HPG agregados.", len(result))
        return result

    def list_fixtures(self) -> list[dict[str, Any]]:
        """Retorna um resumo de todas as fixtures registradas.

        Cada entrada contém informações de identificação, tipo, endereço
        DMX e canais HPG atribuídos.

        Returns:
            Lista de dicionários com o resumo de cada fixture.
        """
        result: list[dict[str, Any]] = []
        for fixture in self._fixtures.values():
            result.append(fixture.to_dict())
        return result

    # ── Propriedades ─────────────────────────────────────────────────────

    @property
    def universe_id(self) -> int:
        """Identificador do universo DMX associado."""
        return self._universe_id

    @property
    def fixture_count(self) -> int:
        """Número de fixtures registradas."""
        return len(self._fixtures)

    @property
    def total_hpg_channels(self) -> int:
        """Total de canais HPG em uso por todas as fixtures."""
        return len(self._used_hpg_channels)

    @property
    def registered_ids(self) -> list[str]:
        """Lista de IDs das fixtures registradas."""
        return list(self._fixtures.keys())

    # ── Representação ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"FixtureController(universe_id={self._universe_id}, "
            f"fixtures={self.fixture_count}, "
            f"hpg_channels={self.total_hpg_channels})"
        )
