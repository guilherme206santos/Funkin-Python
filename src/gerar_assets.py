"""Gera o áudio (.wav) e o mapa de notas de cada música, sem arquivos externos.

Por música:
  assets/audio/<id>_inst.wav            bateria + baixo (uma vez por música)
  assets/audio/<id>_<dif>_op.wav        melodia do oponente  (depende das notas)
  assets/audio/<id>_<dif>_jg.wav        melodia do jogador   (silencia quando você erra)
  assets/charts/<id>_<dif>.json         mapa de notas

O jogo chama ``garantir()`` sozinho, só para a música/dificuldade escolhida.
Uso manual:
  python src/gerar_assets.py                 # tudo (demora um pouco)
  python src/gerar_assets.py neon dificil    # uma música/dificuldade
"""
from __future__ import annotations

import math
import random
import sys
import wave
from array import array
from pathlib import Path

import musicas
import ritmo

SR = 22050                                   # taxa de amostragem (mono, 16 bits)
DOIS_PI = 2 * math.pi


# ----------------------------------------------------------------- caminhos ---
def caminho_inst(raiz: Path, m) -> Path:
    return raiz / "assets" / "audio" / f"{m.id}_inst.wav"


def caminho_voz(raiz: Path, m, dif: str, quem: str) -> Path:
    return raiz / "assets" / "audio" / f"{m.id}_{dif}_{quem}.wav"


def caminho_chart(raiz: Path, m, dif: str) -> Path:
    return raiz / "assets" / "charts" / f"{m.id}_{dif}.json"


def pronto(raiz: Path, m, dif: str) -> bool:
    return (ritmo.chart_atual(caminho_chart(raiz, m, dif))
            and all(p.exists() for p in (
                caminho_inst(raiz, m), caminho_voz(raiz, m, dif, "op"),
                caminho_voz(raiz, m, dif, "jg"))))


# ---------------------------------------------------------------- utilidades ---
def _novo_buffer(duracao_ms: float):
    return [0.0] * int(SR * duracao_ms / 1000.0)


def _idx(ms: float) -> int:
    return int(SR * ms / 1000.0)


def _escrever_wav(caminho: Path, buf) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    ints = array("h", (int(max(-1.0, min(1.0, x)) * 32767 * 0.9) for x in buf))
    if sys.byteorder == "big":
        ints.byteswap()
    with wave.open(str(caminho), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(ints.tobytes())


# ------------------------------------------------------------ instrumentos ---
def _kick(buf, ini: int, ganho: float = 0.9) -> None:
    fase = 0.0
    for i in range(int(SR * 0.22)):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        fase += DOIS_PI * (45 + 110 * math.exp(-t * 28)) / SR
        buf[j] += math.sin(fase) * math.exp(-t * 14) * ganho


def _snare(buf, ini: int, rng: random.Random, ganho: float = 1.0) -> None:
    for i in range(int(SR * 0.16)):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        ruido = rng.uniform(-1, 1) * math.exp(-t * 26)
        tom = math.sin(DOIS_PI * 190 * t) * math.exp(-t * 30)
        buf[j] += (ruido * 0.45 + tom * 0.35) * ganho


def _hat(buf, ini: int, rng: random.Random, ganho: float = 0.18) -> None:
    for i in range(int(SR * 0.05)):
        j = ini + i
        if j >= len(buf):
            break
        buf[j] += rng.uniform(-1, 1) * math.exp(-(i / SR) * 90) * ganho


def _baixo(buf, ini: int, freq: float, dur_ms: float, ganho: float = 0.32) -> None:
    n = int(SR * dur_ms / 1000.0)
    fase = 0.0
    for i in range(n):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        fase += DOIS_PI * freq / SR
        env = min(1.0, t / 0.005) * math.exp(-t * 5)
        buf[j] += math.tanh(2.5 * math.sin(fase)) * env * ganho


def _voz(buf, ini: int, freq: float, dur_ms: float, ganho: float, timbre: str,
         sustentada: bool = False) -> None:
    n = int(SR * dur_ms / 1000.0)
    fase = 0.0
    queda = 0.6 if sustentada else 3.5         # nota longa quase não decai
    for i in range(n):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        resto = n - i
        env = min(1.0, t / 0.008) * math.exp(-t * queda)
        if resto < 250:
            env *= resto / 250.0
        fase += DOIS_PI * freq * (1 + 0.004 * math.sin(DOIS_PI * 5.5 * t)) / SR
        if timbre == "quadrada":
            s = math.tanh(4 * math.sin(fase)) * 0.6
        elif timbre == "serra":
            s = (math.sin(fase) + 0.5 * math.sin(2 * fase)
                 + 0.33 * math.sin(3 * fase) + 0.25 * math.sin(4 * fase)) * 0.45
        else:  # "suave"
            s = math.sin(fase) + 0.3 * math.sin(2 * fase) + 0.12 * math.sin(3 * fase)
        buf[j] += s * env * ganho


# --------------------------------------------------------------- geração ---
def _bateria(inst, base, batida, estilo, c, rng) -> None:
    colcheia = batida / 2
    pos = lambda p: _idx(base + p * colcheia)          # p em colcheias (0..7)
    if estilo == "house":
        for b in range(4):
            _kick(inst, _idx(base + b * batida))
            if b in (1, 3):
                _snare(inst, _idx(base + b * batida), rng, 0.9)
            _hat(inst, pos(b * 2 + 1), rng, 0.24)
    elif estilo == "lento":
        _kick(inst, pos(0))
        if c % 2:
            _kick(inst, pos(5), 0.8)
        _snare(inst, pos(4), rng, 1.1)
        for b in range(4):
            _hat(inst, _idx(base + b * batida), rng, 0.16)
    elif estilo == "pesado":
        for p in (0, 3, 4) + ((6, 7) if c % 2 else ()):
            _kick(inst, pos(p), 1.0)
        for p in (2, 6):
            _snare(inst, pos(p), rng, 1.1)
        for p in range(8):
            _hat(inst, pos(p), rng, 0.16)
    else:  # "rock"
        for b in range(4):
            if b in (0, 2) or (b == 3 and c % 2 == 1):
                _kick(inst, _idx(base + b * batida))
            if b in (1, 3):
                _snare(inst, _idx(base + b * batida), rng)
        for p in range(8):
            _hat(inst, pos(p), rng, 0.20 if p % 2 == 0 else 0.10)


def _baixo_compasso(inst, base, batida, estilo, raiz_c) -> None:
    colcheia = batida / 2
    pos = lambda p: _idx(base + p * colcheia)
    if estilo == "lento":
        _baixo(inst, pos(0), raiz_c, batida * 3.6, 0.36)
        _baixo(inst, pos(6), raiz_c * 1.5, batida * 1.6, 0.30)
    elif estilo == "house":
        for p in range(8):
            if p % 2 == 1:
                _baixo(inst, pos(p), raiz_c, colcheia * 0.8, 0.36)
    else:
        for p in range(8):
            freq = raiz_c * 1.5 if p % 4 == 3 else raiz_c
            _baixo(inst, pos(p), freq, colcheia * 0.85)


def gerar_instrumental(raiz: Path, m) -> None:
    rng = random.Random(m.seed)
    batida = ritmo.ms_por_batida(m.bpm)
    dur = ritmo.duracao_ms(m.bpm, m.blocos)
    inst = _novo_buffer(dur + 1500)
    for c in range(int(dur / (batida * 4))):
        base = c * 4 * batida
        _bateria(inst, base, batida, m.bateria, c, rng)
        if c >= 1:
            _baixo_compasso(inst, base, batida, m.bateria, m.raizes[c % 4])
    inst = [x * 0.7 for x in inst]                     # folga para as vozes não estourarem
    _escrever_wav(caminho_inst(raiz, m), inst)


def gerar_vozes(raiz: Path, m, dif: str, notas, duracao: float) -> None:
    colcheia = ritmo.ms_por_batida(m.bpm) / 2
    voz = {"oponente": _novo_buffer(duracao + 1500), "jogador": _novo_buffer(duracao + 1500)}
    for dono in voz:
        proprias = [n for n in notas if n.dono == dono]
        tempos = sorted({n.tempo for n in proprias})
        for n in proprias:
            longa = n.duracao > 0
            if longa:
                dur = n.duracao * 0.97
            else:
                seguintes = [t for t in tempos if t > n.tempo + 1]
                lacuna = (seguintes[0] - n.tempo) if seguintes else colcheia
                dur = min(colcheia * 0.9, lacuna * 0.95)
            if dono == "oponente":
                _voz(voz[dono], _idx(n.tempo), m.escala[n.lane] * 0.5, dur, 0.22, m.timbre_op, longa)
            else:
                _voz(voz[dono], _idx(n.tempo), m.escala[n.lane], dur, 0.20, "suave", longa)
    _escrever_wav(caminho_voz(raiz, m, dif, "op"), voz["oponente"])
    _escrever_wav(caminho_voz(raiz, m, dif, "jg"), voz["jogador"])


# ------------------------------------------------------------ música do menu ---
def caminho_menu(raiz: Path) -> Path:
    return raiz / "assets" / "audio" / "menu.wav"


def _pad(buf, ini: int, freq: float, dur_ms: float, ganho: float) -> None:
    """Nota longa e suave (duas ondas levemente desafinadas) para o fundo do menu."""
    n = int(SR * dur_ms / 1000.0)
    atq, rel = 0.45, 0.6
    f1 = f2 = 0.0
    for i in range(n):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        resto = (n - i) / SR
        env = min(1.0, t / atq) * min(1.0, resto / rel)
        f1 += DOIS_PI * freq / SR
        f2 += DOIS_PI * (freq * 1.004) / SR
        buf[j] += (math.sin(f1) + 0.6 * math.sin(f2) + 0.2 * math.sin(2 * f1)) * env * ganho


def _pluck(buf, ini: int, freq: float, dur_ms: float, ganho: float) -> None:
    n = int(SR * dur_ms / 1000.0)
    fase = 0.0
    for i in range(n):
        j = ini + i
        if j >= len(buf):
            break
        t = i / SR
        fase += DOIS_PI * freq / SR
        buf[j] += (math.sin(fase) + 0.35 * math.sin(2 * fase) + 0.15 * math.sin(3 * fase)) \
            * math.exp(-t * 7.0) * min(1.0, t / 0.004) * ganho


def gerar_menu(raiz: Path) -> None:
    """Tema de menu em loop (16 compassos): pad, arpejo, baixo, bateria e melodia."""
    rng = random.Random(5)
    bpm = 102.0
    batida = 60000.0 / bpm
    compasso = 4 * batida
    colcheia = batida / 2
    n_comp = 16
    total = compasso * n_comp
    buf = _novo_buffer(total + 3000)                  # sobra no fim, que volta para o começo

    acordes = [                                       # Am - F - C - G
        ([220.00, 261.63, 329.63], 110.00),
        ([174.61, 220.00, 261.63], 87.31),
        ([196.00, 261.63, 329.63], 130.81),
        ([196.00, 246.94, 293.66], 98.00),
    ]
    penta = [440.00, 523.25, 587.33, 659.25, 783.99]  # lá menor pentatônica
    frase = [(0, 3, 3), (3, 2, 1), (4, 1, 2), (6, 0, 2), (8, 1, 3), (11, 2, 1), (12, 3, 3),
             (16, 4, 4), (20, 3, 2), (22, 2, 2), (24, 1, 3), (27, 0, 1), (28, 1, 3)]

    for c in range(n_comp):
        base = c * compasso
        tons, raiz_c = acordes[c % 4]
        for f in tons:                                # pad
            _pad(buf, _idx(base), f, compasso * 1.05, 0.045)
        for p in range(8):                            # arpejo em colcheias
            nota = tons[[0, 1, 2, 1, 0, 1, 2, 1][p]] * 2
            _pluck(buf, _idx(base + p * colcheia), nota, colcheia * 1.6, 0.10 if c >= 2 else 0.07)
        if c >= 2:                                    # a partir do 3º compasso entram baixo e bateria
            for p in (0, 3, 4, 6):
                _baixo(buf, _idx(base + p * colcheia), raiz_c, colcheia * 1.4, 0.30)
            _kick(buf, _idx(base), 0.8)
            _kick(buf, _idx(base + 2.5 * batida), 0.6)
            _snare(buf, _idx(base + batida), rng, 0.8)
            _snare(buf, _idx(base + 3 * batida), rng, 0.8)
            for p in range(8):
                _hat(buf, _idx(base + p * colcheia), rng, 0.13 if p % 2 == 0 else 0.07)
        if c >= 4 and c % 4 == 0 and c < 16:          # melodia: 4 compassos por frase
            frase_ms = base
            for pos, idx, dur in frase:
                if pos >= 32:
                    continue
                oitava = 1.0 if c < 8 else (2.0 if (pos // 8) % 2 else 1.0)
                _voz(buf, _idx(frase_ms + pos * colcheia), penta[idx] * oitava,
                     dur * colcheia * 0.92, 0.10, "suave", dur >= 3)

    n_loop = _idx(total)
    for i in range(n_loop, len(buf)):                 # a "cauda" soma no começo => loop sem emenda
        if i - n_loop < n_loop:
            buf[i - n_loop] += buf[i]
    _escrever_wav(caminho_menu(raiz), [x * 0.85 for x in buf[:n_loop]])


def garantir_menu(raiz: Path) -> None:
    if not caminho_menu(raiz).exists():
        gerar_menu(raiz)


def garantir(raiz: Path, m, dif: str) -> None:
    """Cria só o que ainda não existe (ou está desatualizado) para a música/dificuldade."""
    if pronto(raiz, m, dif):
        return
    notas, duracao = ritmo.gerar_chart(m.bpm, m.seed, dif, m.blocos)
    (raiz / "assets" / "charts").mkdir(parents=True, exist_ok=True)
    ritmo.salvar_chart(caminho_chart(raiz, m, dif), notas, duracao, m.bpm, dif)
    if not caminho_inst(raiz, m).exists():
        gerar_instrumental(raiz, m)
    gerar_vozes(raiz, m, dif, notas, duracao)      # as vozes dependem das notas


if __name__ == "__main__":
    RAIZ = Path(__file__).resolve().parent.parent
    ids = sys.argv[1:2] or [m.id for m in musicas.MUSICAS]
    difs = sys.argv[2:3] or list(ritmo.ORDEM_DIFICULDADES)
    for i in ids:
        for d in difs:
            print(f"Gerando {i} / {d} ...", flush=True)
            garantir(RAIZ, musicas.por_id(i), d)
    print("Pronto.")
