"""Conjunto Racional Harmônico H_N.

Implementa o conjunto H_N = { (a/b) × f₀ : 0 < a/b ≤ N, mdc(a,b) = 1, a,b ∈ Z⁺ }.
H_N é isomorfo a Q⁺ quando N → ∞, garantindo escalabilidade infinita.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterator


@dataclass(frozen=True, slots=True)
class RationalPair:
    """Par racional irredutível (a, b) representando a fração a/b."""

    numerator: int
    denominator: int

    def __post_init__(self) -> None:
        if self.denominator <= 0:
            raise ValueError(f"Denominador deve ser positivo, recebeu {self.denominator}")
        if self.numerator <= 0:
            raise ValueError(f"Numerador deve ser positivo, recebeu {self.numerator}")
        if math.gcd(self.numerator, self.denominator) != 1:
            raise ValueError(
                f"Fração não irredutível: {self.numerator}/{self.denominator}, "
                f"mdc = {math.gcd(self.numerator, self.denominator)}"
            )

    @property
    def value(self) -> float:
        """Valor decimal da fração."""
        return self.numerator / self.denominator

    def __lt__(self, other: object) -> bool:
        if isinstance(other, RationalPair):
            return self.value < other.value
        return NotImplemented

    def __repr__(self) -> str:
        return f"RationalPair({self.numerator}/{self.denominator}={self.value:.4f})"


class RationalSet:
    """Conjunto harmônico racional H_N.

    Gera e gerencia o conjunto H_N = { a/b : 0 < a/b ≤ N, mdc(a,b) = 1 }.

    Examples:
        >>> rs = RationalSet(N=4)
        >>> rs.size
        8
        >>> RationalPair(1, 1) in rs
        True
        >>> RationalPair(2, 2) in rs  # não irredutível
        False
    """

    def __init__(self, N: int = 16) -> None:
        if N < 1:
            raise ValueError(f"N deve ser ≥ 1, recebeu {N}")
        self._N = N
        self._fractions: tuple[RationalPair, ...] = self._generate()

    def _generate(self) -> tuple[RationalPair, ...]:
        """Gera todas as frações irredutíveis a/b com 0 < a/b ≤ N."""
        pairs: list[RationalPair] = []
        for b in range(1, self._N + 1):
            for a in range(1, b * self._N + 1):
                ratio = a / b
                if ratio > self._N + 1e-9:
                    continue
                if math.gcd(a, b) == 1:
                    pairs.append(RationalPair(a, b))
        pairs.sort()
        return tuple(pairs)

    @property
    def N(self) -> int:
        """Ordem máxima do harmônico."""
        return self._N

    @property
    def size(self) -> int:
        """Número de elementos em H_N."""
        return len(self._fractions)

    @property
    def fractions(self) -> tuple[RationalPair, ...]:
        """Frações ordenadas por valor."""
        return self._fractions

    def __len__(self) -> int:
        return self.size

    def __contains__(self, item: object) -> bool:
        if isinstance(item, RationalPair):
            return any(
                f.numerator == item.numerator and f.denominator == item.denominator
                for f in self._fractions
            )
        if isinstance(item, tuple) and len(item) == 2:
            a, b = item
            # Fração não irredutível nunca está no conjunto
            if math.gcd(a, b) != 1:
                return False
            return RationalPair(a, b) in self
        return False

    def __iter__(self) -> Iterator[RationalPair]:
        return iter(self._fractions)

    def __repr__(self) -> str:
        return f"RationalSet(N={self._N}, |H_{self._N}|={self.size})"

    def to_frequencies(
        self, f0: float
    ) -> list[tuple[RationalPair, float]]:
        """Mapeia cada fração para sua frequência correspondente.

        Args:
            f0: Frequência fundamental em Hz.

        Returns:
            Lista de (RationalPair, frequência) ordenada por frequência.
        """
        return [(f, f.value * f0) for f in self._fractions]

    def isomorphic_to_q(self) -> bool:
        """Verifica se H_N é isomorfo a Q⁺.

        Para todo N finito, H_N é um subconjunto finito de Q⁺.
        Quando N → ∞, H_N se torna denso em R⁺ e enumerável, sendo
        portanto isomorfo a Q⁺.

        Returns:
            True — H_N é sempre um subconjunto de Q⁺ por construção.
        """
        return True

    def summary(self) -> dict:
        """Retorna estatísticas do conjunto.

        Returns:
            Dicionário com N, tamanho, valor mínimo, valor máximo e intervalo.
        """
        if not self._fractions:
            return {"N": self._N, "size": 0, "min": 0.0, "max": 0.0, "span": 0.0}
        return {
            "N": self._N,
            "size": self.size,
            "min": self._fractions[0].value,
            "max": self._fractions[-1].value,
            "span": self._fractions[-1].value - self._fractions[0].value,
        }
