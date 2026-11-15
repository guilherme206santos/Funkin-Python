# 🎤 Funkin' Python — Jogo de ritmo com Pygame

**Projeto Avaliativo 2** de *Programação para Engenharia Mecânica* (PPEM Python, 26.2) — UFS.
Jogo de ritmo inspirado em *Friday Night Funkin'*, com a mesma organização de pastas do projeto de referência
[flappybird](https://github.com/wilson-luciano/flappybird): `assets/`, `docs/`, `src/`, `tests/`.

**Integrantes:** Guilherme, Brenda e Lorena.

O oponente canta sozinho; quando chega a sua vez, acerte as setas no tempo certo. No **multijogador**,
dois jogadores disputam a mesma música no mesmo teclado.

## 🧰 Requisitos

- Windows 10/11 (o código também roda em Linux e macOS) e **Python 3.12** (3.10 ou mais novo)
- Teclado; para o multijogador, os dois jogadores usam o mesmo teclado
- Dependências (`requirements.txt`): **pygame** (janela, desenho, eventos e áudio) e **numpy** (análise de ritmo do
  modo personalizado). Opcional: `imageio-ffmpeg` (ler M4A, WMA e vídeos no modo personalizado)

## 🚀 Como começar (Windows / VS Code)

Abra o terminal **dentro da pasta que contém `requirements.txt`**:

```
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python src/main.py
```

(Linux/macOS: `python3 -m venv .venv && source .venv/bin/activate`.)

(O `requirements.txt` instala o **Pygame** e o **numpy**; o numpy é usado na análise das músicas do modo personalizado.)

Ao abrir, o jogo mostra uma **introdução** (texto, logo da UFS e a música do menu subindo de volume).
ENTER, ESPAÇO ou ESC pulam. O áudio é gerado sozinho na primeira vez (a música do menu ao abrir; cada
música/dificuldade na primeira vez que você a joga, 2 a 4 s). Para gerar tudo antes: `python src/gerar_assets.py`.

> **Logo da UFS:** coloque o arquivo em `assets/imgs/logo_ufs.png` (ou `.jpg`). Sem ele, a introdução usa
> um logo provisório escrito com a fonte do jogo.

## 🎮 Modos

| Modo              | Como é                                                                           |
|-------------------|----------------------------------------------------------------------------------|
| **Jogar**         | 1 jogador contra o oponente da música. Usa as teclas do **Jogador 1**            |
| **Multijogador**  | 2 jogadores, mesma música e dificuldade. Cada um escolhe um personagem             |

### 🎶 Modo personalizado (use qualquer música sua)

Na seleção de música, o último cartão é o **Modo personalizado**. Escolha um arquivo de áudio do seu
computador e o jogo **analisa o ritmo e cria as setas na hora**, nas 3 dificuldades. Funciona no modo de
1 jogador e no **multijogador**.

1. Vá até o cartão *Modo personalizado* (→ no fim da lista) e aperte **ENTER**. Abre a janela de arquivos
   do sistema. Você também pode **arrastar o arquivo para a janela do jogo**.
2. Aguarde alguns segundos (barra de progresso). O jogo mostra o BPM e a duração encontrados.
3. **TAB** troca o cenário e o oponente; **O** escolhe outra música; **ENTER** joga.

**Formatos:** WAV, OGG, MP3 e FLAC abrem direto. Para M4A, AAC, WMA, OPUS, vídeos (MP4, MKV...) e outros, o jogo
usa o **ffmpeg** se ele estiver instalado — ou instale com `python -m pip install imageio-ffmpeg`
(traz o ffmpeg junto). Músicas de 5 segundos a 15 minutos.

**Como as setas são criadas** (veja `src/analise.py`):
- o som é dividido em 4 faixas de frequência (graves, médio-graves, médios e agudos) e o jogo procura os
  "ataques", isto é, os instantes em que o som de cada faixa aumenta de repente (bumbo, caixa, voz, guitarra...);
- o andamento (BPM) e as batidas são encontrados por autocorrelação e por um rastreador de batidas, que acompanha
  músicas que aceleram ou desaceleram um pouco;
- cada dificuldade fica com os ataques mais fortes: **Fácil** só nas batidas e bem espaçadas, **Médio** também
  nas colcheias, **Difícil** com tudo, mais setas duplas;
- a seta de cada ataque vem da faixa dominante (graves → baixo, médio-graves → esquerda, médios → cima,
  agudos → direita) e os sons que se sustentam viram **notas longas**.

**Limites (seja realista):**
- funciona melhor com bateria/percussão marcada. Músicas sem batida clara usam o "ritmo livre" (setas nos ataques
  mais fortes, sem grade); sinais sem música (silêncio, tom contínuo, ruído) são recusados com uma mensagem;
- é um gerador automático: não conhece a música, então o resultado pode precisar de ajuste de gosto
  (mude a dificuldade, a velocidade e a calibração de áudio);
- como o arquivo é uma faixa única, não há a voz separada do oponente nem o efeito de a sua voz silenciar ao errar;
- o jogo **não inclui nem copia músicas**: ele lê o arquivo que você escolheu, no seu computador. A análise fica em
  `dados/personalizadas/` e o jogo lembra a última música escolhida.

### Multijogador
- **Jogador 1** fica na esquerda (padrão **W A S D**) e **Jogador 2** na direita (padrão **setas**).
- Escolha de personagem: J1 usa **A / D** para escolher, **S** confirma, **W** cancela; J2 usa **← / →**,
  **↓** confirma, **↑** cancela. Os cinco personagens do jogo estão disponíveis.
- Os dois jogam a música inteira ao mesmo tempo. **Ninguém perde por errar**: só vale pontuação, precisão,
  acertos e erros, e a partida termina quando a música termina. Quem tiver mais pontos vence (desempate por precisão).
- A **velocidade das notas** e a **direção das setas** das Opções valem também no multijogador.
- A música do **Modo personalizado** também pode ser usada no multijogador.

## 🎵 Músicas e oponentes

| Música              | BPM | Cenário            | Oponente       |
|---------------------|-----|--------------------|----------------|
| Primeiro Round      | 120 | Palco              | Diabinho       |
| Cidade Neon         | 140 | Cidade à noite     | Robô X-9       |
| Floresta Assombrada | 100 | Floresta com névoa | Fantasminha    |
| Vulcão Final        | 160 | Vulcão e lava      | Dragão Brasa   |

## 🎚️ Dificuldades

Cada música tem 3 dificuldades. Todas as setas ficam numa grade rítmica (batida, colcheia, semicolcheia),
então **nunca saem do ritmo** — só muda *quantas* aparecem e *a que velocidade* rolam.

| Dificuldade | Velocidade | Setas                                                    |
|-------------|------------|----------------------------------------------------------|
| Fácil       | ×0.8       | só nas batidas, poucas                                   |
| Médio       | ×1.0       | batidas + colcheias                                      |
| Difícil     | ×1.3       | batidas + colcheias + semicolcheias + setas duplas       |

O recorde é guardado separadamente para cada música e dificuldade (só no modo de 1 jogador).

## 🕹️ Controles

| Tecla                         | Ação                                              |
|-------------------------------|---------------------------------------------------|
| **W A S D**                   | Jogador 1 (e modo de 1 jogador) — mude em Opções  |
| **← ↓ ↑ →**                   | Jogador 2 (multijogador) — mude em Opções         |
| **ESC / P**                   | pausar / continuar                                |
| **R**                         | reiniciar                                         |
| **F11**                       | tela cheia liga/desliga                           |
| **↑ ↓ ← → ENTER**            | navegar nos menus                                 |
| **TAB / PgUp / PgDn**         | (seleção de música) modo prática e bloco inicial  |

## ⚙️ Opções

No menu principal → **Opções**:

| Categoria                      | O que dá para mudar |
|--------------------------------|---------------------|
| **Controles - Jogador um / dois** | cada seta aceita *duas* teclas. Selecione a linha, ← → escolhe a Tecla 1 ou 2, ENTER e aperte a nova tecla (BACKSPACE apaga a Tecla 2). Se a tecla já estava em uso (por qualquer jogador), as duas posições trocam; o jogo recusa a mudança se alguma seta ficaria sem tecla. ESC, ENTER e F11 são reservadas |
| **Vídeo**                      | FPS (30 a 240), tela cheia, **resolução** e efeitos de câmera (zoom nas batidas e tremor ao errar) |
| **Jogabilidade**               | **velocidade das notas** (×0.5 a ×2.0), **direção das setas** (cima/baixo), **ghost tapping** e **calibrar áudio** |
| **Áudio**                      | volume da música e volume dos efeitos |
| **Restaurar padrões**          | volta tudo ao padrão, mas mantém a calibração |

Tudo é salvo em `dados/config.json`.

### 🖥️ Resolução (nitidez em tela cheia)
O jogo desenha **direto na resolução do monitor**, em vez de esticar uma imagem pequena. A opção
*Resolução* escolhe a qualidade: **Automática** (a do seu monitor, até 1440p), **Baixa** (1000×640, mais leve),
**Média**, **Alta** ou **Máxima**. Se o jogo ficar pesado, baixe a resolução ou o FPS.

### 🎧 Calibrar áudio
Se o som parecer adiantado ou atrasado em relação às setas, vá em *Jogabilidade → Calibrar áudio*.
Aperte **ESPAÇO** junto com cada "toc" (guie-se pelo som). Com 6 ou mais toques o jogo calcula a mediana do seu
atraso; **← →** fazem o ajuste fino (±5 ms) e **ENTER** salva. Fone Bluetooth costuma precisar de valor bem maior.

### 🏋️ Modo prática
Na seleção de música, **TAB** liga o modo prática e **PgUp/PgDn** escolhem o bloco em que começar.
Nele você não perde por falta de vida e o recorde não é alterado.

## ⭐ Mecânicas

- 4 lanes, julgamento **SICK** (±45 ms), **GOOD** (±90), **BAD** (±130), **SHIT** (±160) e **MISS**
- **Notas longas (sustain):** segure a tecla até o fim; soltar cedo quebra o combo e silencia a sua voz
- Combo, pontuação, precisão e rank (S, A, B, C, D)
- Barra de vida e tela de derrota (1 jogador); **tela de resultados** com gráfico de toques adiantados × atrasados
- Setas, letras e fonte inspiradas no FNF (veja *Créditos*); personagens simplificados desenhados por código
- Zoom de câmera a cada compasso, tremor ao errar, faíscas nos acertos, transições suaves e efeitos sonoros
- Música 100% gerada por código (bateria, baixo, vozes e o tema do menu)

## 🗺️ Roadmap

| Sprint | Conteúdo                                                   |
|--------|------------------------------------------------------------|
| 01–05  | Base do jogo, tempo musical, pontuação, testes, executável |
| 06     | Menus, várias músicas, dificuldades, opções                |
| 07     | Calibração, notas longas, prática, resultados, efeitos     |
| 08     | Visual do FNF, resolução real, introdução, multijogador    |
| 09     | Modo personalizado: importar música e gerar as setas       |

Detalhes em [`docs/roadmap.md`](docs/roadmap.md) e [`docs/sprints/`](docs/sprints).

## 📁 Estrutura

```
funkin-python/
├── assets/
│   ├── fonts/        # texto.ttf (VCR) — e, opcionalmente, titulo.ttf
│   ├── imgs/
│   │   ├── fnf/      # setas, notas longas e alfabeto (folhas de sprites .png + .xml)
│   │   ├── icone.png / icone.ico   # ícone do jogo
│   │   └── logo_ufs.png   # (opcional) logo da introdução
│   ├── audio/        # .wav gerados
│   └── charts/       # mapas de notas (.json) gerados
├── dados/            # (criada ao jogar) config.json, recordes.json e personalizadas/
├── docs/sprints/     # planejamento e critérios de aceitação
├── src/
│   ├── main.py           # estados do jogo, menus, multijogador e laço principal
│   ├── visual.py         # setas (imagens), fontes, personagens, ícones e cenários
│   ├── desenho.py        # desenho independente de resolução (escala K)
│   ├── atlas.py          # leitor de folhas de sprites (.png + .xml)
│   ├── alfabeto.py       # mapa de caracteres -> glifos da fonte em imagens
│   ├── ritmo.py          # regras puras: chart, dificuldades, julgamento, placar
│   ├── analise.py        # análise de ritmo de qualquer música (numpy) e criação das setas
│   ├── audio.py          # abrir qualquer arquivo de áudio (SDL/ffmpeg), seletor de arquivos
│   ├── musicas.py        # catálogo de músicas
│   ├── config.py         # opções (teclas dos 2 jogadores, vídeo, áudio...) e recordes
│   ├── efeitos.py        # efeitos sonoros curtos gerados por código
│   ├── gerar_assets.py   # sintetizador de áudio + gerador de charts
│   └── gerar_icone.py    # gera o ícone (precisa do Pillow)
├── tests/            # testes unitários (sem Pygame)
├── criar_executavel.bat   # (Windows) gera o .exe
├── montar_entrega.py      # monta Codigo.zip e Executavel.zip com os nomes da entrega
├── .gitignore
├── LICENSE
├── README.md
└── requirements.txt
```

Testes: `python -m unittest discover tests`

## 🔧 Criar uma música nova

1. Em `src/musicas.py`, acrescente uma `Musica(...)` (BPM, acordes, escala, estilo de bateria, cenário e oponente).
2. Para um cenário ou personagem novo, adicione-o em `src/visual.py` (`_CENARIOS` e `ESTILOS`).
3. Rode o jogo: ela aparece sozinha no menu.

## 🖼️ Ícone do jogo

O ícone (quatro setas ao redor de um disco de vinil) fica em `assets/imgs/icone.png` (janela e barra de tarefas) e
`assets/imgs/icone.ico` (arquivo `.exe`). Para trocar por outro: substitua os dois arquivos mantendo os nomes
(o `.ico` deve ter vários tamanhos, de 16 a 256 px) ou gere de novo com `python src/gerar_icone.py` (precisa do
Pillow: `python -m pip install pillow`).

## 📦 Executável (Windows, sem precisar de Python)

**Jeito fácil:** dê dois cliques em `criar_executavel.bat`. Ele prepara o ambiente, gera `dist\FunkinPython.exe` e cria o
`executavel.zip` (precisa do Python instalado e de internet na primeira vez).

**Jeito manual:**

O `.exe` precisa ser gerado no próprio Windows, com o ambiente virtual ativo:

```
python -m pip install pyinstaller
pyinstaller --onefile --windowed --name FunkinPython --icon assets/imgs/icone.ico --paths src ^
  --add-data "assets/imgs;assets/imgs" --add-data "assets/fonts;assets/fonts" src/main.py
```

(no PowerShell, troque o `^` de fim de linha por um acento grave `` ` `` ou escreva tudo numa linha só).
As imagens e fontes ficam embutidas no `.exe`; o áudio gerado e as opções são gravados **ao lado do .exe**
(`assets/audio`, `dados/`) — coloque-o numa pasta onde você tenha permissão de escrita.
O logo da UFS (`logo_ufs.png`) fica dentro de `assets/imgs`, então coloque-o lá **antes** de gerar o executável.
Para o modo personalizado ler M4A/WMA/vídeos dentro do `.exe`, instale `imageio-ffmpeg` e acrescente `--collect-all imageio_ffmpeg`
ao comando (ou deixe o ffmpeg instalado no computador).

> Executáveis sem assinatura digital podem acionar o aviso do Windows SmartScreen.

## 🙏 Créditos

- **Código, personagens, cenários, músicas, efeitos sonoros e ícone:** originais da equipe (Guilherme, Brenda e
  Lorena). Todo o áudio é gerado por código; nenhuma música ou som de terceiros acompanha o projeto.
- **Imagens das setas e alfabeto das letras** (`assets/imgs/fnf/`) e a fonte **VCR OSD Mono** (`assets/fonts/texto.ttf`):
  retirados do repositório *FunkinCrew/funkin.assets* (*Friday Night Funkin'*), usados **apenas para fins educacionais**
  neste trabalho acadêmico. Têm licença própria e **não** devem ser redistribuídos nem usados comercialmente
  (detalhes em [`assets/imgs/fnf/CREDITOS.md`](assets/imgs/fnf/CREDITOS.md)). Se essa pasta e a fonte forem removidas, o jogo
  continua funcionando: usa setas desenhadas por código e a fonte Arial.
- **Logo da UFS** (`assets/imgs/logo_ufs.png`, quando presente): marca da Universidade Federal de Sergipe, usada só na
  introdução do jogo.
- **Modelo didático:** estrutura do projeto e etapas (sprints) do repositório do professor Wilson Luciano
  ([flappybird](https://github.com/wilson-luciano/flappybird)).
- **Bibliotecas:** [Pygame](https://www.pygame.org/), [NumPy](https://numpy.org/), [PyInstaller](https://pyinstaller.org/)
  (executável) e Pillow (apenas para gerar o ícone).
- **Ferramenta de IA:** o desenvolvimento contou com a assistência do **Claude** (Anthropic) para escrever e revisar
  o código, os testes e a documentação. A equipe revisou, executou e é responsável pelo resultado.

## 🔐 Licença

Código sob licença **MIT** (arquivo `LICENSE`), exceto os arquivos de terceiros listados em *Créditos*.
*Friday Night Funkin'* é marca de seus criadores; este projeto é apenas didático.
