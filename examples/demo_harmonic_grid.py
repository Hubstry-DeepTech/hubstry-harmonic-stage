"""Exemplo 1: Demonstração da Grade Harmônica H_16.

Este exemplo mostra como gerar o conjunto H_16, mapear para frequências
e endereços DMX, e exibir um resumo das capacidades do protocolo.

Execute:
    python -m examples.demo_harmonic_grid
"""

from src.core import HarmonicGrid, RationalSet


def main() -> None:
    print("=" * 60)
    print("Hubstry Harmonic Stage — Demonstração da Grade Harmônica")
    print("=" * 60)

    # --- Conjunto Racional H_16 ---
    rs = RationalSet(N=16)
    print(f"\nConjunto Racional H_16:")
    print(f"  Elementos: {rs.size}")
    print(f"  Isomorfo a Q⁺: {rs.isomorphic_to_q()}")
    print(f"  Resumo: {rs.summary()}")

    # --- Primeiros 10 canais ---
    print(f"\nPrimeiros 10 canais de H_16:")
    print(f"  {'Fração':>8}  {'Valor':>8}  {'Freq (25 Hz)':>12}")
    print(f"  {'-'*32}")
    for pair in list(rs)[:10]:
        freq = pair.value * 25.0
        print(f"  {pair.numerator:>3}/{pair.denominator:<3}  {pair.value:>8.4f}  {freq:>12.2f} Hz")

    # --- Grade Harmônica Completa ---
    grid = HarmonicGrid(N=16, f0=25.0)
    print(f"\nGrade Harmônica: {grid}")

    # --- Reserva de canais ---
    grid.reserve_channel(0, "Fixture LED-001 Red")
    grid.reserve_channel(1, "Fixture LED-001 Green")
    grid.reserve_channel(2, "Fixture LED-001 Blue")
    print(f"\nApós reservar 3 canais para RGB:")
    summary = grid.summary()
    print(f"  Total:      {summary['total_channels']}")
    print(f"  Reservados: {summary['reserved']}")
    print(f"  Disponíveis:{summary['available']}")
    print(f"  Faixa freq: {summary['freq_min_hz']:.2f} — {summary['freq_max_hz']:.2f} Hz")

    # --- Exportar configuração ---
    config = grid.export_config()
    import json
    print(f"\nConfiguração exportada: {len(config['channels'])} canais")

    # Libera reservas
    grid.free_channel(0)
    grid.free_channel(1)
    grid.free_channel(2)
    print(f"Canais liberados. Disponíveis: {grid.summary()['available']}")


if __name__ == "__main__":
    main()
