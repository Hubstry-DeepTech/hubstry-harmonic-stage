"""Testes da Grade Harmônica (fachada)."""

import json
import pytest

from src.core.harmonic_grid import HarmonicGrid


class TestHarmonicGrid:
    """Testes da fachada HarmonicGrid."""

    @pytest.fixture
    def grid(self):
        return HarmonicGrid(N=16, f0=25.0)

    def test_criação(self, grid):
        assert grid.total_channels > 0
        assert grid.fundamental == 25.0
        assert grid.max_harmonic == 16

    def test_canal_individual(self, grid):
        ch = grid.get_channel(0)
        assert ch["index"] == 0
        assert ch["ratio"][0] > 0
        assert ch["frequency"] > 0
        assert ch["dmx_address"] == 1
        assert ch["reserved"] is False

    def test_todos_canais(self, grid):
        canais = grid.get_channels()
        assert len(canais) == grid.total_channels
        assert canais[0]["index"] == 0

    def test_reserva(self, grid):
        total = grid.summary()["available"]
        grid.reserve_channel(0, "teste")
        assert grid.get_channel(0)["reserved"] is True
        assert grid.get_channel(0)["purpose"] == "teste"
        assert len(grid.available_channels()) == total - 1

    def test_reserva_duplicada(self, grid):
        grid.reserve_channel(0)
        with pytest.raises(ValueError, match="já reservado"):
            grid.reserve_channel(0)

    def test_reserva_fora_do_intervalo(self, grid):
        with pytest.raises(IndexError):
            grid.reserve_channel(-1)

    def test_liberação(self, grid):
        total = grid.summary()["available"]
        grid.reserve_channel(0)
        grid.free_channel(0)
        assert grid.get_channel(0)["reserved"] is False
        assert len(grid.available_channels()) == total

    def test_disponíveis(self, grid):
        grid.reserve_channel(0)
        grid.reserve_channel(10)
        grid.reserve_channel(100)
        disp = grid.available_channels()
        assert 0 not in disp
        assert 10 not in disp
        assert 100 not in disp
        assert 1 in disp

    def test_summary(self, grid):
        s = grid.summary()
        assert s["total_channels"] > 0
        assert s["available"] == s["total_channels"]
        assert s["reserved"] == 0
        assert s["fundamental_hz"] == 25.0

    def test_export_config(self, grid):
        config = grid.export_config()
        assert config["total_channels"] > 0
        assert len(config["channels"]) == grid.total_channels
        assert config["harmonic_order"] == 16
        json_str = json.dumps(config)
        assert len(json_str) > 0

    def test_repr(self, grid):
        r = repr(grid)
        assert "HarmonicGrid" in r
        assert "16" in r


class TestHarmonicGridH4:
    """Testes com H_4."""

    def test_h4_tamanho(self):
        grid = HarmonicGrid(N=4, f0=440.0)
        assert grid.total_channels > 0
        assert grid.fundamental == 440.0

    def test_h4_export(self):
        grid = HarmonicGrid(N=4, f0=100.0)
        config = grid.export_config()
        json.dumps(config)
