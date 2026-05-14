"""Testes do Mapeador de Canais HPG ↔ DMX512."""

import pytest

from src.core.channel_mapper import ChannelMapper, ChannelMapping


class TestChannelMapper:
    """Testes de conversão entre canais harmônicos e DMX512."""

    @pytest.fixture
    def mapper(self):
        return ChannelMapper(N=16, f0=25.0)

    def test_total_canais(self, mapper):
        assert mapper.total_channels > 0

    def test_fundamental(self, mapper):
        assert mapper.fundamental == 25.0

    def test_mapeamento_hpg_para_dmx(self, mapper):
        assert mapper.map_to_dmx(0) == 1

    def test_mapeamento_dmx_para_hpg(self, mapper):
        assert mapper.map_from_dmx(1) == 0

    def test_round_trip(self, mapper):
        for i in [0, 10, 100]:
            dmx = mapper.map_to_dmx(i)
            hpg = mapper.map_from_dmx(dmx)
            assert hpg == i

    def test_clamping_dmx_max(self, mapper):
        assert mapper.map_to_dmx(0) == 1
        assert mapper.map_to_dmx(mapper.total_channels - 1) <= 512

    def test_frequência_canal_0(self, mapper):
        freq = mapper.get_channel_frequency(0)
        assert freq > 0

    def test_frequência_crescente(self, mapper):
        f0 = mapper.get_channel_frequency(0)
        f1 = mapper.get_channel_frequency(1)
        assert f1 >= f0

    def test_ratio_canal(self, mapper):
        a, b = mapper.get_channel_ratio(0)
        assert a > 0 and b > 0

    def test_fixture_rgb_3ch(self, mapper):
        dmx_start, hpg_end, params = mapper.map_to_fixture(0, fixture_channels=3)
        assert dmx_start == 1
        assert len(params) == 3
        assert "red" in params

    def test_fixture_moving_head_8ch(self, mapper):
        dmx_start, hpg_end, params = mapper.map_to_fixture(5, fixture_channels=8)
        assert dmx_start == 6
        assert len(params) == 8
        assert "pan_lo" in params
        assert "tilt_hi" in params

    def test_reserva_e_liberação(self, mapper):
        total = mapper.available_channels
        mapper.reserve_channel(0)
        assert mapper.available_channels == total - 1
        mapper.free_channel(0)
        assert mapper.available_channels == total

    def test_alocação_fixture(self, mapper):
        total = mapper.available_channels
        start, end = mapper.allocate_fixture("LED-001", 4)
        assert start >= 0
        assert end >= start
        assert end - start + 1 == 4
        assert mapper.available_channels == total - 4
        mapper.release_fixture("LED-001")
        assert mapper.available_channels == total

    def test_alocação_fixture_insuficiente(self, mapper):
        with pytest.raises(ValueError):
            mapper.allocate_fixture("BIG-001", mapper.total_channels + 1)

    def test_fixture_não_encontrada(self, mapper):
        with pytest.raises(KeyError):
            mapper.release_fixture("INEXISTENTE")

    def test_mapeamento_completo(self, mapper):
        full = mapper.get_full_mapping()
        assert len(full) == mapper.total_channels
        assert all(isinstance(m, ChannelMapping) for m in full)

    def test_summary(self, mapper):
        s = mapper.summary()
        assert s["total_channels"] > 0
        assert s["available"] == s["total_channels"]
        assert s["fundamental_hz"] == 25.0
        assert s["harmonic_order"] == 16
