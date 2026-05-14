"""Hubstry Harmonic Stage — Interface de Linha de Comando.

CLI para gerenciar canais harmônicos, fixtures e cenas.

Uso:
    hstage info              — informações da grade harmônica
    hstage channels          — listar canais H_N
    hstage export            — exportar configuração como JSON
    hstage scene <arquivo>   — carregar e validar cena
    hstage version           — versão do pacote
"""

from __future__ import annotations

import argparse
import json
import sys


def cmd_info(args: argparse.Namespace) -> None:
    """Exibe informações resumidas da grade harmônica."""
    from src.core import HarmonicGrid

    grid = HarmonicGrid(N=args.N, f0=args.f0)
    info = grid.summary()
    print(f"Hubstry Harmonic Stage v{grid.total_channels} canais")
    print(f"  Ordem harmônica: H_{info['harmonic_order']}")
    print(f"  Canais totais:   {info['total_channels']}")
    print(f"  Disponíveis:     {info['available']}")
    print(f"  Reservados:      {info['reserved']}")
    print(f"  Fundamental:     {info['fundamental_hz']} Hz")
    print(f"  Faixa:           {info['freq_min_hz']:.2f} — {info['freq_max_hz']:.2f} Hz")


def cmd_channels(args: argparse.Namespace) -> None:
    """Lista canais harmônicos com detalhes."""
    from src.core import HarmonicGrid

    grid = HarmonicGrid(N=args.N, f0=args.f0)
    channels = grid.get_channels()

    limit = min(args.limit, len(channels)) if args.limit else len(channels)

    print(f"{'Índ':>4}  {'Fração':>8}  {'Freq (Hz)':>10}  {'DMX':>4}  Status")
    print("-" * 50)
    for ch in channels[:limit]:
        status = "RES" if ch["reserved"] else "OK "
        print(
            f"{ch['index']:>4}  {ch['ratio_str']:>8}  "
            f"{ch['frequency']:>10.2f}  {ch['dmx_address']:>4}  {status}"
        )
    if limit < len(channels):
        print(f"... +{len(channels) - limit} canais")


def cmd_export(args: argparse.Namespace) -> None:
    """Exporta configuração completa como JSON."""
    from src.core import HarmonicGrid

    grid = HarmonicGrid(N=args.N, f0=args.f0)
    config = grid.export_config()
    output = json.dumps(config, indent=2, ensure_ascii=False)
    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output)
        print(f"Configuração exportada: {args.output}")
    else:
        print(output)


def cmd_scene(args: argparse.Namespace) -> None:
    """Carrega e valida um arquivo de cena."""
    from src.stage import SceneParser

    parser = SceneParser()
    scene = parser.from_file(args.file)
    warnings = parser.validate(scene)

    print(f"Cena: {scene.name}")
    print(f"  Fixtures: {len(scene.fixtures)}")
    print(f"  Cues:     {len(scene.cues)}")
    print(f"  Autor:    {scene.metadata.get('author', 'N/A')}")

    if warnings:
        print(f"\n  Avisos ({len(warnings)}):")
        for w in warnings:
            print(f"    ⚠ {w}")
    else:
        print("  ✓ Nenhum aviso.")


def cmd_version(args: argparse.Namespace) -> None:
    """Exibe a versão do pacote."""
    from src import __version__
    print(f"hubstry-harmonic-stage v{__version__}")


def main() -> None:
    """Ponto de entrada do CLI."""
    ap = argparse.ArgumentParser(
        prog="hstage",
        description="Hubstry Harmonic Stage — CLI para controle harmônico de palco",
    )
    ap.add_argument("-N", type=int, default=16, help="Ordem harmônica (padrão: 16)")
    ap.add_argument("--f0", type=float, default=25.0, help="Frequência fundamental Hz (padrão: 25.0)")

    sub = ap.add_subparsers(dest="command")

    sub.add_parser("info", help="Informações da grade harmônica")
    sub.add_parser("version", help="Versão do pacote")

    ch = sub.add_parser("channels", help="Listar canais harmônicos")
    ch.add_argument("--limit", "-l", type=int, default=0, help="Limite de canais")

    ex = sub.add_parser("export", help="Exportar configuração JSON")
    ex.add_argument("--output", "-o", type=str, help="Arquivo de saída")

    sc = sub.add_parser("scene", help="Validar arquivo de cena")
    sc.add_argument("file", help="Caminho do arquivo JSON")

    args = ap.parse_args()

    commands = {
        "info": cmd_info,
        "channels": cmd_channels,
        "export": cmd_export,
        "scene": cmd_scene,
        "version": cmd_version,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
