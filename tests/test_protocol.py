"""Testes do Módulo de Protocolo (pacotes e transporte)."""

import pytest

from src.protocol.packet import HStagePacket, PacketType


class TestHStagePacket:
    """Testes de serialização de pacotes HStage."""

    def test_criação_pacote_data(self):
        pkt = HStagePacket(
            packet_type=PacketType.DATA,
            sequence=1,
            harmonic_n=16,
            channel_count=3,
            channels=[(0, 1.0), (1, 0.5), (2, 0.0)],
        )
        assert pkt.packet_type == PacketType.DATA
        assert pkt.channel_count == 3
        assert len(pkt.channels) == 3

    def test_serialização_deserialização(self):
        original = HStagePacket(
            packet_type=PacketType.DATA,
            sequence=42,
            harmonic_n=16,
            channel_count=2,
            channels=[(0, 1.0), (1, 0.5)],
            auth_tag=b"\x00" * 16,
            timestamp=1700000000000,
        )
        data = original.to_bytes()
        restored = HStagePacket.from_bytes(data)
        assert restored.packet_type == original.packet_type
        assert restored.sequence == original.sequence
        assert restored.harmonic_n == original.harmonic_n
        assert restored.channel_count == original.channel_count
        assert len(restored.channels) == 2
        assert abs(restored.channels[0][1] - 1.0) < 0.01
        assert abs(restored.channels[1][1] - 0.5) < 0.01

    def test_pacote_auth(self):
        pkt = HStagePacket(
            packet_type=PacketType.AUTH,
            sequence=0,
            harmonic_n=16,
            channel_count=0,
            channels=[],
            auth_tag=b"\xAB" * 16,
        )
        assert pkt.is_securable() is True

    def test_pacote_sem_auth(self):
        pkt = HStagePacket(
            packet_type=PacketType.HEARTBEAT,
            sequence=0,
            harmonic_n=16,
            channel_count=0,
            channels=[],
        )
        assert pkt.is_securable() is False

    def test_estimate_size(self):
        pkt = HStagePacket(
            packet_type=PacketType.DATA,
            sequence=1,
            harmonic_n=16,
            channel_count=10,
            channels=[(i, 0.5) for i in range(10)],
        )
        size = pkt.estimate_size()
        assert size > 0

    def test_max_canais_por_pacote(self):
        max_ch = HStagePacket.max_channels_per_packet(16)
        assert max_ch > 100
        assert max_ch <= 500


class TestPacketType:
    """Testes do enum de tipos de pacote."""

    def test_tipos_unicos(self):
        tipos = list(PacketType)
        assert len(tipos) >= 6  # DATA, AUTH, HEARTBEAT, CUE_TRIGGER, CONFIG, SYNC

    def test_valores_unicos(self):
        valores = [t.value for t in PacketType]
        assert len(valores) == len(set(valores))
