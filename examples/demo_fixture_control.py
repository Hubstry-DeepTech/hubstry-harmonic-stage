"""Exemplo 2: Controle de Fixtures DMX via Canais Harmônicos.

Demonstra como registrar fixtures, atribuir canais HPG e
controlar parâmetros individuais (RGB, intensidade, pan/tilt).

Execute:
    python -m examples.demo_fixture_control
"""

from src.stage import FixtureController, Fixture, FixtureType


def main() -> None:
    print("=" * 60)
    print("Hubstry Harmonic Stage — Controle de Fixtures")
    print("=" * 60)

    controller = FixtureController(universe_id=0)

    # --- Registrar fixtures ---
    # PAR LED RGB (3 canais)
    par1 = Fixture(
        id="PAR-001",
        fixture_type=FixtureType.PAR_LED,
        dmx_start_address=1,
        channel_count=4,  # R, G, B, Intensity
        parameters={
            "red": 0, "green": 1, "blue": 2, "intensity": 3,
        },
    )

    # Moving Head (8 canais)
    mh1 = Fixture(
        id="MH-001",
        fixture_type=FixtureType.MOVING_HEAD,
        dmx_start_address=5,
        channel_count=8,
        parameters={
            "red": 0, "green": 1, "blue": 2, "intensity": 3,
            "pan_lo": 4, "pan_hi": 5, "tilt_lo": 6, "tilt_hi": 7,
        },
    )

    # Strip LED (3 canais)
    strip1 = Fixture(
        id="STRIP-001",
        fixture_type=FixtureType.STRIP_LED,
        dmx_start_address=13,
        channel_count=3,
        parameters={"red": 0, "green": 1, "blue": 2},
    )

    controller.add_fixture(par1)
    controller.add_fixture(mh1)
    controller.add_fixture(strip1)

    print(f"\nFixtures registrados: {len(controller.list_fixtures())}")
    for f in controller.list_fixtures():
        print(f"  {f['id']:12s} {f['type'].value:15s} DMX {f['dmx_start']:>3d}  {f['channels']}ch")

    # --- Controlar PAR-001: Vermelho puro ---
    print(f"\n--- PAR-001: Vermelho puro ---")
    hpg_updates = controller.set_values("PAR-001", {
        "red": 1.0, "green": 0.0, "blue": 0.0, "intensity": 0.8,
    })
    print(f"  Canais HPG atualizados: {len(hpg_updates)}")
    for ch_idx, val in sorted(hpg_updates.items()):
        print(f"    HPG[{ch_idx:3d}] = {val:.2f}")

    # --- Controlar MH-001: Azul com pan central ---
    print(f"\n--- MH-001: Azul, pan central ---")
    hpg_updates = controller.set_values("MH-001", {
        "red": 0.0, "green": 0.0, "blue": 1.0, "intensity": 1.0,
        "pan_lo": 127, "pan_hi": 127, "tilt_lo": 64, "tilt_hi": 0,
    })
    print(f"  Canais HPG atualizados: {len(hpg_updates)}")

    # --- Estado atual de todas as fixtures ---
    print(f"\n--- Estado completo ---")
    all_hpg = controller.all_to_hpg()
    print(f"  Total de canais HPG ativos: {len(all_hpg)}")
    for ch_idx, val in sorted(all_hpg.items()):
        print(f"    HPG[{ch_idx:3d}] = {val:.4f}")


if __name__ == "__main__":
    main()
