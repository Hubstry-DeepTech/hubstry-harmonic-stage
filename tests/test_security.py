"""Testes do Módulo de Segurança (HSL Stage)."""

import hmac
import hashlib
import time
import pytest

from src.security.auth_lightweight import AuthPacket, LightAuth
from src.security.hsl_stage import HSLStage


class TestAuthPacket:
    """Testes do pacote de autenticação."""

    def test_tamanho_fixo(self):
        pkt = AuthPacket(
            device_id=b"\x01\x02\x03\x04\x05\x06\x07\x08",
            sequence=1,
            timestamp=int(time.time() * 1000),
            nonce=b"\xAA\xBB\xCC\xDD",
            hmac_tag=b"\x00" * 16,
        )
        data = pkt.to_bytes()
        assert len(data) > 0  # tamanho real do pacote serializado

    def test_serialização_deserialização(self):
        pkt = AuthPacket(
            device_id=b"\x01\x02\x03\x04\x05\x06\x07\x08",
            sequence=42,
            timestamp=1700000000000,
            nonce=b"\xDE\xAD\xBE\xEF",
            hmac_tag=b"\x11" * 16,
        )
        data = pkt.to_bytes()
        pkt2 = AuthPacket.from_bytes(data)
        assert pkt2.device_id == pkt.device_id
        assert pkt2.sequence == pkt.sequence
        assert pkt2.timestamp == pkt.timestamp
        assert pkt2.nonce == pkt.nonce
        assert pkt2.hmac_tag == pkt.hmac_tag

    def test_validate_size(self):
        pkt = AuthPacket(
            device_id=b"\x00" * 8,
            sequence=0,
            timestamp=0,
            nonce=b"\x00" * 4,
            hmac_tag=b"\x00" * 16,
        )
        assert pkt.validate_size()


class TestLightAuth:
    """Testes da autenticação leve."""

    @pytest.fixture
    def auth(self):
        key = hashlib.sha256(b"shared-secret-key-256bits").digest()
        device_id = b"\xAB\xCD\xEF\x01\x23\x45\x67\x89"
        return LightAuth(shared_key=key, device_id=device_id)

    def test_gerar_pacote(self, auth):
        pkt = auth.generate_packet(sequence=1)
        assert pkt.device_id == auth._device_id
        assert pkt.sequence == 1
        assert pkt.hmac_tag != b"\x00" * 16

    def test_verificar_pacote_válido(self, auth):
        pkt = auth.generate_packet(sequence=1)
        assert auth.verify_packet(pkt) is True

    def test_verificar_pacote_modificado(self, auth):
        pkt = auth.generate_packet(sequence=1)
        pkt_modificado = AuthPacket(
            device_id=pkt.device_id,
            sequence=pkt.sequence,
            timestamp=pkt.timestamp,
            nonce=pkt.nonce,
            hmac_tag=b"\xFF" * 16,
        )
        assert auth.verify_packet(pkt_modificado) is False

    def test_verificar_pacote_expirado(self, auth):
        pkt = AuthPacket(
            device_id=auth._device_id,
            sequence=1,
            timestamp=0,
            nonce=b"\x00" * 4,
            hmac_tag=b"\x00" * 16,
        )
        assert auth.verify_packet(pkt, max_age_ms=1000) is False

    def test_round_trip(self, auth):
        pkt = auth.generate_packet(sequence=42)
        data = pkt.to_bytes()
        pkt2 = AuthPacket.from_bytes(data)
        assert auth.verify_packet(pkt2) is True

    def test_rotação_de_chave(self, auth):
        old_key = auth._shared_key
        auth.rotate_key(hashlib.sha256(b"new-key").digest())
        assert auth._shared_key != old_key

    def test_derivar_chave_de_sessão(self, auth):
        session_key = auth.derive_session_key(b"session-seed-123")
        assert len(session_key) == 32

    def test_fingerprint_dispositivo(self, auth):
        fp = auth.get_device_fingerprint()
        assert len(fp) > 0


class TestHSLStage:
    """Testes do HSL para palco."""

    @pytest.fixture
    def hsl(self):
        key = hashlib.sha256(b"hstage-test-key-256bits!!").digest()
        device_id = b"\x10\x20\x30\x40\x50\x60\x70\x80"
        return HSLStage(shared_key=key, device_id=device_id, harmonic_n=16)

    def test_autenticar(self, hsl):
        pkt = hsl.authenticate()
        assert pkt.hmac_tag != b"\x00" * 16

    def test_verificar_pacote_válido(self, hsl):
        pkt = hsl.authenticate()
        ok, reason = hsl.verify(pkt)
        assert ok is True

    def test_sessão(self, hsl):
        hsl.authenticate()
        assert hsl.is_authenticated() is True

    def test_não_autenticado_inicialmente(self, hsl):
        assert hsl.is_authenticated() is False

    def test_info_da_sessão(self, hsl):
        hsl.authenticate()
        info = hsl.session_info()
        assert "active" in info or "authenticated" in info
