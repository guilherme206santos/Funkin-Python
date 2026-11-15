"""Catálogo de músicas (dados puros, sem Pygame).

Para criar uma música nova basta acrescentar uma ``Musica`` em ``MUSICAS``,
escolher um cenário e um oponente que já existam em ``visual.py`` (ou criar
novos lá) e rodar o jogo: o áudio e o mapa de notas são gerados sozinhos.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class Musica:
    id: str
    nome: str
    subtitulo: str
    bpm: float
    raizes: tuple       # nota-base do baixo em cada compasso (repete a cada 4)
    escala: tuple       # frequência (Hz) da melodia para cada lane
    seed: int           # semente do gerador de notas
    bateria: str        # "rock", "house", "lento" ou "pesado"
    cenario: str        # nome do cenário em visual.py
    oponente: str       # estilo do personagem em visual.py
    nome_oponente: str
    timbre_op: str      # "quadrada", "serra" ou "suave"
    blocos: int = 8     # 4 compassos cada, alternando oponente/jogador
    personalizada: bool = False   # música escolhida pelo jogador (modo personalizado)
    arquivo: str = ""


MUSICAS = (
    Musica("palco", "Primeiro Round", "Aquecimento no palco", 120,
           (110.00, 87.31, 130.81, 98.00), (440.00, 523.25, 659.25, 783.99), 7,
           "rock", "palco", "diabinho", "Diabinho", "quadrada"),
    Musica("neon", "Cidade Neon", "Batida eletrônica na noite", 140,
           (146.83, 116.54, 174.61, 130.81), (293.66, 349.23, 440.00, 523.25), 21,
           "house", "cidade", "robo", "Robô X-9", "serra"),
    Musica("floresta", "Floresta Assombrada", "Um fantasma entre as árvores", 100,
           (164.81, 130.81, 196.00, 146.83), (329.63, 392.00, 440.00, 493.88), 33,
           "lento", "floresta", "fantasma", "Fantasminha", "suave"),
    Musica("vulcao", "Vulcão Final", "A luta mais quente", 160,
           (98.00, 155.56, 116.54, 174.61), (392.00, 466.16, 523.25, 587.33), 48,
           "pesado", "vulcao", "dragao", "Dragão Brasa", "serra"),
)


def por_id(id_musica: str) -> Musica:
    for m in MUSICAS:
        if m.id == id_musica:
            return m
    raise KeyError(id_musica)


# ----------------------------------------------------------- modo personalizado ---
# cenário + oponente que o jogador pode escolher para a música dele (TAB na seleção)
VISUAIS_PERSONALIZADA = tuple((m.cenario, m.oponente, m.nome_oponente) for m in MUSICAS)


def _personalizada(id_, nome, subtitulo, bpm, visual, arquivo=""):
    cenario, oponente, nome_op = VISUAIS_PERSONALIZADA[visual % len(VISUAIS_PERSONALIZADA)]
    base = MUSICAS[0]
    return Musica(id_, nome, subtitulo, bpm, base.raizes, base.escala, 0, "rock",
                  cenario, oponente, nome_op, "quadrada", personalizada=True, arquivo=arquivo)


def modelo_personalizada() -> Musica:
    """Cartão "vazio" do modo personalizado (ainda sem arquivo)."""
    return _personalizada("personalizado", "Modo personalizado",
                          "Escolha uma música do seu computador", 120, 0)


def criar_personalizada(nome_arquivo: str, bpm: float, id_hash: str, arquivo: str, visual: int = 0) -> Musica:
    return _personalizada(f"custom-{id_hash[:8]}", nome_arquivo, "Modo personalizado", bpm, visual, arquivo)
