"""Hubstry Harmonic Stage - Transporte UDP/Art-Net

Implementação do transporte de pacotes HStage via UDP, com suporte a broadcast,
multicast e compatibilidade com o protocolo Art-Net (porta padrão 6454).

Notas de compatibilidade com Art-Net:
    - A porta padrão 6454 é a mesma do Art-Net (Art-Net IV), permitindo
      coexistência na mesma rede sem conflitos de firewall.
    - O formato de pacote HStage é **incompatível** com Art-Net DMX; dispositivos
      que falam Art-Net nativo não interpretarão pacotes HStage e vice-versa.
    - Para interoperabilidade dual (Art-Net + HStage), utilize instâncias
      de transporte separadas em portas diferentes, ou implemente um bridge
      que traduza entre os formatos.
    - O multicast padrão (239.255.0.1) difere do Art-Net broadcast padrão
      (2.255.255.255 ou broadcast de subnet), permitindo isolamento quando
      necessário.

Arquitetura de transporte:
    ┌─────────────────────────────────────────┐
    │           HStageTransport               │
    │  ┌───────────┐  ┌────────────────────┐  │
    │  │ UDP Socket │  │ Heartbeat Thread   │  │
    │  │ (IPv4)    │  │ (periodic keepalive)│  │
    │  └───────────┘  └────────────────────┘  │
    │  ┌───────────────────────────────────┐  │
    │  │ Estatísticas (tx/rx/erros/bytes) │  │
    │  └───────────────────────────────────┘  │
    └─────────────────────────────────────────┘

Dependências: apenas stdlib (socket, threading, time).
"""

from __future__ import annotations

import socket
import struct
import threading
import time
from typing import TYPE_CHECKING

from .packet import HStagePacket, PacketType

if TYPE_CHECKING:
    from typing import Optional


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

#: Porta padrão para transporte HStage (igual ao Art-Net para compatibilidade)
DEFAULT_PORT: int = 6454

#: Endereço de bind padrão (todas as interfaces)
DEFAULT_BIND_ADDRESS: str = "0.0.0.0"

#: Grupo multicast padrão (range administrativo local)
DEFAULT_MULTICAST_GROUP: str = "239.255.0.1"

#: TTL padrão para pacotes multicast
DEFAULT_MULTICAST_TTL: int = 1

 #: Endereço de broadcast de subnet padrão
BROADCAST_ADDRESS: str = "255.255.255.255"

#: Tamanho máximo do buffer de recepção UDP
RECV_BUFFER_SIZE: int = 65535

 #: Intervalo padrão de heartbeat em segundos
DEFAULT_HEARTBEAT_INTERVAL: float = 2.0


class HStageTransport:
    """Transporte UDP para pacotes HStage com suporte a Art-Net.

    Gerencia a comunicação via UDP para transmissão e recepção de pacotes
    HStage, com suporte a unicast, broadcast e multicast. Projetado para
    operar na mesma porta do Art-Net (6454) para simplificar a configuração
    de rede em ambientes de palco.

    O transporte é thread-safe: send() e receive() podem ser chamados de
    threads diferentes. O heartbeat opera em thread dedicada.

    Compatibilidade com Art-Net:
        - Porta padrão 6454 (mesma do Art-Net IV).
        - Broadcast para subnet (255.255.255.255) para descoberta de dispositivos.
        - Multicast para comunicação direcionada (239.255.0.1).
        - Formato de pacote HStage independente (não interoperável com Art-Net DMX).

    Args:
        bind_address: Endereço local para bind do socket (padrão: "0.0.0.0").
        port: Porta UDP para bind (padrão: 6454, mesma do Art-Net).
        multicast_group: Grupo multicast para joins, ou None para desabilitar.

    Exemplo::

        >>> transport = HStageTransport(port=6454)
        >>> pkt = HStagePacket(packet_type=PacketType.DATA, sequence=1)
        >>> transport.send(pkt, destination="192.168.1.100", port=6454)
        4
        >>> received = transport.receive(timeout=1.0)
    """

    def __init__(
        self,
        bind_address: str = DEFAULT_BIND_ADDRESS,
        port: int = DEFAULT_PORT,
        multicast_group: str | None = None,
    ) -> None:
        """Inicializa o transporte UDP HStage.

        Cria e configura o socket UDP IPv4 com opções de broadcast e
        reutilização de endereço (SO_REUSEADDR). Se um grupo multicast
        for especificado, faz o join automaticamente.

        Args:
            bind_address: Endereço local para bind (padrão: "0.0.0.0").
            port: Porta UDP (padrão: 6454).
            multicast_group: Grupo multicast para join (padrão: None).
        """
        self._bind_address = bind_address
        self._port = port
        self._multicast_group = multicast_group

        # Estatísticas
        self._stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "errors": 0,
            "last_error": None,
            "last_send_time": 0.0,
            "last_receive_time": 0.0,
        }

        # Lock para thread-safety nas estatísticas
        self._stats_lock = threading.Lock()

        # Socket UDP
        self._socket: socket.socket | None = None
        self._create_socket()

        # Heartbeat
        self._heartbeat_thread: threading.Thread | None = None
        self._heartbeat_running = False
        self._heartbeat_interval: float = DEFAULT_HEARTBEAT_INTERVAL
        self._heartbeat_sequence: int = 0

    def _create_socket(self) -> None:
        """Cria e configura o socket UDP com opções adequadas.

        Configurações aplicadas:
        - SO_REUSEADDR: Permite rebind rápido (útil durante restarts).
        - SO_BROADCAST: Habilita envio de pacotes broadcast.
        - SO_RCVBUF: Buffer de recepção de 64KB.
        """
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, RECV_BUFFER_SIZE)
            sock.settimeout(0.5)  # Timeout curto para operações padrão
            sock.bind((self._bind_address, self._port))

            # Join multicast se configurado
            if self._multicast_group is not None:
                self._join_multicast(sock)

            self._socket = sock

        except OSError as e:
            self._record_error(f"falha ao criar socket: {e}")
            raise

    def _join_multicast(self, sock: socket.socket) -> None:
        """Faz join em um grupo multicast no socket especificado.

        Args:
            sock: Socket UDP configurado para multicast.
        """
        try:
            group = socket.inet_aton(self._multicast_group)
            mreq = struct.pack("4sL", group, socket.INADDR_ANY)
            sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq
            )

            # Configura TTL multicast (escopo local)
            sock.setsockopt(
                socket.IPPROTO_IP, socket.IP_MULTICAST_TTL,
                DEFAULT_MULTICAST_TTL,
            )

        except OSError as e:
            self._record_error(f"falha ao join multicast {self._multicast_group}: {e}")

    def send(
        self, packet: HStagePacket, destination: str, port: int
    ) -> int:
        """Envia um pacote HStage para um destino específico via UDP.

        Serializa o pacote e envia como datagrama UDP unicast. O envio é
        thread-safe e atualiza as estatísticas de transmissão.

        Args:
            packet: Pacote HStage a ser enviado.
            destination: Endereço IP de destino.
            port: Porta UDP de destino.

        Returns:
            int: Número de bytes enviados.

        Raises:
            RuntimeError: Se o socket não estiver inicializado.
            OSError: Se houver erro de rede no envio.
        """
        if self._socket is None:
            raise RuntimeError("Socket não inicializado")

        data = packet.to_bytes()

        try:
            bytes_sent = self._socket.sendto(data, (destination, port))

            with self._stats_lock:
                self._stats["packets_sent"] += 1
                self._stats["bytes_sent"] += bytes_sent
                self._stats["last_send_time"] = time.monotonic()

            return bytes_sent

        except OSError as e:
            self._record_error(f"falha no envio para {destination}:{port}: {e}")
            raise

    def receive(self, timeout: float = 1.0) -> HStagePacket | None:
        """Recebe um pacote HStage com timeout.

        Aguarda por um datagrama UDP, desserializa como HStagePacket e
        atualiza as estatísticas de recepção. Se o timeout expirar sem
        receber dados, retorna None.

        Args:
            timeout: Tempo máximo de espera em segundos (padrão: 1.0).

        Returns:
            HStagePacket | None: Pacote recebido, ou None se timeout.

        Note:
            Pacotes malformados são descartados silenciosamente e contabilizados
            como erros nas estatísticas, sem levantar exceções.
        """
        if self._socket is None:
            raise RuntimeError("Socket não inicializado")

        original_timeout = self._socket.gettimeout()
        self._socket.settimeout(timeout)

        try:
            data, _addr = self._socket.recvfrom(RECV_BUFFER_SIZE)

            try:
                packet = HStagePacket.from_bytes(data)

                with self._stats_lock:
                    self._stats["packets_received"] += 1
                    self._stats["bytes_received"] += len(data)
                    self._stats["last_receive_time"] = time.monotonic()

                return packet

            except (ValueError, struct.error) as e:
                self._record_error(f"pacote malformado recebido: {e}")
                return None

        except socket.timeout:
            return None

        except OSError as e:
            self._record_error(f"erro na recepção: {e}")
            return None

        finally:
            self._socket.settimeout(original_timeout)

    def broadcast(self, packet: HStagePacket) -> None:
        """Envia um pacote para todos os dispositivos na rede.

        Se um grupo multicast estiver configurado, envia para o grupo.
        Caso contrário, envia como broadcast de subnet (255.255.255.255).

        O broadcast é utilizado para descoberta de dispositivos e
        distribuição de comandos para todos os nós simultaneamente.

        Args:
            packet: Pacote HStage a ser transmitido.

        Note:
            Em redes com roteadores entre segmentos, broadcast não atravessa.
            Utilize multicast para alcance multi-segmento.
        """
        if self._multicast_group is not None:
            destination = self._multicast_group
        else:
            destination = BROADCAST_ADDRESS

        try:
            self.send(packet, destination, self._port)
        except OSError:
            # Erro já registrado por send()
            pass

    def start_heartbeat(self, interval: float = DEFAULT_HEARTBEAT_INTERVAL) -> None:
        """Inicia a thread de heartbeat periódico.

        Envia pacotes HEARTBEAT em intervalo regular para manter a presença
        do dispositivo visível na rede. Heartbeats são essenciais para:
        - Detecção de dispositivos ativos por controladores.
        - Manutenção de entradas NAT em firewalls.
        - Monitoramento de latência e jitter.

        Args:
            interval: Intervalo entre heartbeats em segundos (padrão: 2.0).

        Raises:
            RuntimeError: Se o heartbeat já estiver em execução.
        """
        if self._heartbeat_running:
            raise RuntimeError("Heartbeat já está em execução")

        self._heartbeat_interval = interval
        self._heartbeat_running = True
        self._heartbeat_sequence = 0

        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop,
            name="hstage-heartbeat",
            daemon=True,
        )
        self._heartbeat_thread.start()

    def stop_heartbeat(self) -> None:
        """Para a thread de heartbeat periódico.

        Aguarda a finalização da thread com timeout de 2× o intervalo
        de heartbeat para garantir parada limpa.
        """
        if not self._heartbeat_running:
            return

        self._heartbeat_running = False

        if self._heartbeat_thread is not None:
            self._heartbeat_thread.join(timeout=self._heartbeat_interval * 2)
            if self._heartbeat_thread.is_alive():
                self._record_error("heartbeat thread não terminou no timeout")
            self._heartbeat_thread = None

    def _heartbeat_loop(self) -> None:
        """Loop principal da thread de heartbeat."""
        while self._heartbeat_running:
            try:
                self._heartbeat_sequence = (
                    self._heartbeat_sequence + 1
                ) & 0xFFFF  # wrapping uint16

                heartbeat_pkt = HStagePacket(
                    packet_type=PacketType.HEARTBEAT,
                    sequence=self._heartbeat_sequence,
                    channel_count=0,
                    channels=[],
                )

                self.broadcast(heartbeat_pkt)

            except Exception as e:
                self._record_error(f"erro no heartbeat: {e}")

            # Dorme respeitando o flag de parada
            deadline = time.monotonic() + self._heartbeat_interval
            while self._heartbeat_running and time.monotonic() < deadline:
                time.sleep(0.1)

    def get_stats(self) -> dict:
        """Retorna estatísticas acumuladas do transporte.

        Returns:
            dict: Dicionário com:
                - packets_sent: Total de pacotes enviados (int)
                - packets_received: Total de pacotes recebidos (int)
                - bytes_sent: Total de bytes enviados (int)
                - bytes_received: Total de bytes recebidos (int)
                - errors: Total de erros (int)
                - last_error: Último erro registrado (str | None)
                - last_send_time: Timestamp monotônico do último envio (float)
                - last_receive_time: Timestamp monotônico da última recepção (float)
                - heartbeat_active: Se o heartbeat está em execução (bool)
                - heartbeat_interval: Intervalo do heartbeat em segundos (float)
        """
        with self._stats_lock:
            return {
                "packets_sent": self._stats["packets_sent"],
                "packets_received": self._stats["packets_received"],
                "bytes_sent": self._stats["bytes_sent"],
                "bytes_received": self._stats["bytes_received"],
                "errors": self._stats["errors"],
                "last_error": self._stats["last_error"],
                "last_send_time": self._stats["last_send_time"],
                "last_receive_time": self._stats["last_receive_time"],
                "heartbeat_active": self._heartbeat_running,
                "heartbeat_interval": self._heartbeat_interval,
            }

    def _record_error(self, message: str) -> None:
        """Registra um erro nas estatísticas de forma thread-safe.

        Args:
            message: Descrição do erro.
        """
        with self._stats_lock:
            self._stats["errors"] += 1
            self._stats["last_error"] = message

    # ------------------------------------------------------------------
    # Gerenciamento de recursos
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Fecha o socket e para o heartbeat.

        Deve ser chamado ao encerrar o uso do transporte para liberar
        recursos do sistema operacional (file descriptors, threads).
        """
        self.stop_heartbeat()

        if self._socket is not None:
            try:
                # Sai do multicast group se configurado
                if self._multicast_group is not None:
                    try:
                        group = socket.inet_aton(self._multicast_group)
                        mreq = struct.pack("4sL", group, socket.INADDR_ANY)
                        self._socket.setsockopt(
                            socket.IPPROTO_IP,
                            socket.IP_DROP_MEMBERSHIP,
                            mreq,
                        )
                    except OSError:
                        pass

                self._socket.close()

            except OSError:
                pass

            finally:
                self._socket = None

    def __enter__(self) -> HStageTransport:
        """Suporte a context manager (with statement)."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Fecha recursos ao sair do context manager."""
        self.close()

    def __del__(self) -> None:
        """Destrutor: garante liberação de recursos."""
        self.close()
