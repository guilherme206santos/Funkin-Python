# Sprint 09 — Modo personalizado

**Objetivo:** o jogador escolhe uma música do próprio computador e o jogo cria as setas automaticamente.

**Arquivos:** `src/analise.py`, `src/audio.py`, `src/musicas.py`, `src/config.py`, `src/main.py`

**Critérios de aceitação:**
- [ ] Cartão "Modo personalizado" na seleção de música (1 jogador e multijogador)
- [ ] Janela de arquivos do sistema e também arrastar o arquivo para a janela
- [ ] Lê WAV/OGG/MP3/FLAC direto e outros formatos pelo ffmpeg, com mensagens de erro claras
- [ ] Análise em segundo plano com barra de progresso (a janela não trava)
- [ ] BPM com erro menor que 1% e ataques com erro de tempo menor que 15 ms em músicas de teste
- [ ] 3 dificuldades com quantidades diferentes de setas, sem setas coladas e sem nota longa sobreposta
- [ ] Zoom, ícones e oponente acompanham as batidas reais da música
- [ ] Análise guardada em cache e última música lembrada entre sessões
- [ ] Recusa silêncio, tom contínuo, ruído e arquivos curtos demais com uma mensagem
