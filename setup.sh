# ============================================================
# HUBSTRY HARMONIC STAGE — Script de Setup via Terminal
# Execute ESTE script no PowerShell do notebook:
#   cd hubstry-harmonic-stage && bash setup.sh
#   (ou copie os comandos um por um abaixo)
# ============================================================

echo "=== Hubstry Harmonic Stage — Setup ==="

# 1. Criar repositório Git (SE já existir, pular)
echo "[1/7] Inicializando repositório Git..."
git init
git branch -M main

# 2. Adicionar todos os arquivos
echo "[2/7] Adicionando arquivos..."
git add -A

# 3. Commit inicial
echo "[3/7] Commit inicial..."
git commit -m "feat: estrutura completa do hubstry-harmonic-stage v0.1.0

- Core: RationalSet, ChannelMapper, HarmonicGrid (HPG 1.0)
- Stage: DMXBridge, FixtureController, CueEngine, SceneParser
- Security: HSL Stage com autenticação de 200B (vs 8KB TLS)
- Protocol: HStagePacket binário, transporte UDP/Art-Net
- Tests: 4 suítes (rational_set, channel_mapper, harmonic_grid, security, protocol)
- Docs: ARCHITECTURE, API, DMX_MIGRATION
- Examples: 3 demos (grid, fixtures, cues)
- CLI: comando hstage

Baseado no HPG 1.0 (DOI: 10.5281/zenodo.19056387)
Apache 2.0 — Guilherme Goncalves Machado (ORCID: 0009-0008-1083-0784)"

# 4. Adicionar remote (substitua pela URL do seu repo)
echo "[4/7] Adicionando remote..."
# IMPORTANTE: crie o repo VAZIO no GitHub ANTES deste passo
# https://github.com/new → hubstry-harmonic-stage → sem README, .gitignore ou LICENSE
git remote add origin https://github.com/Hubstry-DeepTech/hubstry-harmonic-stage.git

# 5. Push
echo "[5/7] Push para GitHub..."
git push -u origin main

# 6. Assinar commits com GPG (se já tiver chave configurada)
# git tag -a v0.1.0 -m "v0.1.0 — Primeira release"
# git push origin v0.1.0

echo "[6/7] Verificando estrutura..."
find . -type f -name "*.py" -o -name "*.md" -o -name "*.toml" -o -name "*.cff" -o -name "LICENSE" -o -name ".gitignore" | grep -v __pycache__ | sort

echo "[7/7] Setup concluído!"
echo ""
echo "Para rodar os testes:"
echo "  pip install pytest"
echo "  python -m pytest tests/ -v"
echo ""
echo "Para usar o CLI:"
echo "  python -m src.cli info"
echo "  python -m src.cli channels --limit 10"
echo ""
echo "Para rodar os exemplos:"
echo "  python examples/demo_harmonic_grid.py"
echo "  python examples/demo_fixture_control.py"
echo "  python examples/demo_cue_engine.py"
