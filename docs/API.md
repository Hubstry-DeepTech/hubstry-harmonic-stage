# Referência de API — Hubstry Harmonic Stage

## Módulo Core

### RationalSet(N=16)

Conjunto harmônico racional H_N.

```python
from src.core import RationalSet

rs = RationalSet(N=16)
rs.size              # 255
rs.fractions         # tupla de RationalPair ordenados
(1, 2) in rs         # True
rs.to_frequencies(25.0)  # [(RationalPair, float), ...]
```

### ChannelMapper(N=16, f0=25.0)

Mapeamento HPG ↔ DMX512.

```python
from src.core import ChannelMapper

mapper = ChannelMapper(N=16, f0=25.0)
mapper.total_channels    # 255
mapper.map_to_dmx(0)     # 1
mapper.map_from_dmx(1)   # 0
mapper.get_channel_frequency(0)  # 25.0
mapper.allocate_fixture("LED-001", 4)  # (0, 3)
mapper.release_fixture("LED-001")
```

### HarmonicGrid(N=16, f0=25.0)

Fachada unificada.

```python
from src.core import HarmonicGrid

grid = HarmonicGrid(N=16)
grid.reserve_channel(0, "Red PAR-001")
grid.available_channels()  # [1, 2, 3, ...]
grid.export_config()       # dict serializável
grid.summary()             # dict com estatísticas
```

## Módulo Stage

### FixtureType (Enum)

`MOVING_HEAD`, `PAR_LED`, `STRIP_LED`, `DIMMER`, `STROBE`, `FOGGER`

### Fixture(dataclass)

```python
from src.stage import Fixture, FixtureType

f = Fixture(
    id="PAR-001",
    fixture_type=FixtureType.PAR_LED,
    dmx_start_address=1,
    channel_count=4,
    parameters={"red": 0, "green": 1, "blue": 2, "intensity": 3},
)
```

### FixtureController(universe_id=0)

```python
from src.stage import FixtureController

ctrl = FixtureController(universe_id=0)
ctrl.add_fixture(f)
ctrl.set_values("PAR-001", {"red": 1.0, "green": 0.0, "blue": 0.0})
ctrl.all_to_hpg()  # dict[int, float]
ctrl.list_fixtures()
```

### Cue(dataclass)

```python
from src.stage import Cue

cue = Cue(
    id="cue-1",
    name="Vermelho",
    values={0: 1.0, 1: 0.0, 2: 0.0, 3: 0.8},
    fade_in=2.0,
    fade_out=1.0,
    hold=5.0,
    priority=1,
)
```

### CueEngine(fixture_controller)

```python
from src.stage import CueEngine, CueStack

engine = CueEngine(ctrl)
stack = CueStack()

cue = engine.record_cue("Blackout", fade_in=0.5)
stack.add_cue(cue)
engine.go(stack, 1)    # executa cue na posição 1
engine.stop()           # blackout
```

## Módulo Security

### HSLStage(shared_key, device_id, harmonic_n=16)

```python
from src.security import HSLStage
import hashlib

key = hashlib.sha256(b"secret-key").digest()
hsl = HSLStage(shared_key=key, device_id=b"\x00"*8)

pkt = hsl.authenticate()      # AuthPacket
ok, reason = hsl.verify(pkt)  # (True, "")
hsl.is_authenticated()         # True
```

## Módulo Protocol

### HStagePacket

```python
from src.protocol import HStagePacket, PacketType

pkt = HStagePacket(
    packet_type=PacketType.DATA,
    sequence=1,
    harmonic_n=16,
    channel_count=3,
    channels=[(0, 1.0), (1, 0.5), (2, 0.0)],
)
data = pkt.to_bytes()
restored = HStagePacket.from_bytes(data)
```

## CLI

```bash
hstage info                 # informações da grade H_16
hstage channels --limit 10   # primeiros 10 canais
hstage export -o config.json # exportar configuração
hstage scene show.json       # validar cena
hstage version               # versão
```
