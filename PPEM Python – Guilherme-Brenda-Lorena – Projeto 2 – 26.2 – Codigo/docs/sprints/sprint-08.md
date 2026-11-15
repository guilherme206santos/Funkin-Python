# Sprint 08 — Visual do FNF, resolução real, introdução e multijogador

**Objetivo:** melhorar a apresentação do jogo e adicionar um modo para dois jogadores.

**Arquivos:** `src/desenho.py`, `src/visual.py`, `src/atlas.py`, `src/alfabeto.py`, `src/config.py`, `src/gerar_assets.py`, `src/main.py`

**Critérios de aceitação:**
- [ ] Setas, receptores e notas longas lidos de folhas de sprites (`.png` + `.xml`), com setas desenhadas por código como reserva
- [ ] Fonte dos títulos feita de imagens, com acentos desenhados por código; fonte VCR nos demais textos
- [ ] Desenho independente de resolução (escala K): nítido em tela cheia, com opção de resolução
- [ ] Introdução: fade do texto "Trabalho de Programação", fade do logo da UFS e fade para a tela inicial
- [ ] Música do menu gerada por código, em loop, com volume crescente durante a introdução
- [ ] Multijogador local: jogador 1 (WASD) à esquerda, jogador 2 (setas) à direita, escolha de personagem e de música/dificuldade
- [ ] No multijogador ninguém perde por errar; vale pontuação, precisão, acertos e erros; a partida só acaba com a música
- [ ] Controles configuráveis por jogador; o modo de 1 jogador usa as teclas do jogador 1
- [ ] Velocidade e direção das setas das Opções valem também no multijogador
