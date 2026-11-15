"""Regras do jogo de ritmo, sem dependência do Pygame (fácil de testar).

Todo o tempo é medido em milissegundos a partir do início da música.
"""
from __future__ import annotations

import json
import random
from dataclasses import dataclass

# ---------------------------------------------------------------- música ---
BPM = 120                  # valor padrão; cada música define o seu em musicas.py
LANES = 4                  # 0 = esquerda, 1 = baixo, 2 = cima, 3 = direita
COMPASSOS_INTRO = 2        # compassos sem notas no começo
COMPASSOS_POR_BLOCO = 4    # oponente canta 4 compassos, depois o jogador
BLOCOS = 8
VERSAO_CHART = 2           # sobe quando o formato/geração muda (regera arquivos antigos)

# ------------------------------------------------------------- julgamento ---
# (nome, tolerância em ms) — da mais precisa para a menos precisa
JANELAS = (("SICK", 45), ("GOOD", 90), ("BAD", 130), ("SHIT", 160))
JANELA_MAX = 160

PONTOS = {"SICK": 350, "GOOD": 200, "BAD": 100, "SHIT": 50}
PRECISAO = {"SICK": 1.0, "GOOD": 0.75, "BAD": 0.5, "SHIT": 0.25}
VIDA_POR_RATING = {"SICK": 0.04, "GOOD": 0.02, "BAD": -0.01, "SHIT": -0.03}
VIDA_ERRO = -0.06
PONTOS_ERRO = -10

# notas longas (sustain)
TOLERANCIA_SUSTAIN = 100       # pode soltar até 100 ms antes do fim
PONTOS_SUSTAIN_POR_MS = 0.12   # segurar 1 batida (500 ms) rende ~60 pontos
VIDA_SUSTAIN_POR_MS = 0.00002
PONTOS_SUSTAIN_COMPLETO = 100
VIDA_SUSTAIN_QUEBRA = -0.03

# ----------------------------------------------------------- dificuldades ---
# "chances": probabilidade de haver nota em cada nível da grade de semicolcheias
#   nível 0 = batida (1, 2, 3, 4)   nível 1 = colcheia ("e")   nível 2 = semicolcheia
# "duplas":  chance de nota dupla (duas setas juntas) em tempos fortes
# "sustain": chance de uma nota de batida virar nota longa
# "sustain_livre": nota longa pode coincidir com notas de OUTRAS lanes (segurar e apertar)
DIFICULDADES = {
    "facil":   {"nome": "Fácil",   "velocidade": 0.38, "chances": (0.70, 0.00, 0.00),
                "duplas": 0.00, "sustain": 0.22, "sustain_livre": False},
    "medio":   {"nome": "Médio",   "velocidade": 0.50, "chances": (0.92, 0.55, 0.00),
                "duplas": 0.00, "sustain": 0.20, "sustain_livre": False},
    "dificil": {"nome": "Difícil", "velocidade": 0.66, "chances": (0.97, 0.85, 0.35),
                "duplas": 0.25, "sustain": 0.18, "sustain_livre": True},
}
ORDEM_DIFICULDADES = ("facil", "medio", "dificil")


def ms_por_batida(bpm: float = BPM) -> float:
    return 60000.0 / bpm


def duracao_ms(bpm: float = BPM, blocos: int = BLOCOS) -> float:
    """Duração do trecho com notas + 1 compasso final."""
    return (COMPASSOS_INTRO + blocos * COMPASSOS_POR_BLOCO + 1) * 4 * ms_por_batida(bpm)


def inicio_bloco_ms(bloco: int, bpm: float = BPM) -> float:
    return (COMPASSOS_INTRO + bloco * COMPASSOS_POR_BLOCO) * 4 * ms_por_batida(bpm)


@dataclass
class Nota:
    tempo: float           # instante ideal do acerto (ms)
    lane: int              # 0..3
    dono: str              # "oponente" ou "jogador"
    duracao: float = 0.0   # > 0 = nota longa (ms)
    acertada: bool = False
    perdida: bool = False
    segurando: bool = False
    completa: bool = False
    quebrada: bool = False


def _adicionar_sustains(notas, cfg, rng, bpm):
    """Transforma algumas notas de batida em notas longas, sem sobrepor a mesma lane."""
    if cfg["sustain"] <= 0:
        return
    batida = ms_por_batida(bpm)
    passo = batida / 4
    contagem = {}
    for n in notas:
        contagem[(n.tempo, n.dono)] = contagem.get((n.tempo, n.dono), 0) + 1
    for i, n in enumerate(notas):
        pos = n.tempo / batida
        if abs(pos - round(pos)) > 1e-6 or contagem[(n.tempo, n.dono)] > 1:
            continue                                    # só em batidas e fora de duplas
        if rng.random() >= cfg["sustain"]:
            continue
        seguintes = [o for o in notas[i + 1:] if o.dono == n.dono and o.tempo > n.tempo]
        if not cfg["sustain_livre"]:
            prox = seguintes[0].tempo if seguintes else None
        else:
            prox = next((o.tempo for o in seguintes if o.lane == n.lane), None)
        bloco = (int(n.tempo // (4 * batida)) - COMPASSOS_INTRO) // COMPASSOS_POR_BLOCO
        fim_bloco = (COMPASSOS_INTRO + (bloco + 1) * COMPASSOS_POR_BLOCO) * 4 * batida
        limite = fim_bloco - n.tempo
        if prox is not None:
            limite = min(limite, prox - n.tempo)
        opcoes = [m for m in (2.0, 1.0, 0.5) if m * batida <= limite - passo]
        if opcoes:
            n.duracao = rng.choice(opcoes) * batida


def gerar_chart(bpm: float = BPM, seed: int = 7, dificuldade: str = "medio",
                blocos: int = BLOCOS):
    """Cria o mapa de notas de forma determinística.

    Todas as notas ficam numa grade de semicolcheias, então nunca saem do ritmo.
    A dificuldade muda quantos níveis da grade são usados (e a velocidade de
    rolagem, que é aplicada no jogo). Devolve ``(notas, duracao_ms)``.
    """
    cfg = DIFICULDADES[dificuldade]
    rng = random.Random(f"{seed}-{dificuldade}")
    passo = ms_por_batida(bpm) / 4
    notas: list[Nota] = []

    for b in range(blocos):
        dono = "oponente" if b % 2 == 0 else "jogador"
        rampa = 0.75 + 0.25 * min(1.0, b / max(1, blocos - 1))   # fica mais cheio no fim
        lane_ant = -1
        for c in range(COMPASSOS_POR_BLOCO):
            compasso = COMPASSOS_INTRO + b * COMPASSOS_POR_BLOCO + c
            tocou_antes = False
            for p in range(16):
                nivel = 0 if p % 4 == 0 else (1 if p % 4 == 2 else 2)
                chance = cfg["chances"][nivel] * (1.0 if nivel == 0 else rampa)
                if p == 0 and c == 0:
                    chance = 1.0
                if nivel == 2 and tocou_antes:      # evita rajadas de 3 notas seguidas
                    chance = 0.0
                tocou = chance > 0 and rng.random() < chance
                tocou_antes = tocou
                if not tocou:
                    continue
                tempo = (compasso * 16 + p) * passo
                opcoes = [i for i in range(LANES) if i != lane_ant]
                lane = rng.choice(opcoes) if rng.random() < 0.85 else rng.randrange(LANES)
                notas.append(Nota(tempo, lane, dono))
                lane_ant = lane
                if (nivel == 0 and p % 8 == 0 and b >= 2 and cfg["duplas"] > 0
                        and rng.random() < cfg["duplas"]):
                    outra = rng.choice([i for i in range(LANES) if i != lane])
                    notas.append(Nota(tempo, outra, dono))

    notas.sort(key=lambda n: (n.tempo, n.lane))
    _adicionar_sustains(notas, cfg, random.Random(f"{seed}-{dificuldade}-s"), bpm)
    return notas, duracao_ms(bpm, blocos)


def salvar_chart(caminho, notas, duracao, bpm: float = BPM, dificuldade: str = "medio") -> None:
    dados = {
        "versao": VERSAO_CHART,
        "bpm": bpm,
        "dificuldade": dificuldade,
        "duracao_ms": duracao,
        "notas": [{"tempo": n.tempo, "lane": n.lane, "dono": n.dono, "duracao": n.duracao}
                  for n in notas],
    }
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f)


def chart_atual(caminho) -> bool:
    """True se o arquivo existe e está na versão atual do formato."""
    try:
        with open(caminho, encoding="utf-8") as f:
            return json.load(f).get("versao") == VERSAO_CHART
    except (OSError, ValueError, AttributeError):
        return False


def carregar_chart(caminho):
    with open(caminho, encoding="utf-8") as f:
        dados = json.load(f)
    notas = [Nota(n["tempo"], n["lane"], n["dono"], n.get("duracao", 0.0)) for n in dados["notas"]]
    notas.sort(key=lambda n: (n.tempo, n.lane))
    return notas, dados["duracao_ms"]


# ------------------------------------------------------------ julgamento ---
def julgar(delta_ms: float):
    """Classifica o erro de tempo. Devolve None se estiver fora da janela."""
    d = abs(delta_ms)
    for nome, limite in JANELAS:
        if d <= limite:
            return nome
    return None


def escolher_nota(notas, lane: int, t: float):
    """Nota do jogador, ainda ativa, mais próxima de ``t`` naquela lane."""
    melhor = None
    for n in notas:
        if n.tempo > t + JANELA_MAX:
            break
        if n.dono != "jogador" or n.lane != lane or n.acertada or n.perdida:
            continue
        if abs(t - n.tempo) <= JANELA_MAX:
            if melhor is None or abs(t - n.tempo) < abs(t - melhor.tempo):
                melhor = n
    return melhor


def varrer_perdidas(notas, t: float):
    """Marca como perdidas as notas do jogador que passaram da janela."""
    perdidas = []
    for n in notas:
        if n.tempo > t - JANELA_MAX:
            break
        if n.dono == "jogador" and not n.acertada and not n.perdida:
            n.perdida = True
            perdidas.append(n)
    return perdidas


def varrer_oponente(notas, t: float):
    """O oponente acerta sozinho todas as suas notas no instante exato."""
    tocadas = []
    for n in notas:
        if n.tempo > t:
            break
        if n.dono == "oponente" and not n.acertada:
            n.acertada = True
            tocadas.append(n)
    return tocadas


def atualizar_sustains(notas, t: float, seguradas, placar, dt_ms: float):
    """Acompanha as notas longas que o jogador está segurando.

    ``seguradas[lane]`` diz se alguma tecla daquela lane está pressionada.
    Devolve uma lista de eventos ``("completo" | "quebrado", nota)``.
    """
    eventos = []
    for n in notas:
        if n.tempo > t + JANELA_MAX:
            break
        if not n.segurando:
            continue
        if t >= n.tempo + n.duracao - TOLERANCIA_SUSTAIN:
            n.segurando = False
            n.completa = True
            placar.completar_sustain()
            eventos.append(("completo", n))
        elif not seguradas[n.lane]:
            n.segurando = False
            n.quebrada = True
            placar.quebrar_sustain()
            eventos.append(("quebrado", n))
        else:
            placar.segurar(dt_ms)
    return eventos


def histograma(desvios, largura_bin: int = 20, limite: int = JANELA_MAX):
    """Conta os desvios (ms; negativo = adiantado) em faixas. Devolve (contagens, média)."""
    n_bins = (2 * limite) // largura_bin
    cont = [0] * n_bins
    for d in desvios:
        i = int((d + limite) // largura_bin)
        cont[min(n_bins - 1, max(0, i))] += 1
    media = sum(desvios) / len(desvios) if desvios else 0.0
    return cont, media


# --------------------------------------------------------------- placar ---
class Placar:
    def __init__(self) -> None:
        self.pontos = 0
        self.combo = 0
        self.combo_max = 0
        self.vida = 0.5            # 0 = derrota, 1 = cheia
        self.contagem = {nome: 0 for nome, _ in JANELAS}
        self.erros = 0
        self.desvios: list[float] = []
        self.sustains_ok = 0
        self.sustains_quebrados = 0
        self._fracao = 0.0

    def acertar(self, rating: str, desvio: float | None = None) -> None:
        self.contagem[rating] += 1
        self.pontos += PONTOS[rating]
        self.combo += 1
        self.combo_max = max(self.combo_max, self.combo)
        self.vida = min(1.0, max(0.0, self.vida + VIDA_POR_RATING[rating]))
        if desvio is not None:
            self.desvios.append(desvio)

    def errar(self) -> None:
        self.erros += 1
        self.combo = 0
        self.pontos += PONTOS_ERRO
        self.vida = max(0.0, self.vida + VIDA_ERRO)

    def segurar(self, dt_ms: float) -> None:
        self._fracao += dt_ms * PONTOS_SUSTAIN_POR_MS
        inteiros = int(self._fracao)
        self.pontos += inteiros
        self._fracao -= inteiros
        self.vida = min(1.0, self.vida + dt_ms * VIDA_SUSTAIN_POR_MS)

    def completar_sustain(self) -> None:
        self.sustains_ok += 1
        self.pontos += PONTOS_SUSTAIN_COMPLETO

    def quebrar_sustain(self) -> None:
        self.sustains_quebrados += 1
        self.combo = 0
        self.vida = max(0.0, self.vida + VIDA_SUSTAIN_QUEBRA)

    @property
    def acertos(self) -> int:
        return sum(self.contagem.values())

    @property
    def precisao(self) -> float:
        total = self.acertos + self.erros
        if total == 0:
            return 1.0
        soma = sum(PRECISAO[k] * v for k, v in self.contagem.items())
        return soma / total

    @property
    def rank(self) -> str:
        p = self.precisao
        for minimo, letra in ((0.95, "S"), (0.85, "A"), (0.70, "B"), (0.50, "C")):
            if p >= minimo:
                return letra
        return "D"

    @property
    def derrota(self) -> bool:
        return self.vida <= 0.0
