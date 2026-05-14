# Guia de Migração DMX512 → Hubstry Harmonic Stage

## Resumo

Este guia descreve como migrar de sistemas DMX512 convencionais para o Hubstry Harmonic Stage (HStage), mantendo compatibilidade total com fixtures e hardware existentes.

## Pré-requisitos

- Python 3.11+
- Fixtures DMX512 existentes (qualquer marca/modelo)
- Interface DMX USB (ex.: Enttec Open DMX, FTDI)

## Instalação

```bash
pip install hubstry-harmonic-stage
# ou em desenvolvimento:
pip install -e .
```

## Passo 1: Mapear Fixtures Existentes

Cada fixture DMX tem um endereço inicial e um número de canais. No HStage, basta registrar a fixture com os mesmos parâmetros:

```python
# Antes (DMX512 puro):
# Endereço DMX: 1, Canais: 4 (R, G, B, Intensity)

# Depois (HStage):
from src.stage import FixtureController, Fixture, FixtureType

ctrl = FixtureController(universe_id=0)
ctrl.add_fixture(Fixture(
    id="PAR-001",
    fixture_type=FixtureType.PAR_LED,
    dmx_start_address=1,  # mesmo endereço DMX
    channel_count=4,       # mesmo número de canais
    parameters={
        "red": 0, "green": 1, "blue": 2, "intensity": 3,
    },
))
```

## Passo 2: Converter Valores (0-255 → 0.0-1.0)

DMX512 usa valores inteiros 0-255. HStage usa floats 0.0-1.0:

```python
# Antes:
# dmx_channel_1 = 255  # vermelho máximo

# Depois:
ctrl.set_value("PAR-001", "red", 1.0)     # vermelho máximo
ctrl.set_value("PAR-001", "intensity", 0.5) # 50% de intensidade
```

O `DMXBridge` faz a conversão automaticamente:

```python
from src.stage import DMXBridge

bridge = DMXBridge(universe_id=0, harmonic_n=16)
hpg_values = ctrl.all_to_hpg()     # {índice: valor 0.0-1.0}
dmx_values = bridge.hpg_to_dmx(hpg_values)  # [int, int, ...] 0-255
```

## Passo 3: Migrar Cues

```python
from src.stage import CueEngine

engine = CueEngine(ctrl)

# Antes: cue manual com valores DMX
# Cue 1: [255, 0, 0, 200]

# Depois: cue com valores normalizados
ctrl.set_values("PAR-001", {"red": 1.0, "green": 0.0, "blue": 0.0, "intensity": 0.784})
cue = engine.record_cue("Vermelho Intenso", fade_in=2.0)
```

## Passo 4: Ativar Segurança (Opcional)

O HSL adiciona autenticação de ~200 bytes, impossível no DMX512:

```python
from src.security import HSLStage
import hashlib

hsl = HSLStage(
    shared_key=hashlib.sha256(b"sua-chave-secreta-256bits").digest(),
    device_id=b"\x01\x02\x03\x04\x05\x06\x07\x08",
)
pkt = hsl.authenticate()
```

## Tabela de Equivalência Rápida

| DMX512 | HStage |
|--------|--------|
| Endereço 1-512 | HPG[0] - HPG[254] (H₁₆) |
| Valor 0-255 | Float 0.0-1.0 |
| Universe 0-15 | Identificador de universo |
| Nenhum | Autenticação HMAC (~200B) |
| 44 Hz fixo | Configurável via f₀ |
| Unidirecional | Bidirecional (UDP) |

## Limitações Conhecidas

- H₁₆ = 255 canais (vs 512 DMX). Use H₃₂ (1023 canais) se precisar de mais.
- O hardware DMX USB ainda envia DMX512 nativo — a conversão HPG→DMX acontece no software.
- Fade em tempo real requer implementação async (TODO no CueEngine).
