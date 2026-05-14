"""Grade Harmônica H_N — Fachada de alto nível.

Combina RationalSet e ChannelMapper em uma interface unificada para
gestão completa dos canais harmônicos, reserva de canais e exportação
de configuração.
"""

from __future__ import annotations

from .channel_mapper import ChannelMapper, ChannelMapping
from .rational_set import RationalSet


class HarmonicGrid:
    """Grade harmônica — fachada unificada do HPG 1.0.

    Combina o conjunto racional H_N com o mapeador DMX em uma API de alto
    nível para gestão de canais harmônicos. Suporta reserva de canais,
    exportação de configuração e consultas agregadas.

    Args:
        N: Ordem harmônica máxima (padrão 16 → 255 canais).
        f0: Frequência fundamental em Hz (padrão 25.0).

    Examples:
        >>> grid = HarmonicGrid(N=16, f0=25.0)
        >>> channels = grid.get_channels()
        >>> len(channels)
        255
        >>> grid.summary()["available"]
        255
        >>> grid.reserve_channel(0, "teste")
        >>> grid.summary()["available"]
        254
    """

    def __init__(self, N: int = 16, f0: float = 25.0) -> None:
        self._rational_set = RationalSet(N=N)
        self._mapper = ChannelMapper(N=N, f0=f0)
        self._reservations: dict[int, str] = {}

    @property
    def total_channels(self) -> int:
        """Número total de canais H_N."""
        return self._rational_set.size

    @property
    def fundamental(self) -> float:
        """Frequência fundamental f₀."""
        return self._mapper.fundamental

    @property
    def max_harmonic(self) -> int:
        """Ordem harmônica máxima N."""
        return self._rational_set.N

    def get_channel(self, index: int) -> dict:
        """Retorna informações completas de um canal.

        Args:
            index: Índice do canal (base-0).

        Returns:
            Dicionário com index, ratio, frequency, dmx_address,
            reserved e purpose.
        """
        a, b = self._mapper.get_channel_ratio(index)
        return {
            "index": index,
            "ratio": (a, b),
            "ratio_str": f"{a}/{b}",
            "frequency": self._mapper.get_channel_frequency(index),
            "dmx_address": self._mapper.map_to_dmx(index),
            "reserved": index in self._reservations,
            "purpose": self._reservations.get(index),
        }

    def get_channels(self) -> list[dict]:
        """Retorna informações de todos os canais.

        Returns:
            Lista de dicionários com informações de cada canal.
        """
        return [self.get_channel(i) for i in range(self.total_channels)]

    def reserve_channel(self, index: int, purpose: str = "") -> None:
        """Reserva um canal para uso exclusivo.

        Args:
            index: Índice do canal (base-0).
            purpose: Descrição do propósito da reserva.

        Raises:
            IndexError: Se o índice for inválido.
            ValueError: Se o canal já estiver reservado.
        """
        if index < 0 or index >= self.total_channels:
            raise IndexError(
                f"Índice {index} fora do intervalo [0, {self.total_channels - 1}]"
            )
        if index in self._reservations:
            raise ValueError(
                f"Canal {index} já reservado para: {self._reservations[index]}"
            )
        self._reservations[index] = purpose
        self._mapper.reserve_channel(index, purpose)

    def free_channel(self, index: int) -> None:
        """Libera um canal reservado.

        Args:
            index: Índice do canal (base-0).
        """
        self._reservations.pop(index, None)
        self._mapper.free_channel(index)

    def available_channels(self) -> list[int]:
        """Retorna índices dos canais disponíveis.

        Returns:
            Lista ordenada de índices não reservados.
        """
        return sorted(set(range(self.total_channels)) - set(self._reservations.keys()))

    def summary(self) -> dict:
        """Retorna estatísticas da grade harmônica.

        Returns:
            Dicionário com N, total, reserved, available, f0 e
            frequências mínima/máxima.
        """
        rs_summary = self._rational_set.summary()
        return {
            "harmonic_order": self._rational_set.N,
            "total_channels": self.total_channels,
            "reserved": len(self._reservations),
            "available": self.total_channels - len(self._reservations),
            "fundamental_hz": self.fundamental,
            "freq_min_hz": self._mapper.get_channel_frequency(0),
            "freq_max_hz": self._mapper.get_channel_frequency(self.total_channels - 1),
            "reservations": dict(self._reservations),
        }

    def export_config(self) -> dict:
        """Exporta configuração serializável.

        Retorna um dicionário completo com todos os canais, reservas
        e parâmetros, pronto para persistência em JSON ou TOML.

        Returns:
            Configuração como dicionário.
        """
        return {
            "harmonic_order": self._rational_set.N,
            "fundamental_hz": self.fundamental,
            "total_channels": self.total_channels,
            "channels": [
                {
                    "index": ch["index"],
                    "ratio": ch["ratio"],
                    "frequency_hz": ch["frequency"],
                    "dmx_address": ch["dmx_address"],
                    "reserved": ch["reserved"],
                    "purpose": ch["purpose"],
                }
                for ch in self.get_channels()
            ],
            "reservations": dict(self._reservations),
        }

    def __repr__(self) -> str:
        return (
            f"HarmonicGrid(N={self._rational_set.N}, "
            f"canais={self.total_channels}, "
            f"disponíveis={self.total_channels - len(self._reservations)})"
        )
