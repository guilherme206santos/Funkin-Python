# Sprint 07 — Calibração, notas longas e refinamento

**Objetivo:** deixar o jogo mais preciso, mais variado e mais agradável de jogar.

**Arquivos:** `src/ritmo.py`, `src/config.py`, `src/efeitos.py`, `src/gerar_assets.py`, `src/visual.py`, `src/main.py`

**Critérios de aceitação:**
- [ ] Calibração: o ajuste (ms) é medido por toques no metrônomo, salvo e aplicado ao relógio do jogo
- [ ] Notas longas: seguram até o fim (±100 ms), soltar cedo quebra combo e silencia a voz
- [ ] Charts antigos (sem notas longas) são regenerados automaticamente
- [ ] Downscroll e velocidade manual (×0.5 a ×2.0)
- [ ] Ghost tapping opcional (apertar sem nota = erro)
- [ ] Modo prática: começa em um bloco, não perde e não altera o recorde
- [ ] Resultados com histograma de acertos adiantados/atrasados e média em ms
- [ ] Zoom/tremor de câmera (desligável), partículas, transições suaves
- [ ] Volumes separados de música e efeitos; sons de erro, quebra, menus e contagem
