<p align="center">
  <!-- Logo Hubstry Deep Tech -->
  <img src="docs/assets/logo.png" alt="Logo Hubstry Deep Tech" width="200"/>
</p>

<h1 align="center">Hubstry Harmonic Stage (HStage)</h1>

<p align="center">
  <strong>Protocolo Harmônico para Indústria Criativa e Tecnologia de Palco</strong>
</p>

<p align="center">
  <a href="https://www.python.org/downloads/" target="_blank">
    <img src="https://img.shields.io/badge/Python-3.11%2B-blue.svg" alt="Python 3.11+" />
  </a>
  <a href="LICENSE" target="_blank">
    <img src="https://img.shields.io/badge/Licença-Apache_2.0-green.svg" alt="Licença Apache 2.0" />
  </a>
  <a href="https://doi.org/10.5281/zenodo.18652888" target="_blank">
    <img src="https://img.shields.io/badge/HPG-1.0-orange.svg" alt="HPG 1.0 Compatível" />
  </a>
</p>

---

## 🎭 Sobre o Projeto

**Hubstry Harmonic Stage (HStage)** é o módulo de tecnologia de palco e iluminação do ecossistema [Hubstry Harmonic Protocol](https://hubstry.dev). HStage substitui o protocolo DMX512 por um protocolo baseado em harmonização harmônica, oferecendo autenticação robusta de 200 bytes, latência sub-milissegundo e até 255 canais no formato H16 — superando drasticamente os limites do DMX512 tradicional (0 bytes de autenticação, 512 canais brutos, latência de ~23 ms por universo).

### Diferenciais em Relação aos Padrões Atuais

| Recurso | **HStage** | **DMX512** | **Art-Net** |
|---|:---:|:---:|:---:|
| Autenticação por pacote | 200B (HMAC-SHA256) | Nenhuma | Nenhuma |
| Latência típica | < 1 ms | ~23 ms | 2–5 ms |
| Canais (formato H16) | 255 | 512 (bruto) | 512 (bruto) |
| Criptografia nativa | AES-256-GCM | Não | Não |
| Compressão harmônica | H16 (4 bits/canal) | 8 bits/canal | 8 bits/canal |
| Controle de dispositivo | UUID + Função Hash | Endereço fixo (1–512) | IP + Endereço DMX |
| Resolução por canal | 16 bits (65 536 níveis) | 8 bits (256 níveis) | 8 bits (256 níveis) |
| Descoberta automática | Sim (broadcast harmônico) | Não | Sim (Bonjour) |
| Multiplexação | Harmônica | Não | Não |

---

## 🏗️ Arquitetura

A arquitetura do HStage segue os princípios estabelecidos no **Hubstry Protocol Guide (HPG 1.0)**, organizando-se em camadas harmônicas com descoberta automática, autenticação mútua e compressão H16 para máxima eficiência na transmissão de dados de iluminação e controle cênico.

Para detalhes completos da arquitetura, consulte a [documentação em `docs/`](docs/).

```
┌─────────────────────────────────────────────────┐
│              Camada de Aplicação (HStage)        │
│    Cenário · Iluminação · Mapeamento · Vídeo    │
├─────────────────────────────────────────────────┤
│              Camada Harmônica (HCore)            │
│    Multiplexação · H16 · Sincronização           │
├─────────────────────────────────────────────────┤
│              Camada de Segurança (HSec)          │
│    HMAC-SHA256 · AES-256-GCM · 200B Auth        │
├─────────────────────────────────────────────────┤
│              Camada de Transporte (HTP)          │
│    UDP/TCP · Descoberta · Roteamento             │
└─────────────────────────────────────────────────┘
```

---

## 🚀 Início Rápido

### Instalação

```bash
pip install hubstry-harmonic-stage
```

### Exemplo Básico

```python
from hstage import Stage, Device

# Criar um novo palco harmônico
palco = Stage(name="Palco Principal", universe=1)

# Registrar dispositivos (auto-descoberta ou manual)
palco.add_device(Device(uuid="abc123", device_type="moving_head"))
palco.add_device(Device(uuid="def456", device_type="led_wash"))

# Iniciar o protocolo harmônico
palco.start()

# Enviar dados de controle (canal, valor 0–65535)
palco.set_channel(device="abc123", channel=1, value=45000)
palco.set_channel(device="def456", channel=3, value=32000)

# Encerrar
palco.stop()
```

### Linha de Comando (CLI)

```bash
# Iniciar servidor HStage
hstage serve --host 0.0.0.0 --port 7770

# Escanear dispositivos na rede
hstage scan

# Enviar cena pré-configurada
hstage send-cene --file cena_harmonica.json
```

---

## 📂 Estrutura do Repositório

```
hubstry-harmonic-stage/
├── CITATION.cff          # Metadados de citação CFF
├── LICENSE               # Licença Apache 2.0
├── README.md             # Este arquivo
├── pyproject.toml        # Configuração do projeto (PEP 621)
├── docs/                 # Documentação técnica
│   ├── architecture.md   # Arquitetura detalhada
│   ├── h16-format.md     # Especificação do formato H16
│   ├── getting-started.md # Guia de início rápido
│   └── assets/           # Imagens e diagramas
├── src/
│   └── hstage/
│       ├── __init__.py
│       ├── cli.py        # Interface de linha de comando
│       ├── core/
│       │   ├── __init__.py
│       │   ├── stage.py  # Gerenciamento do palco
│       │   └── device.py # Gerenciamento de dispositivos
│       ├── protocol/
│       │   ├── __init__.py
│       │   ├── h16.py    # Codificação/decodificação H16
│       │   └── harmonic.py # Protocolo harmônico
│       ├── security/
│       │   ├── __init__.py
│       │   ├── auth.py   # Autenticação 200B
│       │   └── crypto.py # Criptografia AES-256-GCM
│       └── transport/
│           ├── __init__.py
│           └── udp.py    # Camada de transporte UDP
└── tests/
    ├── __init__.py
    ├── test_stage.py
    ├── test_h16.py
    └── test_auth.py
```

---

## 📚 Publicações Relacionadas

- **Hubstry Protocol Guide (HPG) 1.0**
  Guilherme Gonçalves Machado, 2025.
  DOI: [10.5281/zenodo.18652888](https://doi.org/10.5281/zenodo.18652888)

- **Hubstry Marine Acoustic Layer (HMAL)**
  Guilherme Gonçalves Machado, 2025.
  DOI: [10.5281/zenodo.20184616](https://doi.org/10.5281/zenodo.20184616)

- **GuruDev Core**
  Guilherme Gonçalves Machado, 2025.
  DOI: [10.5281/zenodo.19772798](https://doi.org/10.5281/zenodo.19772798)

---

## 👤 Autor

**Guilherme Gonçalves Machado**

[ORCID: 0009-0008-1083-0784](https://orcid.org/0009-0008-1083-0784)

📧 guilhermemachado.ceo@hubstry.dev

🌐 [hubstry.dev](https://hubstry.dev)

---

## 📄 Licença

Este projeto é licenciado sob os termos da **Licença Apache 2.0**. Consulte o arquivo [LICENSE](LICENSE) para mais informações.

---

<p align="center">
  <sub>Hubstry Deep Tech · Construindo o futuro harmônico da tecnologia criativa</sub>
</p>
