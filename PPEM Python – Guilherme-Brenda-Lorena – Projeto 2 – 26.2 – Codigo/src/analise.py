"""Análise de ritmo de uma música qualquer: acha as batidas e cria as setas (numpy, sem Pygame).

Etapas:
  1. espectro por bandas (graves, médio-graves, médios, agudos) e "fluxo espectral":
     o quanto o som de cada banda aumentou de um instante para o seguinte => ataques (onsets);
  2. andamento (BPM) por autocorrelação + rastreio das batidas por programação dinâmica
     (acompanha músicas que aceleram ou desaceleram um pouco);
  3. as setas: dos ataques detectados, cada dificuldade fica com os mais fortes, respeitando
     um espaço mínimo entre setas; a lane vem da banda dominante (grave, médio, agudo...);
  4. notas longas onde o som da banda se sustenta por mais de uma batida.
"""
from __future__ import annotations

import bisect
import hashlib
import math
import random
from dataclasses import dataclass, field

import numpy as np

import ritmo

SR = 22050                    # taxa de amostragem da análise
N_FFT = 1024
HOP = 256                     # 11,6 ms por quadro
HOP_S = HOP / SR
BANDAS_HZ = ((30, 150), (150, 500), (500, 2000), (2000, 9000))
PESOS_BANDAS = (1.0, 1.0, 0.8, 0.5)
PESOS_LANE = (1.0, 0.95, 0.9, 0.85)      # para escolher a lane quase não se favorece nenhuma banda
BANDA_PARA_LANE = (1, 0, 2, 3)           # grave -> baixo, médio-grave -> esquerda, médio -> cima, agudo -> direita
OFFSET_AMOSTRAS = 660                    # 30 ms: o fluxo espectral "enxerga" o ataque um pouco cedo (calibrado nos testes)
MAX_DURACAO_S = 900
VERSAO_ANALISE = 1


class ErroAnalise(Exception):
    """Mensagem curta (em português) para mostrar ao jogador."""


# ------------------------------------------------------------------ resultado ---
@dataclass
class Analise:
    duracao_ms: float
    bpm: float
    batidas_ms: list = field(default_factory=list)
    confianca: float = 0.0
    metodo: str = "batidas"                # "batidas" ou "livre" (sem batida clara)
    candidatos: list = field(default_factory=list)   # [t_ms, forca, lane, nivel, sustento_ms, v0, v1, v2, v3]
    regularidade: float = 0.0              # 0..1: quão periódico é o ritmo (autocorrelação)

    @property
    def batida_ms(self) -> float:
        return 60000.0 / self.bpm

    def para_dict(self) -> dict:
        return {"versao": VERSAO_ANALISE, "duracao_ms": self.duracao_ms, "bpm": self.bpm,
                "batidas_ms": [round(b, 1) for b in self.batidas_ms], "confianca": self.confianca,
                "metodo": self.metodo, "candidatos": self.candidatos, "regularidade": self.regularidade}

    @classmethod
    def de_dict(cls, d: dict) -> "Analise":
        if d.get("versao") != VERSAO_ANALISE:
            raise ValueError("versão antiga")
        return cls(d["duracao_ms"], d["bpm"], d["batidas_ms"], d["confianca"], d["metodo"],
                   d["candidatos"], d.get("regularidade", 0.0))


def hash_arquivo(caminho) -> str:
    """Identifica o arquivo (tamanho + começo + fim) sem ler tudo."""
    h = hashlib.md5()
    with open(caminho, "rb") as f:
        f.seek(0, 2)
        tam = f.tell()
        h.update(str(tam).encode())
        f.seek(0)
        h.update(f.read(1 << 20))
        if tam > (2 << 20):
            f.seek(-(1 << 20), 2)
            h.update(f.read(1 << 20))
    return h.hexdigest()


def carregar_cache(pasta, id_hash):
    """Análise já feita deste arquivo (ou None)."""
    import json
    from pathlib import Path
    try:
        with open(Path(pasta) / f"{id_hash}.json", encoding="utf-8") as f:
            return Analise.de_dict(json.load(f))
    except (OSError, ValueError, KeyError, TypeError):
        return None


def salvar_cache(pasta, id_hash, an: Analise) -> None:
    import json
    from pathlib import Path
    try:
        Path(pasta).mkdir(parents=True, exist_ok=True)
        with open(Path(pasta) / f"{id_hash}.json", "w", encoding="utf-8") as f:
            json.dump(an.para_dict(), f)
    except OSError:
        pass


# ------------------------------------------------------------------- espectro ---
def _bandas(x, progresso=None):
    """Fluxo espectral e energia de cada banda, quadro a quadro."""
    n_quadros = 1 + max(0, (len(x) - N_FFT) // HOP)
    janela = np.hanning(N_FFT).astype(np.float32)
    freqs = np.fft.rfftfreq(N_FFT, 1.0 / SR)
    indices = [np.where((freqs >= lo) & (freqs < hi))[0] for lo, hi in BANDAS_HZ]
    fluxo = np.zeros((n_quadros, 4), np.float32)
    energia = np.zeros((n_quadros, 4), np.float32)
    anterior = None
    passo = 2048
    for ini in range(0, n_quadros, passo):
        fim = min(n_quadros, ini + passo)
        pos = (np.arange(ini, fim) * HOP)[:, None] + np.arange(N_FFT)[None, :]
        mag = np.abs(np.fft.rfft(x[pos] * janela, axis=1))
        logm = np.log1p(mag * 10.0)
        ant = np.vstack([logm[:1] if anterior is None else anterior, logm[:-1]])
        dif = np.maximum(logm - ant, 0.0)
        for b, idx in enumerate(indices):
            fluxo[ini:fim, b] = dif[:, idx].sum(axis=1)
            energia[ini:fim, b] = np.sqrt((mag[:, idx] ** 2).mean(axis=1))
        anterior = logm[-1:]
        if progresso:
            progresso(fim / n_quadros)
    return fluxo, energia


def _suavizar(v, n):
    k = np.hanning(n + 2)[1:-1]
    return np.convolve(v, k / k.sum(), mode="same")


def _envelope_de_ataques(fluxo):
    """Mistura as bandas num único "quanto atacou agora" e tira a média local."""
    norm = np.empty_like(fluxo)
    for b in range(4):
        ref = np.percentile(fluxo[:, b], 95)
        norm[:, b] = fluxo[:, b] / max(ref, 1e-6)
    env = norm @ np.array(PESOS_BANDAS, np.float32)
    env = _suavizar(env, 5)
    janela = max(3, int(0.4 / HOP_S))
    media = np.convolve(env, np.ones(janela) / janela, mode="same")
    return np.maximum(env - media, 0.0), norm


# --------------------------------------------------------------------- andamento ---
def _autocorrelacao(env):
    e = env - env.mean()
    n = len(e)
    f = np.fft.rfft(e, 2 * n)
    ac = np.fft.irfft(f * np.conj(f))[:n]
    return ac / (ac[0] + 1e-9)


def estimar_bpm(env) -> float:
    ac = _autocorrelacao(env)
    lag_min = max(2, int(60 / (200 * HOP_S)))
    lag_max = min(len(ac) - 2, int(60 / (60 * HOP_S)))
    if lag_max <= lag_min:
        raise ErroAnalise("Música curta demais para achar o ritmo")
    lags = np.arange(lag_min, lag_max + 1)
    bpms = 60.0 / (lags * HOP_S)
    peso = np.exp(-0.5 * (np.log2(bpms / 120.0) / 1.0) ** 2)      # prefere andamentos perto de 120
    pontos = ac[lags] * peso
    i = int(np.argmax(pontos))
    lag = float(lags[i])
    if 0 < i < len(lags) - 1:                                     # interpolação parabólica
        a, b, c = pontos[i - 1], pontos[i], pontos[i + 1]
        den = a - 2 * b + c
        if abs(den) > 1e-9:
            lag += 0.5 * (a - c) / den
    return 60.0 / (lag * HOP_S)


def _rastrear_batidas(env, periodo, rigidez=100.0):
    """Programação dinâmica (Ellis, 2007): batidas em ataques fortes, espaçadas ~ um período."""
    n = len(env)
    p = max(2, int(round(periodo)))
    local = env / (env.std() + 1e-9)
    janela = np.arange(-2 * p, -int(round(p / 2)) + 1)
    pesos = -rigidez * np.log(-janela / p) ** 2
    cum = np.zeros(n)
    volta = np.full(n, -1, dtype=int)
    primeira = True
    limiar = 0.01 * local.max()
    for i in range(n):
        cand = pesos.copy()
        validos = (i + janela) >= 0
        cand[validos] += cum[i + janela[validos]]
        cand[~validos] = pesos[~validos]
        k = int(np.argmax(cand))
        cum[i] = local[i] + cand[k]
        if primeira and local[i] < limiar:
            volta[i] = -1
        else:
            volta[i] = i + janela[k] if validos[k] else -1
            primeira = False
    # última batida: pico de pontuação na parte final
    mediana = np.median(cum[cum > 0]) if np.any(cum > 0) else 0
    picos = [i for i in range(1, n - 1) if cum[i] >= cum[i - 1] and cum[i] > cum[i + 1] and cum[i] > 0.5 * mediana]
    fim = picos[-1] if picos else int(np.argmax(cum))
    batidas = [fim]
    while volta[batidas[-1]] >= 0:
        batidas.append(int(volta[batidas[-1]]))
    return np.array(batidas[::-1])


def _quadro_para_ms(q) -> float:
    return (q * HOP + OFFSET_AMOSTRAS) / SR * 1000.0


def _bpm_por_regressao(batidas_ms) -> float:
    """BPM médio ajustando uma reta aos instantes das batidas (mais preciso que a mediana)."""
    t = np.asarray(batidas_ms, dtype=float)
    idx = np.arange(len(t))
    per = float(np.median(np.diff(t)))
    for _ in range(2):                                   # ignora batidas muito fora da reta
        a, b = np.polyfit(idx, t, 1)
        ok = np.abs(t - (a * idx + b)) < 0.25 * per
        if ok.sum() < 8:
            break
        a, b = np.polyfit(idx[ok], t[ok], 1)
    return 60000.0 / float(a if a > 0 else per)


def _estender_batidas(batidas_ms, duracao_ms):
    """Completa o começo e o fim da música com o mesmo intervalo entre batidas."""
    if len(batidas_ms) < 2:
        return batidas_ms
    per = float(np.median(np.diff(batidas_ms)))
    antes = []
    t = batidas_ms[0] - per
    while t > -per:
        antes.append(t)
        t -= per
    depois = []
    t = batidas_ms[-1] + per
    while t < duracao_ms + per:
        depois.append(t)
        t += per
    return antes[::-1] + list(batidas_ms) + depois


# ---------------------------------------------------------------------- analisar ---
def analisar(x, progresso=None) -> Analise:
    """``x``: amostras mono (float) a 22050 Hz."""
    x = np.asarray(x, dtype=np.float32)
    if len(x) < SR * 5:
        raise ErroAnalise("A música precisa ter pelo menos 5 segundos")
    if len(x) > SR * MAX_DURACAO_S:
        raise ErroAnalise("Música longa demais (máximo 15 minutos)")
    pico = float(np.max(np.abs(x)))
    if pico < 1e-4:
        raise ErroAnalise("O arquivo parece estar em silêncio")
    x = x / pico
    duracao_ms = len(x) / SR * 1000.0

    def prog(a, b):
        return (lambda v: progresso(a + (b - a) * v)) if progresso else None

    fluxo, energia = _bandas(x, prog(0.0, 0.6))
    total = fluxo.sum(axis=1)
    if np.percentile(total, 99) < 5.0:                         # quase nada muda no som (tom contínuo...)
        raise ErroAnalise("Não encontrei ataques de som (música muito contínua?)")
    env, norm = _envelope_de_ataques(fluxo)
    if env.max() < 1e-6:
        raise ErroAnalise("Não encontrei ataques de som (música muito suave?)")
    if progresso:
        progresso(0.65)

    # ---- andamento e batidas
    bpm0 = estimar_bpm(env)
    ac = _autocorrelacao(env)
    lag0 = int(round(60.0 / (bpm0 * HOP_S)))
    regularidade = float(ac[max(2, lag0 - 3):lag0 + 4].max())
    if regularidade < 0.1 and np.percentile(total, 99) / (total.mean() + 1e-9) < 1.6:
        raise ErroAnalise("Não encontrei ritmo nem notas marcantes nesse arquivo")
    frames = _rastrear_batidas(env, 60.0 / (bpm0 * HOP_S))
    if len(frames) < 8:
        raise ErroAnalise("Não consegui acompanhar o ritmo desta música")
    # alinha cada batida ao pico de ataque mais próximo (±3 quadros)
    refinadas = []
    for f in frames:
        lo, hi = max(0, f - 3), min(len(env), f + 4)
        refinadas.append(lo + int(np.argmax(env[lo:hi])))
    batidas_ms = [_quadro_para_ms(f) for f in refinadas]
    bpm = _bpm_por_regressao(batidas_ms)
    while bpm < 70:
        bpm *= 2
    while bpm > 190:
        bpm /= 2
    confianca = float(env[refinadas].mean() / (env.mean() + 1e-9))
    metodo = "batidas" if (confianca >= 1.25 and regularidade >= 0.28) else "livre"
    batidas_ms = _estender_batidas(batidas_ms, duracao_ms)
    if progresso:
        progresso(0.8)

    # ---- ataques
    ref = float(np.percentile(env, 99)) or float(env.max())
    n = len(env)
    cand = []
    for i in range(2, n - 2):
        e = env[i]
        if e <= 0 or e < env[i - 1] or e <= env[i + 1]:
            continue
        lo, hi = max(0, i - 3), min(n, i + 4)
        if e < env[lo:hi].max():
            continue
        forca = min(1.0, float(e / ref))
        if forca < 0.04:
            continue
        a, b, c = env[i - 1], env[i], env[i + 1]
        den = a - 2 * b + c
        delta = float(np.clip(0.5 * (a - c) / den, -0.5, 0.5)) if abs(den) > 1e-9 else 0.0
        t = _quadro_para_ms(i + delta)
        v = norm[max(0, i - 1):i + 2].max(axis=0)
        banda = int(np.argmax(v * np.array(PESOS_LANE)))
        # quanto o som se sustenta depois do ataque (na banda que mais se sustenta entre as que atacaram)
        fim = min(n - 1, i + int(2.5 / HOP_S))
        sustento, banda_sust = 0.0, banda
        for bb in range(4):
            if bb != banda and v[bb] < 0.35:
                continue
            ener = energia[:, bb]
            e0 = float(ener[i:i + 4].max())
            j = i + 4
            while j < fim and ener[j] >= 0.5 * e0:
                j += 1
            ms = (j - i) * HOP_S * 1000.0
            if ms > sustento:
                sustento, banda_sust = ms, bb
        cand.append([round(t, 1), round(forca, 3), BANDA_PARA_LANE[banda], 3, round(sustento, 0)]
                    + [round(float(u), 2) for u in v] + [BANDA_PARA_LANE[banda_sust]])
    if len(cand) < 20:
        raise ErroAnalise("Encontrei poucos ataques de som para criar as setas")

    # ---- nível na grade rítmica (batida / colcheia / semicolcheia) e "colagem" leve
    for c in cand:
        t2, nivel = nivel_na_grade(c[0], batidas_ms) if metodo == "batidas" else (c[0], 0)
        c[0], c[3] = round(t2, 1), nivel
    cand.sort(key=lambda c: c[0])
    if progresso:
        progresso(1.0)
    return Analise(duracao_ms, round(bpm, 2), batidas_ms, round(confianca, 2), metodo, cand,
                   round(regularidade, 2))


def nivel_na_grade(t, batidas_ms):
    """(tempo, nível): 0 = batida, 1 = colcheia, 2 = semicolcheia, 3 = fora da grade.

    Se o ataque estiver a menos de 25 ms de um ponto da grade, o tempo é "colado" nele."""
    k = bisect.bisect_right(batidas_ms, t) - 1
    if k < 0 or k >= len(batidas_ms) - 1:
        return t, 3
    b0, b1 = batidas_ms[k], batidas_ms[k + 1]
    passo = (b1 - b0) / 4.0
    pos = (t - b0) / passo
    j = int(round(pos))
    erro = abs(pos - j) * passo
    if erro > 0.22 * passo:
        return t, 3
    j %= 4
    nivel = 0 if j == 0 else (1 if j == 2 else 2)
    return (b0 + round(pos) * passo if erro <= 25 else t), nivel


# ------------------------------------------------------------------ montar as setas ---
PARAMETROS = {
    "facil":   {"niveis": (0,),           "gap": 420, "nps": 1.2, "corte": 0.22, "holds": 0.10, "livre": False, "duplas": 0.0},
    "medio":   {"niveis": (0, 1),         "gap": 230, "nps": 2.8, "corte": 0.14, "holds": 0.10, "livre": False, "duplas": 0.0},
    "dificil": {"niveis": (0, 1, 2, 3),   "gap": 125, "nps": 5.0, "corte": 0.08, "holds": 0.12, "livre": True,  "duplas": 0.30},
}


def _equilibrar(notas, aceitas):
    """Se alguma lane ficou quase sem setas, passa para ela setas das lanes mais usadas
    (só onde a banda daquela lane também atacou)."""
    total = len(notas)
    if total < 24:
        return
    cont = [0] * 4
    for n in notas:
        cont[n.lane] += 1
    alvo = int(0.14 * total)
    for lane in sorted(range(4), key=lambda l: cont[l]):
        if cont[lane] >= alvo:
            continue
        banda = BANDA_PARA_LANE.index(lane)
        pares = sorted(((c[5 + banda], n) for n, c in zip(notas, aceitas)
                        if cont[n.lane] > alvo * 1.6 and c[5 + banda] >= 0.2),
                       key=lambda p: -p[0])
        for _, n in pares:
            if cont[lane] >= alvo:
                break
            cont[n.lane] -= 1
            n.lane = lane
            cont[lane] += 1


def montar_chart(an: Analise, dificuldade: str, semente=0):
    """Escolhe os ataques da dificuldade e devolve ``(notas, duracao_ms)`` no formato do jogo."""
    p = PARAMETROS[dificuldade]
    rng = random.Random(f"{semente}-{dificuldade}")
    batida = an.batida_ms
    livre_modo = an.metodo == "livre"
    cands = [c for c in an.candidatos
             if c[1] >= p["corte"] and (livre_modo or c[3] in p["niveis"])]
    inicio = an.candidatos[0][0] if an.candidatos else 0
    limite_notas = max(8, int(p["nps"] * max(1.0, (an.duracao_ms - inicio) / 1000.0)))

    aceitas, tempos = [], []
    for c in sorted(cands, key=lambda c: -c[1]):
        t = c[0]
        k = bisect.bisect_left(tempos, t)
        if (k > 0 and t - tempos[k - 1] < p["gap"]) or (k < len(tempos) and tempos[k] - t < p["gap"]):
            continue
        tempos.insert(k, t)
        aceitas.insert(k, c)
        if len(aceitas) >= limite_notas:
            break

    notas = []
    anterior, repeticoes = -1, 0
    for c in aceitas:
        lane = c[2]
        v = c[5:9]
        ordem = sorted(range(4), key=lambda b: -v[b] * PESOS_LANE[b])
        melhor, segundo = ordem[0], ordem[1]
        if v[segundo] * PESOS_LANE[segundo] >= 0.7 * v[melhor] * PESOS_LANE[melhor] and rng.random() < 0.5:
            lane = BANDA_PARA_LANE[segundo]            # varia as lanes quando duas bandas atacam juntas
        if lane == anterior:
            repeticoes += 1
        else:
            repeticoes = 0
        if repeticoes >= 2:                       # evita a mesma seta muitas vezes seguidas
            ordem = sorted(range(4), key=lambda b: -v[b] * PESOS_LANE[b])
            for b in ordem:
                if BANDA_PARA_LANE[b] != anterior:
                    lane = BANDA_PARA_LANE[b]
                    break
            repeticoes = 0
        anterior = lane
        notas.append(ritmo.Nota(c[0], lane, "jogador"))

    _equilibrar(notas, aceitas)

    # setas duplas (só no difícil), nos ataques mais fortes sobre a batida
    if p["duplas"] > 0:
        extras = []
        ultimo = -1e9
        for n, c in zip(notas, aceitas):
            if c[1] >= 0.8 and c[3] == 0 and n.tempo - ultimo > 900 and rng.random() < p["duplas"]:
                v = c[5:9]
                ordem = sorted(range(4), key=lambda b: -v[b])
                outra = next((BANDA_PARA_LANE[b] for b in ordem if BANDA_PARA_LANE[b] != n.lane), None)
                if outra is not None:
                    extras.append(ritmo.Nota(n.tempo, outra, "jogador"))
                    ultimo = n.tempo
        notas += extras

    # notas longas: onde o som se sustenta por mais de uma batida
    info = {c[0]: c for c in aceitas}
    elegiveis = sorted((n for n in notas if n.tempo in info and info[n.tempo][4] >= max(450.0, 0.9 * batida)),
                       key=lambda n: -info[n.tempo][4])
    max_holds = int(p["holds"] * len(notas)) + 1
    passo = batida / 4.0
    feitos = 0
    for n in elegiveis:
        if feitos >= max_holds:
            break
        if any(o is not n and o.tempo == n.tempo for o in notas):
            continue                                   # nada de nota longa em seta dupla
        c = info[n.tempo]
        dur = round(min(c[4] * 0.9, 2.0 * batida) / passo) * passo
        if dur < 0.9 * batida:
            continue
        lane = c[9] if len(c) > 9 else n.lane
        # setas que cairiam durante a nota: na mesma lane (ou em qualquer lane, nas dificuldades
        # que não pedem segurar e apertar ao mesmo tempo)
        dentro = [o for o in notas if o is not n and n.tempo + 60 < o.tempo < n.tempo + dur + 60
                  and (o.lane == lane or not p["livre"])]
        if len(dentro) > 3 or any(o.duracao > 0 for o in dentro):
            continue
        if any(h.lane == lane and h.duracao > 0 and not (n.tempo + dur + 60 < h.tempo or h.tempo + h.duracao + 60 < n.tempo)
               for h in notas):
            continue                                   # não sobrepõe outra nota longa na mesma lane
        for o in dentro:
            notas.remove(o)
        n.lane, n.duracao = lane, dur
        feitos += 1

    notas.sort(key=lambda n: (n.tempo, n.lane))
    return notas, an.duracao_ms + 800.0
