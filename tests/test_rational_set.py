"""Testes do Conjunto Racional Harmônico H_N."""

import math
import pytest

from src.core.rational_set import RationalPair, RationalSet


class TestRationalPair:
    """Testes do par racional irredutível."""

    def test_criacao_valida(self):
        p = RationalPair(3, 4)
        assert p.numerator == 3
        assert p.denominator == 4
        assert p.value == pytest.approx(0.75)

    def test_fração_irredutível_obrigatória(self):
        with pytest.raises(ValueError, match="não irredutível"):
            RationalPair(2, 4)

    def test_denominador_positivo(self):
        with pytest.raises(ValueError, match="Denominador deve ser positivo"):
            RationalPair(1, -1)

    def test_numerador_positivo(self):
        with pytest.raises(ValueError, match="Numerador deve ser positivo"):
            RationalPair(0, 1)

    def test_comparação(self):
        assert RationalPair(1, 2) < RationalPair(2, 3)

    def test_repr(self):
        p = RationalPair(1, 3)
        assert "1/3" in repr(p)


class TestRationalSet:
    """Testes do conjunto H_N."""

    def test_tamanho_h4(self):
        rs = RationalSet(N=4)
        assert rs.size > 0
        assert rs.size == len(rs.fractions)

    def test_tamanho_h16(self):
        rs = RationalSet(N=16)
        assert rs.size > 0

    def test_contém_par_válido(self):
        rs = RationalSet(N=16)
        assert RationalPair(1, 1) in rs
        assert RationalPair(3, 2) in rs

    def test_não_contém_não_irredutível(self):
        """Fração não irredutível não deve estar no conjunto."""
        rs = RationalSet(N=16)
        # 2/4 = 1/2 já está no conjunto como 1/2, não como 2/4
        # RationalPair(2,4) lança ValueError, então verificamos via tuple
        result = (2, 4) in rs
        assert result is False

    def test_fracoes_ordenadas(self):
        rs = RationalSet(N=4)
        valores = [f.value for f in rs.fractions]
        assert valores == sorted(valores)

    def test_frequências(self):
        rs = RationalSet(N=4)
        f0 = 440.0
        freqs = rs.to_frequencies(f0)
        assert len(freqs) == rs.size
        assert freqs[0][1] == pytest.approx(rs.fractions[0].value * f0)

    def test_isomorfismo_q(self):
        rs = RationalSet(N=16)
        assert rs.isomorphic_to_q() is True

    def test_summary(self):
        rs = RationalSet(N=16)
        s = rs.summary()
        assert s["N"] == 16
        assert s["size"] > 0
        assert s["min"] > 0
        assert s["max"] <= 16 + 1e-9

    def test_n_inválido(self):
        with pytest.raises(ValueError):
            RationalSet(N=0)

    def test_iteração(self):
        rs = RationalSet(N=2)
        count = 0
        for _ in rs:
            count += 1
        assert count == rs.size

    def test_h32_maior_que_h16(self):
        rs16 = RationalSet(N=16)
        rs32 = RationalSet(N=32)
        assert rs32.size > rs16.size
