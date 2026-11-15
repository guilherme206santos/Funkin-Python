"""Efeitos sonoros curtos gerados por código (bytes PCM 16 bits mono, sem Pygame)."""
from __future__ import annotations

import math
import random
import sys
from array import array

SR = 22050
DOIS_PI = 2 * math.pi


def _para_bytes(amostras) -> bytes:
    ints = array("h", (int(max(-1.0, min(1.0, x)) * 32767) for x in amostras))
    if sys.byteorder == "big":
        ints.byteswap()
    return ints.tobytes()


def _tom(freq, dur, ganho=0.6, queda=12.0, freq_fim=None):
    n = int(SR * dur)
    out, fase = [], 0.0
    for i in range(n):
        t = i / SR
        f = freq if freq_fim is None else freq + (freq_fim - freq) * (i / n)
        fase += DOIS_PI * f / SR
        env = min(1.0, t / 0.004) * math.exp(-t * queda)
        out.append(math.sin(fase) * env * ganho)
    return out


def _juntar(*trechos):
    out = []
    for t in trechos:
        out.extend(t)
    return out


def _erro():
    """Zumbido grave e curto, para MISS."""
    n = int(SR * 0.16)
    out, fase = [], 0.0
    for i in range(n):
        t = i / SR
        fase += DOIS_PI * (150 - 60 * i / n) / SR
        quadrada = 1.0 if math.sin(fase) >= 0 else -1.0
        out.append(quadrada * 0.28 * math.exp(-t * 14))
    return out


def _quebra():
    """Estalo grave, para nota longa solta antes da hora."""
    rng = random.Random(3)
    n = int(SR * 0.12)
    return [(rng.uniform(-1, 1) * 0.5 + math.sin(DOIS_PI * 110 * i / SR) * 0.5)
            * math.exp(-(i / SR) * 28) * 0.5 for i in range(n)]


def _fim():
    return _juntar(*[_tom(f, 0.13, 0.5, 6) for f in (523.25, 659.25, 783.99, 1046.5)])


def _derrota():
    return _juntar(*[_tom(f, 0.2, 0.5, 5) for f in (392.0, 349.23, 311.13, 233.08)])


EFEITOS = {   # nome: (gerador, volume base)
    "erro": (_erro, 0.8),
    "quebra": (_quebra, 0.8),
    "mover": (lambda: _tom(660, 0.04, 0.5, 40), 0.5),
    "ok": (lambda: _juntar(_tom(660, 0.05, 0.5, 30), _tom(990, 0.08, 0.5, 20)), 0.6),
    "voltar": (lambda: _tom(440, 0.07, 0.5, 25, 330), 0.5),
    "contagem": (lambda: _tom(800, 0.09, 0.6, 14), 0.7),
    "vai": (lambda: _tom(1200, 0.2, 0.6, 8), 0.8),
    "fim": (_fim, 0.7),
    "derrota": (_derrota, 0.7),
    "toc": (lambda: _tom(1000, 0.05, 0.9, 40), 1.0),   # clique da calibração
}


def gerar(nome: str) -> bytes:
    return _para_bytes(EFEITOS[nome][0]())


def volume_base(nome: str) -> float:
    return EFEITOS[nome][1]


def metronomo(intervalo_ms: float, cliques: int = 8) -> bytes:
    """Cliques regulares (um laço sem emenda) usados na calibração."""
    total = int(SR * intervalo_ms / 1000.0) * cliques
    buf = [0.0] * total
    clique = _tom(1000, 0.05, 0.9, 40)
    for k in range(cliques):
        ini = int(SR * intervalo_ms / 1000.0) * k
        for i, v in enumerate(clique):
            buf[ini + i] += v
    return _para_bytes(buf)
