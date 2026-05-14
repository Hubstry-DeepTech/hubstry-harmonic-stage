"""Hubstry Harmonic Stage - Core Module

Módulo central do protocolo harmônico para indústria criativa.
Baseado no HPG 1.0 (DOI: 10.5281/zenodo.19056387).

O HPG define canais de comunicação como frações racionais irredutíveis
de uma frequência fundamental f₀: f(a,b) = (a/b) × f₀, onde mdc(a,b) = 1.
O conjunto H_N é isomorfo a Q⁺ — infinitamente enumerável e denso em R⁺.
"""

from .harmonic_grid import HarmonicGrid
from .channel_mapper import ChannelMapper
from .rational_set import RationalSet

__all__ = ["HarmonicGrid", "ChannelMapper", "RationalSet"]
__version__ = "0.1.0"
