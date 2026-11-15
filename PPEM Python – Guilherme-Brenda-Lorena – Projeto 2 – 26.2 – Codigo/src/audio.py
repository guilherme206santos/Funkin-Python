"""Áudio do modo personalizado: abrir qualquer arquivo, preparar para a análise e escolher o arquivo.

Como o jogo lê "qualquer" formato:
  1. o Pygame/SDL abre direto WAV, OGG, MP3, FLAC e outros comuns;
  2. se falhar (M4A, AAC, WMA, OPUS, vídeos...), o ffmpeg converte, caso ele esteja instalado
     (ou via ``pip install imageio-ffmpeg``, que traz o ffmpeg junto).
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

import numpy as np

EXTENSOES = (".mp3", ".wav", ".ogg", ".oga", ".flac", ".m4a", ".aac", ".wma", ".opus", ".aiff", ".aif",
             ".mp2", ".mp4", ".m4b", ".webm", ".mkv", ".mka", ".3gp", ".amr", ".caf", ".mov", ".avi")
SR_ANALISE = 22050


class ErroAudio(Exception):
    """Mensagem curta (em português) para mostrar ao jogador."""


# ----------------------------------------------------------------------- ffmpeg ---
def localizar_ffmpeg():
    exe = shutil.which("ffmpeg")
    if exe:
        return exe
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def converter_com_ffmpeg(origem, destino, freq=44100):
    ffmpeg = localizar_ffmpeg()
    if not ffmpeg:
        raise ErroAudio("sem_ffmpeg")
    cmd = [ffmpeg, "-y", "-v", "error", "-i", str(origem), "-vn", "-ac", "2", "-ar", str(freq),
           "-c:a", "pcm_s16le", str(destino)]
    extra = {"creationflags": 0x08000000} if os.name == "nt" else {}     # sem janela de console
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=300, **extra)
    except (OSError, subprocess.TimeoutExpired):
        raise ErroAudio("Não consegui converter esse arquivo de áudio")
    if r.returncode != 0 or not os.path.exists(destino) or os.path.getsize(destino) < 1000:
        raise ErroAudio("Não consegui ler esse arquivo de áudio")


def carregar_som(caminho):
    """``pygame.mixer.Sound`` com a música inteira, em qualquer formato que o SDL ou o ffmpeg leiam."""
    import pygame
    caminho = str(caminho)
    if not os.path.isfile(caminho):
        raise ErroAudio("Arquivo não encontrado")
    try:
        return pygame.mixer.Sound(caminho)
    except (pygame.error, RuntimeError, OSError):
        pass
    freq = (pygame.mixer.get_init() or (44100,))[0]
    with tempfile.TemporaryDirectory() as pasta:
        wav = os.path.join(pasta, "musica.wav")
        try:
            converter_com_ffmpeg(caminho, wav, freq)
        except ErroAudio as erro:
            if str(erro) == "sem_ffmpeg":
                raise ErroAudio("Formato não suportado. Use MP3/WAV/OGG ou instale o ffmpeg "
                                "(pip install imageio-ffmpeg).")
            raise
        try:
            return pygame.mixer.Sound(wav)           # o Sound já copia os dados para a memória
        except (pygame.error, RuntimeError, OSError):
            raise ErroAudio("Não consegui abrir esse arquivo de áudio")


# ------------------------------------------------------------------ conversões ---
def reamostrar(x, de, para):
    """Troca a taxa de amostragem (média de blocos quando é divisão exata; senão, interpolação)."""
    if de == para:
        return x
    if de % para == 0:
        k = de // para
        n = (len(x) // k) * k
        return x[:n].reshape(-1, k).mean(axis=1)
    destino = int(len(x) * para / de)
    return np.interp(np.linspace(0, len(x) - 1, destino), np.arange(len(x)), x)


def som_para_mono(som):
    """Amostras mono (float -1..1) a 22050 Hz de um ``Sound`` — é o que a análise recebe."""
    import pygame
    arr = pygame.sndarray.array(som).astype(np.float32)
    if arr.ndim == 2:
        arr = arr.mean(axis=1)
    freq = (pygame.mixer.get_init() or (SR_ANALISE,))[0]
    return reamostrar(arr / 32768.0, freq, SR_ANALISE).astype(np.float32)


def buffer_para_mixer(dados_mono_22k: bytes, freq: int, canais: int = 2, formato: int = -16) -> bytes:
    """Converte áudio mono de 22050 Hz (16 bits) para o formato real do mixer (taxa, canais)."""
    x = np.frombuffer(dados_mono_22k, dtype=np.int16).astype(np.float32)
    if freq != 22050 and len(x) > 1:
        destino = int(round(len(x) * freq / 22050.0))
        x = np.interp(np.linspace(0, len(x) - 1, destino), np.arange(len(x)), x)
    if canais > 1:
        x = np.repeat(x[:, None], canais, axis=1).reshape(-1)
    if formato == 32:
        return (x / 32768.0).astype(np.float32).tobytes()
    return np.clip(x, -32768, 32767).astype(np.int16).tobytes()


# --------------------------------------------------------------- escolher arquivo ---
def escolher_arquivo(titulo="Escolha uma música"):
    """Abre a janela de arquivos do sistema. Devolve ``(caminho | None, erro | None)``."""
    try:
        import tkinter
        from tkinter import filedialog
    except ImportError:
        return None, "A janela de arquivos não está disponível (tkinter). Arraste o arquivo para o jogo."
    try:
        raiz = tkinter.Tk()
        raiz.withdraw()
        try:
            raiz.attributes("-topmost", True)
        except tkinter.TclError:
            pass
        padrao = " ".join("*" + e for e in EXTENSOES)
        caminho = filedialog.askopenfilename(
            parent=raiz, title=titulo,
            filetypes=[("Arquivos de áudio", padrao), ("Todos os arquivos", "*.*")])
        raiz.destroy()
    except Exception:
        return None, "Não consegui abrir a janela de arquivos. Arraste o arquivo para o jogo."
    return (caminho or None), None
