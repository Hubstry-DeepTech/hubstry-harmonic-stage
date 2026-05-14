"""Hubstry Harmonic Stage - Formato de Pacote HStage

Define o formato binário de pacotes para comunicação entre dispositivos de palco
no ecossistema Hubstry Harmonic Stage. Projetado para ser compacto, eficiente e
compatível com MTU de redes Ethernet padrão (~1500 bytes).

Layout do pacote HStage:
    ┌──────────┬──────────┬─────┬───────┬─────────────┬──────────┬──────────┐
    │ type(1B) │ seq(2B)  │N(1B)│cnt(1B)│ channels()  │auth(16B) │ ts(8B)   │
    │  PacketType│ uint16 │uint8│ uint8 │ 3B cada    │ opcional │ uint64   │
    └──────────┴──────────┴─────┴───────┴─────────────┴──────────┴──────────┘

Cada canal é codificado em 3 bytes: [índice: 1B][valor: 2B big-endian]
onde valor = int(float_value * 65535), mapeando 0.0-1.0 para 0-65535.

O campo auth_tag é opcional (presente quando o pacote está protegido pelo
Harmonic Security Layer) e contém os primeiros 16 bytes do HMAC-SHA256.

Dependências: apenas stdlib (enum, struct, time).
"""

from __future__ import annotations

import enum
import struct
import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Tamanho mínimo do cabeçalho fixo (type + seq + N + count + timestamp)
HEADER_FIXED_SIZE: int = 1 + 2 + 1 + 1 + 8  # = 13 bytes

#: Tamanho do campo auth_tag
AUTH_TAG_SIZE: int = 16

#: Tamanho de cada canal codificado (índice 1B + valor 2B)
CHANNEL_ENCODING_SIZE: int = 3

#: Tamanho máximo de payload para MTU-safe em Ethernet (~1400 bytes margem segura)
MTU_SAFE_PAYLOAD: int = 1400

#: Valor máximo de float normalizado
_FLOAT_MAX: int = 65535


# ---------------------------------------------------------------------------
# Enumeração de tipos de pacote
# ---------------------------------------------------------------------------


class PacketType(enum.IntEnum):
    """Tipos de pacote do protocolo HStage.

    Cada tipo define a semântica do conteúdo do pacote e como o receptor
    deve processá-lo. Os valores são compactos (1 byte) para minimizar
    o overhead de protocolo.

    Membros:
        DATA: Pacote de dados harmônicos (canais HPG).
        AUTH: Pacote de autenticação HSL.
        HEARTBEAT: Pacote de keep-alive para detecção de presença.
        CUE_TRIGGER: Disparo de cue de iluminação/áudio.
        CONFIG: Configuração de parâmetros do dispositivo.
        SYNC: Sincronização de estado entre dispositivos.
    """

    DATA = 0x01
    AUTH = 0x02
    HEARTBEAT = 0x03
    CUE_TRIGGER = 0x04
    CONFIG = 0x05
    SYNC = 0x06


# ---------------------------------------------------------------------------
# Pacote HStage
# ---------------------------------------------------------------------------


@dataclass(slots=True)
class HStagePacket:
    """Pacote do protocolo Hubstry Harmonic Stage.

    Representa um pacote binário compacto para transmissão de dados de controle
    harmônico entre dispositivos de palco. Suporta múltiplos canais com valores
    normalizados (0.0-1.0), autenticação HMAC opcional e timestamp para
    sincronização e detecção de pacotes obsoletos.

    Args:
        packet_type: Tipo do pacote (PacketType).
        sequence: Número de sequência (uint16, wrapping automático).
        harmonic_n: Ordem harmônica para este pacote (uint8, padrão: 16).
        channel_count: Número de canais no payload (uint8).
        channels: Lista de tuplas (índice, valor) com valores em [0.0, 1.0].
        auth_tag: Tag HMAC de 16 bytes, ou None se não autenticado.
        timestamp: Timestamp em milissegundos (uint64).
        payload: Payload binário adicional, ou None.

    Exemplo::

        >>> pkt = HStagePacket(
        ...     packet_type=PacketType.DATA,
        ...     sequence=1,
        ...     harmonic_n=16,
        ...     channel_count=4,
        ...     channels=[(0, 0.5), (1, 0.75), (2, 0.0), (3, 1.0)],
        ... )
        >>> data = pkt.to_bytes()
        >>> restored = HStagePacket.from_bytes(data)
    """

    packet_type: PacketType
    sequence: int
    harmonic_n: int = 16
    channel_count: int = 0
    channels: list[tuple[int, float]] = field(default_factory=list)
    auth_tag: bytes | None = None
    timestamp: int = 0
    payload: bytes | None = None

    def __post_init__(self) -> None:
        """Valida os campos após a inicialização."""
        if not isinstance(self.packet_type, PacketType):
            raise ValueError(
                f"packet_type deve ser PacketType, recebido {type(self.packet_type)}"
            )
        if not 0 <= self.sequence < (1 << 16):
            raise ValueError(
                f"sequence deve ser uint16 (0..{(1 << 16) - 1}), "
                f"recebido {self.sequence}"
            )
        if not 0 <= self.harmonic_n < (1 << 8):
            raise ValueError(
                f"harmonic_n deve ser uint8 (0..{(1 << 8) - 1}), "
                f"recebido {self.harmonic_n}"
            )
        if not 0 <= self.channel_count < (1 << 8):
            raise ValueError(
                f"channel_count deve ser uint8 (0..{(1 << 8) - 1}), "
                f"recebido {self.channel_count}"
            )
        if self.auth_tag is not None and len(self.auth_tag) != AUTH_TAG_SIZE:
            raise ValueError(
                f"auth_tag deve ter {AUTH_TAG_SIZE} bytes ou ser None, "
                f"recebido {len(self.auth_tag) if self.auth_tag else 'None'}"
            )
        if not 0 <= self.timestamp < (1 << 64):
            raise ValueError(
                f"timestamp deve ser uint64, recebido {self.timestamp}"
            )
        # Sincroniza channel_count com len(channels) se necessário
        if self.channel_count != len(self.channels):
            self.channel_count = len(self.channels)

    def to_bytes(self) -> bytes:
        """Serializa o pacote para formato binário.

        Formato:
            [type: 1B][seq: 2B BE][N: 1B][count: 1B]
            [channels: count × 3B (idx: 1B + val: 2B BE)]
            [auth_tag: 16B] (presente apenas se auth_tag não é None)
            [timestamp: 8B BE]

        O timestamp é preenchido automaticamente com o horário atual se
        estiver em zero.

        Returns:
            bytes: Pacote serializado.

        Raises:
            ValueError: Se algum valor de canal estiver fora do intervalo.
        """
        # Preenche timestamp automaticamente se necessário
        ts = self.timestamp
        if ts == 0:
            ts = int(time.time() * 1000) & ((1 << 64) - 1)

        # Cabeçalho fixo: [type:1B][seq:2B BE][N:1B][count:1B] = 5 bytes
        header = struct.pack(
            ">BHBB",
            self.packet_type.value,
            self.sequence & 0xFFFF,
            self.harmonic_n & 0xFF,
            self.channel_count & 0xFF,
        )

        # Canais
        channels_data = bytearray()
        for idx, val in self.channels:
            if not 0.0 <= val <= 1.0:
                raise ValueError(
                    f"Valor do canal {idx} fora do intervalo [0.0, 1.0]: {val}"
                )
            val_uint16 = int(val * _FLOAT_MAX) & 0xFFFF
            channels_data.append(idx & 0xFF)
            channels_data.extend(struct.pack(">H", val_uint16))

        # Auth tag (opcional)
        has_auth = self.auth_tag is not None

        # Monta o pacote completo
        result = bytearray(header)
        result.extend(channels_data)

        if has_auth:
            result.extend(self.auth_tag)

        result.extend(struct.pack(">Q", ts))

        return bytes(result)

    @classmethod
    def from_bytes(cls, data: bytes) -> HStagePacket:
        """Desserializa um pacote a partir de dados binários.

        Detecta automaticamente a presença do campo auth_tag com base no
        tamanho do pacote vs. o tamanho esperado sem autenticação.

        Args:
            data: Dados binários do pacote.

        Returns:
            HStagePacket: Instância do pacote desserializado.

        Raises:
            ValueError: Se os dados forem muito curtos ou inconsistentes.
        """
        if len(data) < HEADER_FIXED_SIZE:
            raise ValueError(
                f"Dados muito curtos: mínimo {HEADER_FIXED_SIZE} bytes, "
                f"recebido {len(data)}"
            )

        # Desempacota cabeçalho fixo: [type:1B][seq:2B BE][N:1B][count:1B] = 5 bytes
        type_val, sequence, harmonic_n, channel_count = struct.unpack(
            ">BHBB", data[:5]
        )

        # Timestamp nos últimos 8 bytes
        timestamp = struct.unpack(">Q", data[-8:])[0]

        # Determina se há auth_tag verificando o tamanho
        # Tamanho esperado sem auth: 5 + (count * 3) + 8
        # Tamanho esperado com auth: 5 + (count * 3) + 16 + 8
        channels_size = channel_count * CHANNEL_ENCODING_SIZE
        expected_without_auth = 5 + channels_size + 8
        expected_with_auth = 5 + channels_size + AUTH_TAG_SIZE + 8

        has_auth = len(data) == expected_with_auth
        if not has_auth and len(data) != expected_without_auth:
            raise ValueError(
                f"Tamanho inconsistente: recebido {len(data)}, "
                f"esperado {expected_without_auth} (sem auth) ou "
                f"{expected_with_auth} (com auth) para {channel_count} canais"
            )

        # Extrai canais
        channels_offset = 5
        channels: list[tuple[int, float]] = []
        for i in range(channel_count):
            offset = channels_offset + i * CHANNEL_ENCODING_SIZE
            idx = data[offset]
            val_uint16 = struct.unpack(">H", data[offset + 1 : offset + 3])[0]
            val = val_uint16 / _FLOAT_MAX
            channels.append((idx, val))

        # Extrai auth_tag se presente
        auth_tag: bytes | None = None
        if has_auth:
            auth_start = 5 + channels_size
            auth_tag = data[auth_start : auth_start + AUTH_TAG_SIZE]

        return cls(
            packet_type=PacketType(type_val),
            sequence=sequence,
            harmonic_n=harmonic_n,
            channel_count=channel_count,
            channels=channels,
            auth_tag=auth_tag,
            timestamp=timestamp,
        )

    def estimate_size(self) -> int:
        """Estima o tamanho do pacote em bytes quando serializado.

        Returns:
            int: Tamanho estimado em bytes.
        """
        base = 5  # header (type + seq + N + count)
        base += len(self.channels) * CHANNEL_ENCODING_SIZE
        if self.auth_tag is not None:
            base += AUTH_TAG_SIZE
        base += 8  # timestamp
        return base

    def is_securable(self) -> bool:
        """Verifica se o pacote possui tag de autenticação.

        Um pacote é considerado "securável" quando possui um auth_tag
        válido anexado, indicando que foi processado pelo Harmonic
        Security Layer (HSL).

        Returns:
            bool: True se o pacote possui auth_tag de 16 bytes.
        """
        return self.auth_tag is not None and len(self.auth_tag) == AUTH_TAG_SIZE

    @staticmethod
    def max_channels_per_packet(harmonic_n: int) -> int:
        """Calcula o número máximo de canais que cabem em um pacote MTU-safe.

        Considera o overhead fixo do protocolo (cabeçalho + timestamp)
        e o espaço opcional para auth_tag, garantindo que o pacote
        final não exceda o limite MTU-safe de ~1400 bytes.

        Cálculo:
            espaço_disponível = MTU_SAFE - header_fixo - timestamp - auth_tag
            max_canais = espaço_disponível // tamanho_por_canal

        Args:
            harmonic_n: Ordem harmônica (usada como referência, não afeta
                o cálculo de tamanho diretamente, mas documenta o contexto).

        Returns:
            int: Número máximo de canais por pacote MTU-safe.
        """
        available = MTU_SAFE_PAYLOAD - HEADER_FIXED_SIZE - AUTH_TAG_SIZE
        return max(0, available // CHANNEL_ENCODING_SIZE)
