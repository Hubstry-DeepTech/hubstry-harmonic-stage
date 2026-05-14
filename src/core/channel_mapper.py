"""Mapeador de Canais Harmônicos para DMX512.

Converte índices de canais H_N em endereços DMX (1-512) e parâmetros
de fixture (red, green, blue, pan, tilt, intensity, etc.).

DMX512 usa endereçamento base-1 (1-512), enquanto HPG usa base-0.
Este módulo gerencia a conversão bidirecional com clamping de valores.
"""

from __future__ import annotations

from dataclasses import dataclass, field


# Parâmetros padrão de fixtures por número de canais
FIXTURE_PARAMS: dict[int, list[str]] = {
    1: ["intensity"],
    2: ["intensity", "strobe"],
    3: ["red", "green", "blue"],
    4: ["red", "green", "blue", "intensity"],
    5: ["red", "green", "blue", "intensity", "strobe"],
    6: ["red", "green", "blue", "intensity", "pan_lo", "pan_hi"],
    7: ["red", "green", "blue", "intensity", "pan_lo", "pan_hi", "tilt_lo"],
    8: ["red", "green", "blue", "intensity", "pan_lo", "pan_hi", "tilt_lo", "tilt_hi"],
    9: [
        "red", "green", "blue", "intensity",
        "pan_lo", "pan_hi", "tilt_lo", "tilt_hi", "speed",
    ],
    10: [
        "red", "green", "blue", "intensity",
        "pan_lo", "pan_hi", "tilt_lo", "tilt_hi", "speed", "mode",
    ],
    12: [
        "red", "green", "blue", "white", "amber", "uv",
        "intensity", "strobe", "speed", "mode", "pan_lo", "pan_hi",
    ],
    16: [
        "red", "green", "blue", "white", "amber", "uv",
        "intensity", "strobe", "speed", "mode",
        "pan_lo", "pan_hi", "tilt_lo", "tilt_hi", "function", "macro",
    ],
}


@dataclass
class ChannelMapping:
    """Mapeamento individual de canal HPG ↔ DMX."""

    hpg_index: int
    hpg_ratio: tuple[int, int]
    frequency: float
    dmx_address: int
    param_name: str | None = None
    fixture_id: str | None = None


class ChannelMapper:
    """Mapeador de canais HPG para DMX512.

    Converte índices do conjunto H_N em endereços DMX e parâmetros
    de fixture, gerenciando a alocação de canais de forma eficiente.

    O H_16 possui 255 canais, enquanto DMX512 possui 512 slots.
    Cada fixture ocupa N canais DMX consecutivos (tipicamente 3-16).

    Args:
        N: Ordem harmônica máxima (padrão 16 → 255 canais).
        f0: Frequência fundamental em Hz (padrão 25.0 Hz).

    Examples:
        >>> mapper = ChannelMapper(N=16, f0=25.0)
        >>> mapper.map_to_dmx(0)
        1
        >>> mapper.get_channel_frequency(0)
        25.0
    """

    def __init__(self, N: int = 16, f0: float = 25.0) -> None:
        from .rational_set import RationalSet

        self._N = N
        self._f0 = f0
        self._rational_set = RationalSet(N=N)
        self._reserved: set[int] = set()
        self._fixture_allocations: dict[str, tuple[int, int]] = {}

    @property
    def total_channels(self) -> int:
        """Número total de canais H_N."""
        return self._rational_set.size

    @property
    def fundamental(self) -> float:
        """Frequência fundamental f₀."""
        return self._f0

    @property
    def max_harmonic(self) -> int:
        """Ordem harmônica máxima N."""
        return self._N

    @property
    def available_channels(self) -> int:
        """Canais H_N não reservados."""
        return self.total_channels - len(self._reserved)

    def get_channel_ratio(self, channel_index: int) -> tuple[int, int]:
        """Retorna a fração (a, b) de um canal H_N.

        Args:
            channel_index: Índice do canal (base-0).

        Returns:
            Tupla (numerador, denominador).

        Raises:
            IndexError: Se o índice estiver fora do intervalo.
        """
        if channel_index < 0 or channel_index >= self.total_channels:
            raise IndexError(
                f"Índice {channel_index} fora do intervalo [0, {self.total_channels - 1}]"
            )
        pair = self._rational_set.fractions[channel_index]
        return (pair.numerator, pair.denominator)

    def get_channel_frequency(self, channel_index: int) -> float:
        """Retorna a frequência f(a,b) = (a/b) × f₀ de um canal.

        Args:
            channel_index: Índice do canal (base-0).

        Returns:
            Frequência em Hz.
        """
        a, b = self.get_channel_ratio(channel_index)
        return (a / b) * self._f0

    def map_to_dmx(self, channel_index: int) -> int:
        """Mapeia índice HPG para endereço DMX (base-1).

        Mapeamento direto: HPG[i] → DMX[i+1], com clamping em 512.

        Args:
            channel_index: Índice do canal HPG (base-0).

        Returns:
            Endereço DMX (1-512).
        """
        dmx = channel_index + 1
        return min(max(dmx, 1), 512)

    def map_from_dmx(self, dmx_address: int) -> int:
        """Mapeia endereço DMX para índice HPG (base-0).

        Args:
            dmx_address: Endereço DMX (1-512).

        Returns:
            Índice HPG (base-0).
        """
        hpg = dmx_address - 1
        return min(max(hpg, 0), self.total_channels - 1)

    def map_to_fixture(
        self, channel_index: int, fixture_channels: int = 3
    ) -> tuple[int, int, list[str]]:
        """Mapeia canal HPG para faixa de DMX de uma fixture.

        Args:
            channel_index: Índice inicial HPG.
            fixture_channels: Número de canais da fixture (padrão 3 = RGB).

        Returns:
            Tupla (endereço DMX inicial, índice HPG final, lista de parâmetros).
        """
        dmx_start = self.map_to_dmx(channel_index)
        params = FIXTURE_PARAMS.get(fixture_channels, [f"ch{i}" for i in range(fixture_channels)])
        hpg_end = min(channel_index + fixture_channels - 1, self.total_channels - 1)
        return (dmx_start, hpg_end, params)

    def allocate_fixture(
        self, fixture_id: str, channel_count: int
    ) -> tuple[int, int]:
        """Aloca canais HPG consecutivos para uma fixture.

        Args:
            fixture_id: Identificador da fixture.
            channel_count: Número de canais necessários.

        Returns:
            Tupla (índice HPG inicial, índice HPG final).

        Raises:
            ValueError: Se não houver canais suficientes.
        """
        available = sorted(set(range(self.total_channels)) - self._reserved)

        for start_idx in range(len(available) - channel_count + 1):
            block = available[start_idx : start_idx + channel_count]
            if len(block) == channel_count and all(
                block[i] == available[start_idx] + i for i in range(channel_count)
            ):
                hpg_start = block[0]
                hpg_end = block[-1]
                for ch in block:
                    self._reserved.add(ch)
                self._fixture_allocations[fixture_id] = (hpg_start, hpg_end)
                return (hpg_start, hpg_end)

        raise ValueError(
            f"Não há {channel_count} canais consecutivos disponíveis "
            f"(disponíveis: {self.available_channels})"
        )

    def release_fixture(self, fixture_id: str) -> None:
        """Libera canais alocados para uma fixture.

        Args:
            fixture_id: Identificador da fixture.
        """
        if fixture_id not in self._fixture_allocations:
            raise KeyError(f"Fixture '{fixture_id}' não encontrada")
        start, end = self._fixture_allocations.pop(fixture_id)
        for ch in range(start, end + 1):
            self._reserved.discard(ch)

    def reserve_channel(self, channel_index: int, purpose: str = "") -> None:
        """Marca um canal como reservado.

        Args:
            channel_index: Índice do canal HPG.
            purpose: Descrição do propósito da reserva.
        """
        self._reserved.add(channel_index)

    def free_channel(self, channel_index: int) -> None:
        """Libera um canal reservado.

        Args:
            channel_index: Índice do canal HPG.
        """
        self._reserved.discard(channel_index)

    def get_full_mapping(self) -> list[ChannelMapping]:
        """Retorna o mapeamento completo HPG ↔ DMX.

        Returns:
            Lista de ChannelMapping para todos os canais.
        """
        mappings = []
        for i in range(self.total_channels):
            a, b = self.get_channel_ratio(i)
            mappings.append(
                ChannelMapping(
                    hpg_index=i,
                    hpg_ratio=(a, b),
                    frequency=self.get_channel_frequency(i),
                    dmx_address=self.map_to_dmx(i),
                )
            )
        return mappings

    def summary(self) -> dict:
        """Retorna estatísticas do mapeador.

        Returns:
            Dicionário com total, reservados, disponíveis e alocações.
        """
        return {
            "total_channels": self.total_channels,
            "reserved": len(self._reserved),
            "available": self.available_channels,
            "fixture_count": len(self._fixture_allocations),
            "fixtures": dict(self._fixture_allocations),
            "fundamental_hz": self._f0,
            "harmonic_order": self._N,
        }
