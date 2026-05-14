"""Exemplo 3: Motor de Cues e Cena Completa.

Demonstra gravação, execução e serialização de cues teatrais
usando o motor de cue e o parser de cenas.

Execute:
    python -m examples.demo_cue_engine
"""

import json
from src.stage import FixtureController, Fixture, FixtureType, CueEngine, CueStack, SceneParser


def main() -> None:
    print("=" * 60)
    print("Hubstry Harmonic Stage — Motor de Cues")
    print("=" * 60)

    # --- Setup de fixtures ---
    controller = FixtureController(universe_id=0)
    controller.add_fixture(Fixture(
        id="PAR-001", fixture_type=FixtureType.PAR_LED,
        dmx_start_address=1, channel_count=4,
        parameters={"red": 0, "green": 1, "blue": 2, "intensity": 3},
    ))
    controller.add_fixture(Fixture(
        id="MH-001", fixture_type=FixtureType.MOVING_HEAD,
        dmx_start_address=5, channel_count=8,
        parameters={
            "red": 0, "green": 1, "blue": 2, "intensity": 3,
            "pan_lo": 4, "pan_hi": 5, "tilt_lo": 6, "tilt_hi": 7,
        },
    ))

    engine = CueEngine(controller)
    stack = CueStack()

    # --- Cue 1: Blackout ---
    engine.stop()
    cue1 = engine.record_cue("Blackout", fade_in=0.5, fade_out=0.5, hold=0)
    stack.add_cue(cue1)
    print(f"\nCue 1 gravado: {cue1.name} ({len(cue1.values)} canais)")

    # --- Cue 2: Vermelho ---
    controller.set_values("PAR-001", {"red": 1.0, "green": 0.0, "blue": 0.0, "intensity": 1.0})
    controller.set_values("MH-001", {"red": 0.5, "green": 0.0, "blue": 0.0, "intensity": 0.8})
    cue2 = engine.record_cue("Vermelho", fade_in=2.0, fade_out=1.0, hold=5.0)
    stack.add_cue(cue2)
    print(f"Cue 2 gravado: {cue2.name} ({len(cue2.values)} canais)")

    # --- Cue 3: Azul Panorâmico ---
    controller.set_values("PAR-001", {"red": 0.0, "green": 0.2, "blue": 1.0, "intensity": 0.9})
    controller.set_values("MH-001", {"red": 0.0, "green": 0.1, "blue": 0.8, "intensity": 1.0,
                                       "pan_lo": 200, "pan_hi": 55, "tilt_lo": 128, "tilt_hi": 0})
    cue3 = engine.record_cue("Azul Panorâmico", fade_in=3.0, fade_out=2.0, hold=10.0)
    stack.add_cue(cue3)
    print(f"Cue 3 gravado: {cue3.name} ({len(cue3.values)} canais)")

    # --- Execução ---
    print(f"\n--- Execução da CueStack ({len(stack)} cues) ---")
    for pos in range(len(stack)):
        cue = stack.get_cue(pos + 1)
        print(f"  GO {pos + 1}: {cue.name} (fade_in={cue.fade_in}s, hold={cue.hold}s)")

    # --- Serialização ---
    print(f"\n--- Serialização JSON ---")
    json_data = stack.to_json()
    scene_dict = {
        "name": "Show Demo Hubstry",
        "fixtures": [
            {"id": f.id, "type": f.fixture_type.value, "dmx_start": f.dmx_start_address,
             "channels": f.channel_count, "params": f.parameters}
            for f in controller.list_fixtures()
        ],
        "cues": [
            {"name": stack.get_cue(i+1).name,
             "fade_in": stack.get_cue(i+1).fade_in,
             "fade_out": stack.get_cue(i+1).fade_out,
             "hold": stack.get_cue(i+1).hold}
            for i in range(len(stack))
        ],
        "metadata": {"author": "Guilherme Gonçalves Machado", "created_at": "2026-05-15"},
    }
    print(json.dumps(scene_dict, indent=2, ensure_ascii=False))

    # --- Validação de cena ---
    parser = SceneParser()
    scene = parser.from_dict(scene_dict)
    warnings = parser.validate(scene)
    print(f"\nValidação da cena: {len(warnings)} aviso(s)")


if __name__ == "__main__":
    main()
