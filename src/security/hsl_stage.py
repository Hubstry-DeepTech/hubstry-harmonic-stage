"""Hubstry Harmonic Stage - Camada de Segurança Harmônica (HSL Stage)

Implementação do Harmonic Security Layer otimizado para comunicação entre
dispositivos de palco, incluindo autenticação mútua, cifragem de canais HPG
e proteção contra ataques de replay.

O HSL Stage integra o LightAuth com a lógica de sessão e cifragem de dados
de controle harmônico, mantendo o overhead mínimo de ~200 bytes por pacote
de autenticação em comparação aos ~8000 bytes do TLS 1.3.

Arquitetura:
    ┌─────────────────────────────────────────┐
    │              HSLStage                    │
    │  ┌───────────┐  ┌────────────────────┐  │
    │  │ LightAuth │  │ Anti-Replay Buffer │  │
    │  │ (crypto)  │  │ (janela deslizante)│  │
    │  └───────────┘  └────────────────────┘  │
    │  ┌───────────┐  ┌────────────────────┐  │
    │  │ Session   │  │ Channel Encryptor  │  │
    │  │ Manager   │  │ (XOR+derivado)    │  │
    │  └───────────┘  └────────────────────┘  │
    └─────────────────────────────────────────┘

Dependências: apenas stdlib + módulo auth_lightweight deste pacote.
"""

from __future__ import annotations

import struct
import time
from collections import deque

from .auth_lightweight import AuthPacket, LightAuth


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Tamanho padrão da janela anti-replay (últimos N sequências rastreadas)
DEFAULT_REPLAY_WINDOW: int = 64

#: Tamanho da chave de sessão derivada em bytes
SESSION_KEY_SIZE: int = 32

#: Identificador de contexto para cifragem de canais
CHANNEL_ENCRYPT_CONTEXT: bytes = b"HSL-channel"


class HSLStage:
    """Camada de segurança harmônica para comunicação de palco.

    Gerencia autenticação mútua, cifragem de canais HPG e proteção contra
    replay para a comunicação entre dispositivos no ecossistema Hubstry
    Harmonic Stage.

    O HSL Stage combina:
    - **LightAuth**: Para geração e verificação de pacotes HMAC.
    - **Anti-replay**: Janela deslizante de sequências para detectar
      pacotes duplicados ou reordenados maliciosamente.
    - **Cifragem de canais**: Cifra XOR leve baseada em chave de sessão
      derivada, suficiente para ofuscar dados de controle harmônico.

    Args:
        shared_key: Chave compartilhada de 256 bits (32 bytes) pré-distribuída.
        device_id: Identificador único do dispositivo (8 bytes).
        harmonic_n: Ordem harmônica padrão para cifragem (padrão: 16).

    Exemplo::

        >>> key = os.urandom(32)
        >>> dev_id = os.urandom(8)
        >>> hsl = HSLStage(shared_key=key, device_id=dev_id, harmonic_n=16)
        >>> auth_pkt = hsl.authenticate()
        >>> ok, reason = hsl.verify(auth_pkt)
        >>> ok
        True
    """

    def __init__(
        self,
        shared_key: bytes,
        device_id: bytes,
        harmonic_n: int = 16,
    ) -> None:
        """Inicializa a camada de segurança harmônica.

        Args:
            shared_key: Chave compartilhada de 256 bits (32 bytes).
            device_id: Identificador único do dispositivo (8 bytes).
            harmonic_n: Ordem harmônica padrão para cifragem.
        """
        self._auth = LightAuth(shared_key=shared_key, device_id=device_id)
        self._harmonic_n = harmonic_n

        # Estado da sessão
        self._session_active: bool = False
        self._session_start_ms: int = 0
        self._session_key: bytes | None = None
        self._session_peer_device_id: bytes | None = None
        self._sequence_counter: int = 0
        self._packet_count: int = 0

        # Buffer anti-replay (janela deslizante de sequências)
        self._replay_window: deque[int] = deque(maxlen=DEFAULT_REPLAY_WINDOW)
        self._max_sequence_seen: int = 0

    def authenticate(self) -> AuthPacket:
        """Gera um pacote de autenticação inicial.

        Cria um AuthPacket com o próximo número de sequência disponível,
        pronto para ser enviado a um dispositivo par para estabelecimento
        de sessão.

        Returns:
            AuthPacket: Pacote de autenticação para transmissão.
        """
        self._sequence_counter += 1
        packet = self._auth.generate_packet(sequence=self._sequence_counter)
        self._packet_count += 1
        self._session_active = True

        return packet

    def verify(self, packet: AuthPacket) -> tuple[bool, str]:
        """Verifica um pacote de autenticação recebido.

        Realiza verificações em camadas:
        1. Tamanho e formato do pacote.
        2. Detecção de replay (sequência já vista).
        3. Frescor do timestamp.
        4. Verificação HMAC-SHA256.

        Args:
            packet: Pacote de autenticação a ser verificado.

        Returns:
            tuple[bool, str]: (sucesso, razão detalhada).
                - (True, "OK"): Verificação bem-sucedida.
                - (False, motivo): Falha com descrição do motivo.
        """
        # 1. Validação de formato
        if not packet.validate_size():
            return (False, "formato inválido: campos com tamanho incorreto")

        # 2. Detecção de replay
        if self._is_replay(packet.sequence):
            return (
                False,
                f"replay detectado: sequência {packet.sequence} já processada",
            )

        # 3. Verificação HMAC e frescor (delegada ao LightAuth)
        if not self._auth.verify_packet(packet):
            return (False, "HMAC inválido ou timestamp expirado")

        # 4. Marca sequência como processada
        self._mark_sequence(packet.sequence)
        self._max_sequence_seen = max(self._max_sequence_seen, packet.sequence)
        self._packet_count += 1

        return (True, "OK")

    def encrypt_channel(self, channel_index: int, value: float) -> bytes:
        """Cifra dados de um canal harmônico para transmissão segura.

        Utiliza cifragem XOR com uma chave derivada da chave de sessão,
        combinada com o índice do canal para garantir que cada canal
        produz ciphertext diferente para o mesmo valor.

        O valor float (0.0-1.0) é convertido para uint16 (0-65535) antes
        da cifragem, resultando em 4 bytes de output (índice + valor cifrado).

        Formato de saída: [channel_index: 2B big-endian][encrypted_value: 2B]

        Args:
            channel_index: Índice do canal harmônico (0 a harmonic_n-1).
            value: Valor do canal no intervalo [0.0, 1.0].

        Returns:
            bytes: Dados cifrados do canal (4 bytes).

        Raises:
            RuntimeError: Se não há sessão ativa (sem chave de sessão).
            ValueError: Se o valor estiver fora do intervalo [0.0, 1.0].
        """
        if not self._session_active or self._session_key is None:
            raise RuntimeError(
                "Sessão não ativa. Chame create_session() antes de cifrar canais."
            )

        if not 0.0 <= value <= 1.0:
            raise ValueError(
                f"valor deve estar no intervalo [0.0, 1.0], recebido {value}"
            )

        # Converte float para uint16
        value_uint16 = int(value * 65535) & 0xFFFF

        # Deriva sub-chave para este canal específico
        channel_key = self._derive_channel_key(channel_index)

        # Cifra o valor com XOR usando a sub-chave (primeiros 2 bytes)
        encrypted_value = value_uint16 ^ int.from_bytes(
            channel_key[:2], "big"
        )

        return struct.pack(">HH", channel_index & 0xFFFF, encrypted_value)

    def decrypt_channel(self, data: bytes) -> tuple[int, float]:
        """Decifra dados de um canal harmônico recebido.

        Operação inversa de encrypt_channel: extrai o índice do canal,
        decifra o valor XOR e converte de volta para float.

        Args:
            data: Dados cifrados do canal (4 bytes).

        Returns:
            tuple[int, float]: (índice_do_canal, valor_decifrado_no_intervalo_0.0-1.0).

        Raises:
            RuntimeError: Se não há sessão ativa.
            ValueError: Se os dados tiverem tamanho incorreto.
        """
        if not self._session_active or self._session_key is None:
            raise RuntimeError(
                "Sessão não ativa. Chame create_session() antes de decifrar canais."
            )

        if len(data) != 4:
            raise ValueError(
                f"Dados cifrados devem ter 4 bytes, recebido {len(data)}"
            )

        channel_index, encrypted_value = struct.unpack(">HH", data)

        # Deriva sub-chave para este canal
        channel_key = self._derive_channel_key(channel_index)

        # Decifra com XOR
        value_uint16 = encrypted_value ^ int.from_bytes(
            channel_key[:2], "big"
        )

        # Converte de volta para float
        value = value_uint16 / 65535.0

        return (channel_index, value)

    def create_session(self, peer_packet: AuthPacket) -> bool:
        """Estabelece uma sessão autenticada com um dispositivo par.

        Realiza autenticação mútua:
        1. Verifica o pacote do par usando verify().
        2. Deriva uma chave de sessão combinada usando o device_id do par.
        3. Ativa a sessão para cifragem de canais.

        Args:
            peer_packet: Pacote de autenticação recebido do dispositivo par.

        Returns:
            bool: True se a sessão foi estabelecida com sucesso.
        """
        ok, reason = self.verify(peer_packet)
        if not ok:
            return False

        # Deriva chave de sessão usando device_ids de ambos os lados
        # Ordena lexicograficamente para garantir que ambos os lados derivam a mesma chave
        my_id = self._auth.device_id
        peer_id = peer_packet.device_id

        if my_id <= peer_id:
            seed = my_id + peer_id
        else:
            seed = peer_id + my_id

        self._session_key = self._auth.derive_session_key(seed)
        self._session_peer_device_id = peer_id
        self._session_active = True
        self._session_start_ms = int(time.time() * 1000) & ((1 << 64) - 1)

        return True

    def is_authenticated(self) -> bool:
        """Verifica se há uma sessão ativa e válida.

        Returns:
            bool: True se a sessão está ativa.
        """
        return self._session_active

    def session_info(self) -> dict:
        """Retorna metadados da sessão atual.

        Returns:
            dict: Dicionário com informações da sessão contendo:
                - active: Se a sessão está ativa (bool)
                - age_ms: Idade da sessão em milissegundos (int)
                - packet_count: Total de pacotes processados (int)
                - peer_device_id: Device ID do par em hex (str | None)
                - session_key_set: Se a chave de sessão está definida (bool)
                - harmonic_n: Ordem harmônica configurada (int)
                - replay_window_size: Tamanho da janela anti-replay atual (int)
                - max_sequence_seen: Maior sequência já vista (int)
        """
        return {
            "active": self._session_active,
            "age_ms": self.session_age_ms,
            "packet_count": self.packet_count,
            "peer_device_id": (
                self._session_peer_device_id.hex()
                if self._session_peer_device_id
                else None
            ),
            "session_key_set": self._session_key is not None,
            "harmonic_n": self._harmonic_n,
            "replay_window_size": len(self._replay_window),
            "max_sequence_seen": self._max_sequence_seen,
        }

    # ------------------------------------------------------------------
    # Propriedades
    # ------------------------------------------------------------------

    @property
    def session_active(self) -> bool:
        """Indica se a sessão está atualmente ativa.

        Returns:
            bool: True se autenticado e com sessão válida.
        """
        return self._session_active

    @property
    def session_age_ms(self) -> int:
        """Idade da sessão atual em milissegundos.

        Returns:
            int: Milissegundos desde o início da sessão, ou 0 se inativa.
        """
        if not self._session_active or self._session_start_ms == 0:
            return 0

        now_ms = int(time.time() * 1000) & ((1 << 64) - 1)

        if now_ms >= self._session_start_ms:
            return now_ms - self._session_start_ms
        else:
            # Trata wrapping de uint64
            return (1 << 64) - self._session_start_ms + now_ms

    @property
    def packet_count(self) -> int:
        """Número total de pacotes processados (enviados + recebidos/verificados).

        Returns:
            int: Contagem acumulada de pacotes.
        """
        return self._packet_count

    # ------------------------------------------------------------------
    # Métodos internos
    # ------------------------------------------------------------------

    def _is_replay(self, sequence: int) -> bool:
        """Verifica se um número de sequência já foi processado.

        Utiliza a janela deslizante de sequências para detectar pacotes
        duplicados. Um pacote é considerado replay se:
        - Sua sequência está explicitamente na janela, OU
        - Sua sequência é menor que o máximo visto menos o tamanho da janela
          (exceto para o caso de wrapping de sequência uint32).

        Args:
            sequence: Número de sequência a verificar.

        Returns:
            bool: True se a sequência já foi vista (possível replay).
        """
        # Verificação direta: está na janela?
        if sequence in self._replay_window:
            return True

        # Verificação de janela deslizante: sequência muito antiga?
        # Para evitar falsos positivos no wrapping de uint32, só verificamos
        # se a sequência está "muito atrás" quando o max_sequence_seen é
        # significativamente maior.
        if self._max_sequence_seen > DEFAULT_REPLAY_WINDOW:
            min_acceptable = self._max_sequence_seen - DEFAULT_REPLAY_WINDOW
            if sequence < min_acceptable:
                # Possível replay, mas precisa verificar se não é wrapping
                # Se a diferença é > 2^31, provavelmente é wrapping legítimo
                diff = self._max_sequence_seen - sequence
                if diff < (1 << 31):
                    return True

        return False

    def _mark_sequence(self, sequence: int) -> None:
        """Marca uma sequência como processada na janela anti-replay.

        Args:
            sequence: Número de sequência a registrar.
        """
        self._replay_window.append(sequence)

    def _derive_channel_key(self, channel_index: int) -> bytes:
        """Deriva uma sub-chave para cifragem de canal específico.

        Utiliza SHA-256(session_key || channel_index || context) para
        derivar uma sub-chave única por canal, garantindo que o mesmo
        valor em canais diferentes produz ciphertexts diferentes.

        Args:
            channel_index: Índice do canal harmônico.

        Returns:
            bytes: Sub-chave derivada (32 bytes).
        """
        if self._session_key is None:
            raise RuntimeError("Chave de sessão não disponível")

        import hashlib

        derivation_input = (
            self._session_key
            + struct.pack(">H", channel_index & 0xFFFF)
            + CHANNEL_ENCRYPT_CONTEXT
        )

        return hashlib.sha256(derivation_input).digest()
