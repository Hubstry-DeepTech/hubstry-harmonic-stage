# Arquitetura do Hubstry Harmonic Stage

## Visão Geral

O Hubstry Harmonic Stage (HStage) é a implementação do **HPG 1.0** para o domínio de tecnologia de palco e indústria criativa. Substitui o protocolo DMX512 com canais harmônicos racionais, oferecendo autenticação integrada, latência sub-ms e escalabilidade infinita.

## Pilares Matemáticos

O HPG 1.0 (DOI: 10.5281/zenodo.19056387) define canais de comunicação como frações racionais irredutíveis:

```
f(a,b) = (a/b) × f₀    onde mdc(a,b) = 1
```

- H₁₆ = 255 canais (equivalente à profundidade DMX512 prática)
- H₃₂ = 1.023 canais (superior ao DMX512)
- H_N → Q⁺ quando N → ∞ (escalabilidade infinita)

## Módulos

```
src/
├── __init__.py          — Metadados do pacote
├── cli.py               — Interface de linha de comando (hstage)
├── core/                — Matemática harmônica (HPG 1.0)
│   ├── rational_set.py  — Conjunto H_N
│   ├── channel_mapper.py— HPG ↔ DMX512
│   └── harmonic_grid.py — Fachada unificada
├── stage/               — Controle de palco
│   ├── dmx_bridge.py    — Bridge HPG ↔ DMX
│   ├── fixture_controller.py — Registro e controle de fixtures
│   ├── cue_engine.py    — Motor de cues teatrais
│   └── scene_parser.py  — Serialização de cenas
├── security/            — Autenticação leve
│   ├── auth_lightweight.py — Pacote de 200B com HMAC
│   └── hsl_stage.py     — HSL para palco
└── protocol/            — Transporte
    ├── packet.py        — Formato binário HStage
    └── transport.py     — UDP/Art-Net
```

## Fluxo de Dados

```
Cue → CueEngine → FixtureController → HPG channels → DMXBridge → DMX512 → Fixture
                                                        ↓
                                              HSL (200B auth)
                                                        ↓
                                              HStagePacket → UDP :6454
```

## Comparação com DMX512

| Métrica | DMX512 | HStage |
|---------|--------|--------|
| Canais | 512 fixos | 255 (H₁₆) → ∞ (H_∞) |
| Autenticação | Nenhuma | ~200B (HMAC-SHA256) |
| Bidirecional | Não (unidirecional) | Sim (UDP) |
| Latência de handshake | N/A | Sub-ms |
| Endereçamento | Base-1 | Base-0 + fração racional |
| Taxa de refresh | 44 Hz fixa | Configurável via f₀ |

## Compatibilidade

HStage é compatível com DMX512 no nível de hardware — qualquer fixture DMX existente funciona sem modificação. O mapeamento é transparente: canais HPG são convertidos para endereços DMX pelo `DMXBridge`.
