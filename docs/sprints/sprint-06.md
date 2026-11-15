# Sprint 06 — Menus, músicas, dificuldades e opções

**Objetivo:** transformar o jogo de uma música em um jogo completo, com menus e configurações.

**Arquivos:** `src/musicas.py`, `src/visual.py`, `src/config.py`, `src/ritmo.py`, `src/gerar_assets.py`, `src/main.py`

**Critérios de aceitação:**
- [ ] Menu principal com Jogar, Opções e Sair
- [ ] 4 músicas, cada uma com cenário e oponente próprios
- [ ] 3 dificuldades por música: mudam a velocidade e a quantidade de setas, sem sair da grade rítmica
- [ ] Recorde salvo por música e dificuldade
- [ ] Opções: remapear as 4 setas (2 teclas cada), FPS e tela cheia, salvos em `dados/config.json`
- [ ] Teclas repetidas são trocadas, nunca duplicadas
- [ ] Áudio e charts gerados sob demanda, sem travar a janela
