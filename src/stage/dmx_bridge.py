"""DMX Bridge — Ponte bidirecional entre canais HPG e universo DMX512.

Este módulo implementa a conversão de valores normalizados dos canais harmônicos
do sistema HPG (0.0–1.0, ponto flutuante) para os valores inteiros do protocolo
DMX512 (0–255, 8 bits por canal). A ponte mantém uma tabela de mapeamento que
associa cada canal HPG a um endereço DMX dentro do universo configurado.

O mapeamento segue a relação:
    DMX_valor = round(HPG_valor × 255)
    HPG_valor = DMX_valor / 255.0

Exemplo de uso:
    >>> bridge = DMXBridge(universe_id=1, harmonic_n=16)
    >>> hpg = {0: 0.5, 1: 1.0, 3: 0.25}
    >>> dmx = bridge.hpg_to_dmx(hpg)
    >>> dmx[0]   # → 128
    >>> dmx[1]   # → 255
    >>> dmx[3]   # → 64
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ChannelMapping:
    """Representa um único mapeamento canal HPG → endereço DMX.

    Attributes:
        hpg_index: Índice do canal harmônico (0 a H_N-1).
        dmx_address: Endereço DMX correspondente (1 a 512).
        label: Rótulo descritivo opcional para o mapeamento.
    """

    hpg_index: int
    dmx_address: int
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa o mapeamento para dicionário."""
        return {
            "hpg_index": self.hpg_index,
            "dmx_address": self.dmx_address,
            "label": self.label,
        }


@dataclass
class ChannelMapper:
    """Mapeador interno de canais HPG para endereços DMX.

    Constrói uma tabela de mapeamento sequencial onde o canal HPG de índice *i*
    é mapeado para o endereço DMX *(i + 1)*, respeitando o tamanho máximo do
    universo DMX512 (512 canais, endereços 1–512).

    Attributes:
        harmonic_n: Número total de canais harmônicos HPG.
        universe_size: Tamanho do universo DMX (padrão 512).
    """

    harmonic_n: int = 16
    universe_size: int = 512
    _mappings: list[ChannelMapping] = field(default_factory=list, init=False)

    def __post_init__(self) -> None:
        """Constrói a tabela de mapeamento após a inicialização."""
        self._build_mapping_table()

    def _build_mapping_table(self) -> None:
        """Constrói a tabela sequencial HPG → DMX.

        Cada canal HPG (0 … harmonic_n-1) é mapeado para um endereço DMX
        sequencial (1 … harmonic_n), limitado ao tamanho do universo.
        """
        self._mappings.clear()
        usable_channels = min(self.harmonic_n, self.universe_size)
        for i in range(usable_channels):
            self._mappings.append(
                ChannelMapping(
                    hpg_index=i,
                    dmx_address=i + 1,  # DMX é base-1
                    label=f"HPG_{i:03d}→DMX_{i + 1:03d}",
                )
            )
        logger.debug(
            "Tabela de mapeamento construída: %d canais HPG → DMX",
            usable_channels,
        )

    def hpg_index_for_dmx(self, dmx_address: int) -> int | None:
        """Retorna o índice HPG correspondente a um endereço DMX.

        Args:
            dmx_address: Endereço DMX (1 a 512).

        Returns:
            Índice do canal HPG ou ``None`` se não houver mapeamento.
        """
        for mapping in self._mappings:
            if mapping.dmx_address == dmx_address:
                return mapping.hpg_index
        return None

    def dmx_address_for_hpg(self, hpg_index: int) -> int | None:
        """Retorna o endereço DMX correspondente a um índice HPG.

        Args:
            hpg_index: Índice do canal harmônico (0 a N-1).

        Returns:
            Endereço DMX ou ``None`` se não houver mapeamento.
        """
        if 0 <= hpg_index < len(self._mappings):
            return self._mappings[hpg_index].dmx_address
        return None

    @property
    def mappings(self) -> list[ChannelMapping]:
        """Lista de mapeamentos configurados."""
        return list(self._mappings)

    @property
    def active_count(self) -> int:
        """Número de mapeamentos ativos."""
        return len(self._mappings)


class DMXBridge:
    """Ponte bidirecional entre canais harmônicos HPG e universo DMX512.

    A ``DMXBridge`` é o componente central que converte valores normalizados
    do sistema HPG (ponto flutuante 0.0–1.0) para valores inteiros do
    protocolo DMX512 (0–255), e vice-versa.

    Cada canal HPG é mapeado sequencialmente para um endereço DMX dentro do
    universo. A conversão direta (HPG→DMX) utiliza arredondamento para o
    inteiro mais próximo, enquanto a conversão inversa (DMX→HPG) normaliza
    pelo valor máximo (255).

    Args:
        universe_id: Identificador do universo DMX (padrão 0).
        harmonic_n: Número de canais harmônicos HPG a mapear (padrão 16).

    Example:
        >>> bridge = DMXBridge(universe_id=0, harmonic_n=16)
        >>> hpg = {0: 0.75, 2: 1.0, 5: 0.0}
        >>> dmx = bridge.hpg_to_dmx(hpg)
        >>> restored = bridge.dmx_to_hpg(dmx)
        >>> assert abs(restored[0] - 0.75) < 0.01
    """

    def __init__(self, universe_id: int = 0, harmonic_n: int = 16) -> None:
        """Inicializa a ponte DMX com universo e quantidade de canais HPG.

        Args:
            universe_id: Identificador do universo DMX (0–15 tipicamente).
            harmonic_n: Quantidade de canais harmônicos a mapear.
        """
        self._universe_id: int = universe_id
        self._universe_size: int = 512
        self._mapper: ChannelMapper = ChannelMapper(
            harmonic_n=harmonic_n,
            universe_size=self._universe_size,
        )
        self._last_dmx: list[int] = [0] * self._universe_size
        logger.info(
            "DMXBridge inicializada: universo=%d, HPG canais=%d",
            universe_id,
            harmonic_n,
        )

    # ── Conversão HPG → DMX ──────────────────────────────────────────────

    def hpg_to_dmx(self, hpg_values: dict[int, float]) -> list[int]:
        """Converte valores dos canais HPG para o universo DMX512.

        Para cada par ``(canal_hpg, valor)`` no dicionário de entrada, o valor
        normalizado (0.0–1.0) é convertido para inteiro DMX (0–255) usando
        arredondamento:

        .. math::
            \\text{DMX}[i] = \\text{round}(\\text{HPG}[i] \\times 255)

        Canais HPG sem correspondência no universo são silenciosamente ignorados.
        Valores fora do intervalo [0.0, 1.0] são clamped.

        Args:
            hpg_values: Dicionário ``{canal_hpg: valor_float}``.

        Returns:
            Lista de 512 inteiros representando o universo DMX completo.
            Posições sem canais HPG mapeados mantêm o último valor enviado
            (inicialmente 0).
        """
        output = list(self._last_dmx)  # cópia do último estado

        for hpg_index, value in hpg_values.items():
            dmx_addr = self._mapper.dmx_address_for_hpg(hpg_index)
            if dmx_addr is None:
                logger.warning(
                    "Canal HPG %d não possui mapeamento DMX — ignorado",
                    hpg_index,
                )
                continue

            # Clamping para o intervalo válido
            clamped = max(0.0, min(1.0, value))
            dmx_value = round(clamped * 255)
            # Garantia de limite inteiro 0–255
            dmx_value = max(0, min(255, dmx_value))

            # DMX usa endereços base-1; lista Python é base-0
            output[dmx_addr - 1] = dmx_value

        self._last_dmx = output
        logger.debug(
            "HPG→DMX: %d canais convertidos no universo %d",
            len(hpg_values),
            self._universe_id,
        )
        return output

    # ── Conversão DMX → HPG ──────────────────────────────────────────────

    def dmx_to_hpg(self, dmx_values: list[int]) -> dict[int, float]:
        """Converte valores do universo DMX512 para canais HPG.

        Para cada endereço DMX mapeado, o valor inteiro (0–255) é normalizado
        para ponto flutuante (0.0–1.0):

        .. math::
            \\text{HPG}[i] = \\frac{\\text{DMX}[i]}{255.0}

        Endereços DMX sem mapeamento HPG são ignorados. Valores inteiros
        fora do intervalo [0, 255] são clamped antes da conversão.

        Args:
            dmx_values: Lista de inteiros representando o universo DMX.
                        Deve conter pelo menos ``universe_size`` elementos.

        Returns:
            Dicionário ``{canal_hpg: valor_float}`` com os canais mapeados.

        Raises:
            ValueError: Se ``dmx_values`` tiver menos elementos que o tamanho
                        do universo configurado.
        """
        if len(dmx_values) < self._universe_size:
            raise ValueError(
                f"Array DMX possui {len(dmx_values)} elementos, "
                f"mas o universo requer {self._universe_size}."
            )

        result: dict[int, float] = {}

        for mapping in self._mapper.mappings:
            raw_value = dmx_values[mapping.dmx_address - 1]
            # Clamping de segurança
            clamped = max(0, min(255, raw_value))
            hpg_value = clamped / 255.0
            result[mapping.hpg_index] = round(hpg_value, 6)

        logger.debug(
            "DMX→HPG: %d canais convertidos do universo %d",
            len(result),
            self._universe_id,
        )
        return result

    # ── Tabela de mapeamento ──────────────────────────────────────────────

    def get_mapping_table(self) -> list[dict]:
        """Retorna a tabela completa de mapeamento HPG ↔ DMX.

        Cada entrada do dicionário retornado contém:

        - ``hpg_index``: Índice do canal harmônico.
        - ``dmx_address``: Endereço DMX correspondente.
        - ``label``: Rótulo descritivo do mapeamento.

        Returns:
            Lista de dicionários com o mapeamento completo.
        """
        return [m.to_dict() for m in self._mapper.mappings]

    def set_universe_size(self, size: int = 512) -> None:
        """Configura o tamanho do universo DMX512.

        O tamanho mínimo é 1 e o máximo é 512 (limite do protocolo DMX512).
        Ao redimensionar, o mapeador interno é reconstruído, o que pode
        alterar os canais ativos se o novo tamanho for menor que o número
        de canais HPG.

        Args:
            size: Novo tamanho do universo (1–512).

        Raises:
            ValueError: Se ``size`` estiver fora do intervalo válido.
        """
        if not 1 <= size <= 512:
            raise ValueError(
                f"Tamanho do universo deve estar entre 1 e 512, recebido: {size}"
            )
        self._universe_size = size
        self._mapper = ChannelMapper(
            harmonic_n=self._mapper.harmonic_n,
            universe_size=size,
        )
        # Ajusta o buffer do último estado
        self._last_dmx = [0] * size
        logger.info(
            "Universo DMX %d redimensionado para %d canais",
            self._universe_id,
            size,
        )

    # ── Propriedades ─────────────────────────────────────────────────────

    @property
    def universe_id(self) -> int:
        """Identificador do universo DMX (somente leitura)."""
        return self._universe_id

    @property
    def universe_size(self) -> int:
        """Tamanho atual do universo DMX em canais."""
        return self._universe_size

    @property
    def active_channels(self) -> int:
        """Número de canais HPG ativamente mapeados para DMX."""
        return self._mapper.active_count

    @property
    def mapping_table(self) -> list[dict]:
        """Tabela de mapeamento HPG ↔ DMX (alias para :meth:`get_mapping_table`)."""
        return self.get_mapping_table()

    # ── Representação ────────────────────────────────────────────────────

    def __repr__(self) -> str:
        return (
            f"DMXBridge(universe_id={self._universe_id}, "
            f"universe_size={self._universe_size}, "
            f"active_channels={self.active_channels})"
        )
