"""Tudo que é desenhado com Pygame: setas, fontes, personagens, ícones e cenários.

Todas as coordenadas são "unidades de projeto" (1000 x 640); veja ``desenho.py``.
"""
import math
import random
from pathlib import Path

import pygame

import alfabeto
import desenho as D
from atlas import Atlas
from desenho import ALTURA, LARGURA

CHAO_Y = 520

TAM_SETA = 33
ANGULOS = [270, 180, 0, 90]   # esquerda, baixo, cima, direita
CORES_LANE = [(194, 75, 153), (0, 229, 255), (18, 250, 5), (249, 57, 63)]
CORES_RATING = {
    "SICK": (80, 220, 255), "GOOD": (90, 230, 110),
    "BAD": (255, 190, 60), "SHIT": (255, 110, 60), "MISS": (230, 50, 60),
}
CORES_DIFICULDADE = {"facil": (90, 220, 120), "medio": (255, 200, 70), "dificil": (255, 85, 85)}

ESTILO = None      # EstiloSetas (imagens do FNF) ou None => setas desenhadas por código


def usar_estilo(estilo):
    global ESTILO
    ESTILO = estilo


# ----------------------------------------------------------- imagens das setas ---
def _escurecer(sup):
    s = sup.copy()
    s.fill((90, 90, 90), special_flags=pygame.BLEND_RGB_MULT)
    return s


class EstiloSetas:
    """Notas, receptores e notas longas feitos com as folhas de sprites do FNF."""

    ESCALA_NOTA = 0.47     # unidades de projeto por pixel da imagem original (seta ~73)
    LARG_HOLD = 31         # largura do corpo da nota longa (unidades de projeto)
    DIRECOES = ("Left", "Down", "Up", "Right")

    def __init__(self, pasta):
        pasta = Path(pasta)
        e = self.ESCALA_NOTA * D.K
        notas = Atlas(pasta / "notes.png", pasta / "notes.xml")
        strum = Atlas(pasta / "noteStrumline.png", pasta / "noteStrumline.xml")
        self.nota = [notas.quadro(f"note{d}0001", e) for d in self.DIRECOES]
        self.nota_apagada = [_escurecer(s) for s in self.nota]
        self.parado = [strum.quadro(f"static{d}0001", e) for d in self.DIRECOES]
        self.press = [strum.quadro(f"press{d}0003", e) for d in self.DIRECOES]
        self.confirm = [[strum.quadro(f"confirm{d}000{i}", e) for i in (1, 2, 3, 4)]
                        for d in self.DIRECOES]

        folha = pygame.image.load(str(pasta / "NOTE_hold_assets.png")).convert_alpha()
        fator = self.LARG_HOLD * D.K / 50.0
        tam_corpo = (max(1, round(50 * fator)), max(1, round(87 * fator)))
        tam_cauda = (tam_corpo[0], max(1, round(64 * fator)))      # a ponta ocupa só as 64 primeiras linhas
        self.corpo, self.cauda = [], []
        for lane in range(4):                    # cada cor ocupa 2 células de 52 px
            c = folha.subsurface(pygame.Rect(1 + 104 * lane, 0, 50, 87)).copy()
            f = folha.subsurface(pygame.Rect(53 + 104 * lane, 0, 50, 64)).copy()
            self.corpo.append(pygame.transform.smoothscale(c, tam_corpo))
            self.cauda.append(pygame.transform.smoothscale(f, tam_cauda))
        self.corpo_apagado = [_escurecer(s) for s in self.corpo]
        self.cauda_apagada = [_escurecer(s) for s in self.cauda]
        self.cauda_virada = [pygame.transform.flip(s, False, True) for s in self.cauda]
        self.cauda_virada_apagada = [pygame.transform.flip(s, False, True) for s in self.cauda_apagada]

    def _centrar(self, tela, img, cx, cy):
        tela.blit(img, img.get_rect(center=(round(cx * D.K), round(cy * D.K))))

    def desenhar_nota(self, tela, cx, cy, lane, apagada=False):
        self._centrar(tela, (self.nota_apagada if apagada else self.nota)[lane], cx, cy)

    def desenhar_receptor(self, tela, cx, cy, lane, estado, idade_ms):
        if estado == "confirm":
            img = self.confirm[lane][max(0, min(3, int(idade_ms // 45)))]
        elif estado == "press":
            img = self.press[lane]
        else:
            img = self.parado[lane]
        self._centrar(tela, img, cx, cy)

    def desenhar_sustain(self, tela, cx, y_cab, y_cauda, lane, apagada=False):
        k = D.K
        ya, yb = y_cab * k, y_cauda * k
        abaixo = yb >= ya                                  # a cauda fica abaixo da cabeça?
        corpo = (self.corpo_apagado if apagada else self.corpo)[lane]
        if abaixo:
            cauda = (self.cauda_apagada if apagada else self.cauda)[lane]
        else:
            cauda = (self.cauda_virada_apagada if apagada else self.cauda_virada)[lane]
        w, th = corpo.get_size()
        ch = cauda.get_height()
        x = int(round(cx * k - w / 2))
        topo, base = (ya, yb) if abaixo else (yb, ya)
        topo_v, base_v = max(topo, -60), min(base, tela.get_height() + 60)
        if base_v - topo_v < 2:
            return
        antigo = tela.get_clip()
        tela.set_clip(pygame.Rect(0, int(topo_v), tela.get_width(), int(base_v - topo_v) + 1))
        if abaixo:
            cap_y = int(base - ch)
            y = cap_y - th
            while y + th > topo:
                tela.blit(corpo, (x, y))
                y -= th
        else:
            cap_y = int(topo)
            y = cap_y + ch
            while y < base:
                tela.blit(corpo, (x, y))
                y += th
        tela.blit(cauda, (x, cap_y))
        tela.set_clip(antigo)


def carregar_estilo_setas(pasta):
    """Tenta carregar as imagens do FNF; se faltar algo, o jogo desenha as setas por código."""
    try:
        usar_estilo(EstiloSetas(pasta))
    except (OSError, KeyError, pygame.error, ValueError):
        usar_estilo(None)
    return ESTILO is not None


# ------------------------------------------------------------------ setas ---
def pontos_seta(cx, cy, lane, tam):
    base = [(0, -1), (0.95, 0.05), (0.42, 0.05), (0.42, 0.95),
            (-0.42, 0.95), (-0.42, 0.05), (-0.95, 0.05)]
    ang = math.radians(ANGULOS[lane])
    c, s = math.cos(ang), math.sin(ang)
    return [(cx + tam * (x * c - y * s), cy + tam * (x * s + y * c)) for x, y in base]


def desenhar_seta(tela, cx, cy, lane, cor=None, tam=TAM_SETA, apagada=False):
    if ESTILO is not None:
        ESTILO.desenhar_nota(tela, cx, cy, lane, apagada)
        return
    cor = cor or CORES_LANE[lane]
    if apagada:
        cor = tuple(int(c * 0.35) for c in cor)
    pts = pontos_seta(cx, cy, lane, tam)
    D.polygon(tela, cor, pts)
    D.polygon(tela, (255, 255, 255), pts, 3)


def desenhar_receptor(tela, cx, cy, lane, estado="parado", idade_ms=0):
    """estado: "parado", "press" (tecla apertada) ou "confirm" (acerto)."""
    if estado is True:
        estado = "confirm"
    elif estado is False:
        estado = "parado"
    if ESTILO is not None:
        ESTILO.desenhar_receptor(tela, cx, cy, lane, estado, idade_ms)
        return
    pts = pontos_seta(cx, cy, lane, TAM_SETA)
    if estado != "parado":
        escuro = tuple(int(c * 0.55) for c in CORES_LANE[lane])
        D.polygon(tela, escuro, pts)
        D.polygon(tela, CORES_LANE[lane], pts, 4)
    else:
        D.polygon(tela, (45, 45, 60), pts)
        D.polygon(tela, (150, 150, 170), pts, 3)


def desenhar_sustain(tela, cx, y_a, y_b, lane, apagada=False, ativo=False):
    """Corpo de uma nota longa entre as alturas y_a (cabeça) e y_b (cauda)."""
    if ESTILO is not None:
        ESTILO.desenhar_sustain(tela, cx, y_a, y_b, lane, apagada)
        return
    cor = CORES_LANE[lane]
    if apagada:
        cor = tuple(int(c * 0.35) for c in cor)
    topo, base = max(min(y_a, y_b), -40), min(max(y_a, y_b), ALTURA + 40)
    if base - topo < 4:
        return
    D.rect(tela, cor, (cx - 11, topo, 22, base - topo), border_radius=10)
    claro = tuple(min(255, c + (110 if ativo else 60)) for c in cor)
    D.rect(tela, claro, (cx - 3, topo + 4, 6, max(1, base - topo - 8)), border_radius=3)
    D.rect(tela, (255, 255, 255), (cx - 11, topo, 22, base - topo), 2, border_radius=10)


# ------------------------------------------------------------------ fontes ---
class FonteSprites:
    """Fonte feita de imagens: cada letra é um quadro da folha de sprites "bold" do FNF.

    Só existem maiúsculas e alguns símbolos; acentos são desenhados por código sobre a
    letra-base. Para o que não existe (números, por exemplo) use ``Fonte`` com reserva.
    """

    def __init__(self, atlas, altura):
        self.atlas = atlas
        self.e = altura * D.K / 67.0          # 67 px = altura de uma maiúscula na folha
        self._glifos = {}
        self._cache = {}

    def _glifo(self, nome):
        g = self._glifos.get(nome)
        if g is None:
            g = self._glifos[nome] = self.atlas.quadro(nome + "0000", self.e)
        return g

    def metrics(self, msg):
        return [(1,) if alfabeto.decompor(c) else None for c in msg]

    def render(self, msg, antialias, cor):
        base = self._cache.get(msg)
        if base is None:
            base = self._cache[msg] = self._montar(msg)
        cor = tuple(cor[:3])
        if cor == (255, 255, 255):
            return base
        img = base.copy()
        img.fill(cor, special_flags=pygame.BLEND_RGB_MULT)
        return img

    def _acento(self, sup, tipo, cx, topo, base):
        e = self.e
        espessura = max(4, int(8 * e))
        borda = max(2, int(4 * e))
        y1 = int(topo - 2 * e)               # base do acento (logo acima da letra)

        def tracar(pontos):
            for cor, larg in (((0, 0, 0, 255), espessura + 2 * borda), ((255, 255, 255, 255), espessura)):
                pygame.draw.lines(sup, cor, False, pontos, larg)
                for p in pontos:
                    pygame.draw.circle(sup, cor, p, larg // 2)

        if tipo == "agudo":
            tracar([(int(cx - 7 * e), y1), (int(cx + 9 * e), int(y1 - 19 * e))])
        elif tipo == "grave":
            tracar([(int(cx + 7 * e), y1), (int(cx - 9 * e), int(y1 - 19 * e))])
        elif tipo == "circunflexo":
            tracar([(int(cx - 12 * e), y1), (cx, int(y1 - 16 * e)), (int(cx + 12 * e), y1)])
        elif tipo == "til":
            pts = [(int(cx + (-16 + 4 * i) * e), int(y1 - 7 * e - 6 * e * math.sin(i * math.pi / 4)))
                   for i in range(9)]
            tracar(pts)
        elif tipo == "trema":
            for dx in (-9, 9):
                for cor, r in (((0, 0, 0, 255), espessura / 2 + borda), ((255, 255, 255, 255), espessura / 2 + 1)):
                    pygame.draw.circle(sup, cor, (int(cx + dx * e), int(y1 - 8 * e)), max(2, int(r)))
        elif tipo == "cedilha":
            tracar([(int(cx - 2 * e), int(base - 2 * e)), (int(cx + 5 * e), int(base + 5 * e)),
                    (int(cx + 9 * e), int(base + 11 * e)), (int(cx + 4 * e), int(base + 17 * e)),
                    (int(cx - 6 * e), int(base + 16 * e))])

    def _montar(self, msg):
        e = self.e
        cap = int(round(67 * e))
        itens, x = [], 0
        tem_acento = tem_cedilha = False
        for ch in msg:
            d = alfabeto.decompor(ch)
            if d is None:
                continue
            nome, acento = d
            if nome == "espaco":
                x += int(38 * e)
                continue
            g = self._glifo(nome)
            w, h = g.get_size()
            alin = alfabeto.alinhamento(nome)
            y = 0 if alin == "topo" else ((cap - h) // 2 if alin == "meio" else cap - h)
            itens.append((g, x, y, acento, w, h))
            x += w - max(1, int(3 * e))
            tem_acento = tem_acento or acento in ("agudo", "grave", "circunflexo", "til", "trema")
            tem_cedilha = tem_cedilha or acento == "cedilha"
        sup_m = int(12 * e) + (int(38 * e) if tem_acento else 0)
        inf_m = int(26 * e) if tem_cedilha else int(2 * e)
        sup = pygame.Surface((max(1, x + int(3 * e)), sup_m + cap + inf_m), pygame.SRCALPHA)
        for g, gx, gy, acento, w, h in itens:
            sup.blit(g, (gx, sup_m + gy))
            if acento:
                self._acento(sup, acento, gx + w // 2, sup_m + gy, sup_m + gy + h)
        return sup


class Fonte:
    """Fonte principal (arquivo ou sprites) com reserva do sistema.

    Se o texto tiver algum símbolo que a fonte principal não desenha, o texto inteiro é
    desenhado com a reserva em vez de aparecer □□□. ``contorno`` (em px de projeto) dá um
    contorno preto à reserva para combinar com as letras em sprites.
    """

    def __init__(self, principal, reserva=None, contorno=0):
        self.principal = principal if principal is not None else reserva
        self.reserva = reserva
        self.contorno = contorno

    def render(self, msg, antialias, cor):
        fonte = self.principal
        if self.reserva is not None and fonte is not self.reserva:
            try:
                if any(m is None for m in fonte.metrics(msg)):
                    fonte = self.reserva
            except pygame.error:
                fonte = self.reserva
        if self.contorno and fonte is self.reserva and fonte is not self.principal:
            c = max(1, D.px(self.contorno))
            base = fonte.render(msg, antialias, cor)
            preto = fonte.render(msg, antialias, (0, 0, 0))
            w, h = base.get_size()
            out = pygame.Surface((w + 2 * c, h + 2 * c), pygame.SRCALPHA)
            for dx in (-c, 0, c):
                for dy in (-c, 0, c):
                    if dx or dy:
                        out.blit(preto, (c + dx, c + dy))
            out.blit(base, (c, c))
            return out
        return fonte.render(msg, antialias, cor)


def texto(tela, fonte, msg, cor, centro=None, topo_esq=None, sombra=True):
    img = fonte.render(msg, True, cor)
    ret = img.get_rect()
    if centro is not None:
        ret.center = D.pt(centro)
    elif topo_esq is not None:
        ret.topleft = D.pt(topo_esq)
    if sombra:
        sob = fonte.render(msg, True, (0, 0, 0))
        tela.blit(sob, (ret.x + D.px(2), ret.y + D.px(2)))
    tela.blit(img, ret)


def veu(tela, alfa):
    v = pygame.Surface(tela.get_size(), pygame.SRCALPHA)
    v.fill((0, 0, 0, alfa))
    tela.blit(v, (0, 0))


# ------------------------------------------------------------ personagens ---
ESTILOS = {
    "bf": dict(corpo=(60, 140, 235), calca=(40, 50, 110), pele=(250, 215, 190),
               detalhe=(240, 70, 70), acessorio="bone"),
    "diabinho": dict(corpo=(200, 60, 110), calca=(60, 30, 80), pele=(250, 215, 190),
                     detalhe=(255, 220, 80), acessorio="chifres"),
    "robo": dict(corpo=(120, 130, 150), calca=(70, 75, 95), pele=(170, 180, 200),
                 detalhe=(0, 229, 255), acessorio="antena"),
    "fantasma": dict(corpo=(225, 235, 255), calca=(225, 235, 255), pele=(240, 245, 255),
                     detalhe=(150, 170, 230), acessorio="fantasma"),
    "dragao": dict(corpo=(60, 170, 90), calca=(40, 120, 70), pele=(90, 200, 110),
                   detalhe=(255, 140, 40), acessorio="dragao"),
}
NOMES_PERSONAGENS = {"bf": "Boyfriend", "diabinho": "Diabinho", "robo": "Robô X-9",
                     "fantasma": "Fantasminha", "dragao": "Dragão Brasa"}
ORDEM_PERSONAGENS = ("bf", "diabinho", "robo", "fantasma", "dragao")


def cor_do_estilo(estilo):
    return ESTILOS[estilo]["corpo"]


def desenhar_personagem(tela, x, chao, estilo, pose, fase, olha_direita, t_ms=0.0):
    """Boneco de formas simples. ``pose`` = lane cantada (0..3) ou None."""
    e = ESTILOS[estilo]
    acess = e["acessorio"]
    bop = abs(math.sin(math.pi * fase)) * 8
    flutua = 26 + 7 * math.sin(t_ms / 380.0) if acess == "fantasma" else 0
    y = chao - bop - flutua + (22 if pose == 1 else 0)
    quadril = y - 55
    topo_torso = quadril - 85
    ombro = topo_torso + 16
    cab = (x, int(topo_torso - 36))
    lado = 1 if olha_direita else -1

    # ---- atrás do corpo: asas e cauda do dragão
    if acess == "dragao":
        for s in (-1, 1):
            D.polygon(tela, e["detalhe"], [(x + s * 30, ombro), (x + s * 105, ombro - 75), (x + s * 72, ombro + 24)])
        D.polygon(tela, e["calca"], [(x - lado * 30, quadril + 6), (x - lado * 120, quadril + 34), (x - lado * 30, quadril + 44)])

    # ---- pernas (o fantasma termina em barra ondulada)
    if acess == "fantasma":
        D.rect(tela, e["corpo"], (x - 38, quadril - 10, 76, 52), border_radius=18)
        for dx in (-25, 0, 25):
            D.circle(tela, e["corpo"], (x + dx, int(quadril + 42)), 13)
    else:
        D.rect(tela, e["calca"], (x - 28, quadril, 22, chao - quadril + 6), border_radius=6)
        D.rect(tela, e["calca"], (x + 6, quadril, 22, chao - quadril + 6), border_radius=6)

    # ---- braços
    esq_mao = (x - 52, ombro + 58)
    dir_mao = (x + 52, ombro + 58)
    if pose == 0:
        esq_mao = (x - 120, ombro - 4)
    elif pose == 3:
        dir_mao = (x + 120, ombro - 4)
    elif pose == 2:
        esq_mao, dir_mao = (x - 62, ombro - 78), (x + 62, ombro - 78)
    elif pose == 1:
        esq_mao, dir_mao = (x - 48, ombro + 78), (x + 48, ombro + 78)
    for ombro_x, mao in ((x - 34, esq_mao), (x + 34, dir_mao)):
        D.line(tela, e["corpo"], (ombro_x, ombro), mao, 15)
        D.circle(tela, e["pele"], mao, 10)

    # ---- tronco
    D.rect(tela, e["corpo"], (x - 38, topo_torso, 76, 88), border_radius=14)
    if acess == "antena":
        D.rect(tela, e["calca"], (x - 22, topo_torso + 18, 44, 40), border_radius=6)
        luz = e["detalhe"] if pose is not None else (60, 80, 90)
        D.circle(tela, luz, (x, topo_torso + 38), 9)
    elif acess == "dragao":
        D.ellipse(tela, (235, 222, 150), (x - 22, topo_torso + 14, 44, 62))

    # ---- cabeça
    if acess == "antena":
        D.rect(tela, e["pele"], (cab[0] - 33, cab[1] - 28, 66, 58), border_radius=10)
        visor = e["detalhe"] if pose is not None else (40, 120, 140)
        D.rect(tela, visor, (cab[0] - 25, cab[1] - 14, 50, 18), border_radius=6)
        for dx in (-9, 0, 9):
            D.line(tela, (60, 70, 90), (cab[0] + dx, cab[1] + 12), (cab[0] + dx, cab[1] + 22), 3)
        D.line(tela, e["pele"], (cab[0], cab[1] - 28), (cab[0], cab[1] - 46), 4)
        D.circle(tela, e["detalhe"], (cab[0], cab[1] - 48), 6)
    else:
        D.circle(tela, e["pele"], cab, 34)
        if acess == "dragao":
            D.ellipse(tela, (120, 215, 135), (cab[0] + lado * 14 - 17, cab[1] + 2, 34, 24))
        for dx in (-12, 12):
            ex, ey = cab[0] + dx + 4 * lado, cab[1] - 6
            if acess == "fantasma":
                D.ellipse(tela, (30, 30, 60), (ex - 5, ey - 8, 10, 16))
            elif acess == "dragao":
                D.circle(tela, (255, 230, 80), (ex, ey), 8)
                D.line(tela, (20, 20, 20), (ex + 3 * lado, ey - 7), (ex + 3 * lado, ey + 7), 3)
            else:
                D.circle(tela, (255, 255, 255), (ex, ey), 8)
                D.circle(tela, (20, 20, 30), (ex + 3 * lado, ey), 4)
        if pose is None:
            D.line(tela, (60, 30, 30), (cab[0] - 9, cab[1] + 15), (cab[0] + 9, cab[1] + 15), 3)
        else:
            D.ellipse(tela, (70, 20, 30), (cab[0] - 11, cab[1] + 8, 22, 18))

    # ---- acessórios
    if acess == "bone":
        D.rect(tela, e["detalhe"], (x - 34, cab[1] - 44, 68, 22), border_radius=10)
        D.rect(tela, e["detalhe"], (x + (8 if olha_direita else -46), cab[1] - 28, 38, 8), border_radius=4)
    elif acess == "chifres":
        for dx in (-22, 22):
            D.polygon(tela, e["detalhe"], [(x + dx - 9, cab[1] - 28), (x + dx + 9, cab[1] - 28), (x + dx, cab[1] - 56)])
    elif acess == "dragao":
        for dx in (-16, 0, 16):
            D.polygon(tela, e["detalhe"], [(x + dx - 8, cab[1] - 30), (x + dx + 8, cab[1] - 30), (x + dx, cab[1] - 52)])


def desenhar_icone(tela, cx, cy, cor, triste, escala=1.0):
    r = int(30 * escala)
    D.circle(tela, cor, (cx, cy), r)
    D.circle(tela, (255, 255, 255), (cx, cy), r, 3)
    for dx in (-10, 10):
        D.circle(tela, (20, 20, 30), (cx + dx * escala, cy - 6 * escala), max(2, int(4 * escala)))
    ret = (0, 0, int(22 * escala), int(16 * escala))
    if triste:
        ret = (cx - ret[2] / 2, cy + 14 * escala - ret[3] / 2, ret[2], ret[3])
        D.arc(tela, (20, 20, 30), ret, 0, math.pi, 3)
    else:
        ret = (cx - ret[2] / 2, cy + 6 * escala - ret[3] / 2, ret[2], ret[3])
        D.arc(tela, (20, 20, 30), ret, math.pi, 2 * math.pi, 3)


# --------------------------------------------------------------- cenários ---
def _gradiente(sup, topo, base, y0=0, y1=ALTURA):
    """Degradê vertical desenhado linha a linha em pixels reais."""
    r0, r1 = D.px(y0), min(sup.get_height(), D.px(y1))
    largura = sup.get_width()
    for y in range(r0, r1):
        k = (y - r0) / max(1, r1 - r0)
        cor = tuple(int(topo[i] + (base[i] - topo[i]) * k) for i in range(3))
        pygame.draw.line(sup, cor, (0, y), (largura, y))


def _halo(sup, centro, raio, cor, passos=6, alfa=18):
    """Brilho suave: cada anel é desenhado numa camada própria e somado por transparência."""
    for i in range(passos, 0, -1):
        camada = pygame.Surface(sup.get_size(), pygame.SRCALPHA)
        D.circle(camada, (*cor, alfa), centro, raio + i * 14)
        sup.blit(camada, (0, 0))


def _cenario_palco():
    cen = D.Surface((LARGURA, ALTURA))
    _gradiente(cen, (18, 10, 40), (73, 22, 100))
    luz = pygame.Surface(cen.get_size(), pygame.SRCALPHA)
    for cx in (390, 610):
        D.polygon(luz, (255, 255, 255, 22), [(cx - 18, 0), (cx + 18, 0), (cx + 150, 560), (cx - 150, 560)])
    cen.blit(luz, (0, 0))
    D.rect(cen, (30, 18, 52), (0, CHAO_Y, LARGURA, ALTURA - CHAO_Y))
    D.line(cen, (200, 90, 220), (0, CHAO_Y), (LARGURA, CHAO_Y), 3)
    return cen


def _cenario_cidade():
    rng = random.Random(5)
    cen = D.Surface((LARGURA, ALTURA))
    _gradiente(cen, (8, 10, 40), (95, 30, 115), 0, CHAO_Y)
    _halo(cen, (800, 110), 40, (200, 200, 255))
    D.circle(cen, (240, 240, 255), (800, 110), 40)
    x = 0
    while x < LARGURA:
        w = rng.randint(60, 120)
        h = rng.randint(150, 360)
        D.rect(cen, (14, 12, 34), (x, CHAO_Y - h, w, h))
        D.rect(cen, (30, 24, 70), (x, CHAO_Y - h, w, h), 2)
        for wy in range(CHAO_Y - h + 14, CHAO_Y - 14, 22):
            for wx in range(x + 8, x + w - 12, 18):
                if rng.random() < 0.4:
                    cor = rng.choice([(255, 230, 120), (0, 229, 255), (255, 80, 200)])
                    D.rect(cen, cor, (wx, wy, 8, 10))
        x += w + rng.randint(0, 10)
    D.rect(cen, (16, 10, 36), (0, CHAO_Y, LARGURA, ALTURA - CHAO_Y))
    D.line(cen, (255, 60, 200), (0, CHAO_Y), (LARGURA, CHAO_Y), 3)
    for y in (545, 575, 612):
        D.line(cen, (0, 200, 230), (0, y), (LARGURA, y), 1)
    for k in range(-8, 9):
        D.line(cen, (180, 40, 160), (LARGURA // 2 + k * 30, CHAO_Y), (LARGURA // 2 + k * 160, ALTURA), 1)
    return cen


def _cenario_floresta():
    rng = random.Random(11)
    cen = D.Surface((LARGURA, ALTURA))
    _gradiente(cen, (8, 20, 32), (24, 62, 60), 0, CHAO_Y)
    _halo(cen, (500, 120), 70, (210, 235, 225))
    D.circle(cen, (225, 240, 232), (500, 120), 70)
    for cor_folha, cor_tronco, n, hmin, hmax in (((14, 44, 44), (10, 28, 30), 12, 160, 280),
                                                  ((8, 32, 30), (6, 20, 22), 11, 220, 400)):
        for i in range(n):
            x = int(i * LARGURA / (n - 1)) + rng.randint(-25, 25)
            h = rng.randint(hmin, hmax)
            D.rect(cen, cor_tronco, (x - 8, CHAO_Y - h // 2, 16, h // 2))
            for k in range(3):
                topo = CHAO_Y - h + k * h // 4
                larg = 40 + k * 20
                D.polygon(cen, cor_folha, [(x, topo), (x + larg, topo + h // 3), (x - larg, topo + h // 3)])
    nevoa = pygame.Surface(cen.get_size(), pygame.SRCALPHA)
    for _ in range(9):
        D.ellipse(nevoa, (200, 230, 220, 28), (rng.randint(-100, 800), rng.randint(430, 500), rng.randint(250, 450), 70))
    cen.blit(nevoa, (0, 0))
    D.rect(cen, (12, 28, 26), (0, CHAO_Y, LARGURA, ALTURA - CHAO_Y))
    D.line(cen, (90, 200, 170), (0, CHAO_Y), (LARGURA, CHAO_Y), 3)
    for _ in range(40):
        D.circle(cen, (60, 120, 100), (rng.randint(0, LARGURA), rng.randint(CHAO_Y + 8, ALTURA)), rng.randint(1, 3))
    return cen


def _cenario_vulcao():
    rng = random.Random(23)
    cen = D.Surface((LARGURA, ALTURA))
    _gradiente(cen, (34, 6, 10), (235, 95, 25), 0, CHAO_Y)
    fumaca = pygame.Surface(cen.get_size(), pygame.SRCALPHA)
    for _ in range(14):
        D.circle(fumaca, (30, 20, 20, 60), (rng.randint(300, 700), rng.randint(20, 200)), rng.randint(30, 70))
    cen.blit(fumaca, (0, 0))
    D.polygon(cen, (42, 20, 20), [(150, CHAO_Y), (390, 240), (610, 240), (850, CHAO_Y)])
    D.polygon(cen, (28, 14, 14), [(0, CHAO_Y), (120, 380), (240, CHAO_Y)])
    D.polygon(cen, (28, 14, 14), [(760, CHAO_Y), (900, 360), (1000, CHAO_Y)])
    _halo(cen, (500, 236), 60, (255, 150, 40), 5, 16)
    D.ellipse(cen, (255, 170, 50), (385, 226, 230, 28))
    for sx in (430, 500, 570):
        ponto = [(sx, 250)]
        for yy in range(270, CHAO_Y, 24):
            ponto.append((sx + rng.randint(-14, 14) + (sx - 500) // 6 * (yy - 250) // 40, yy))
        D.lines(cen, (255, 120, 30), False, ponto, 5)
    D.rect(cen, (58, 14, 10), (0, CHAO_Y, LARGURA, ALTURA - CHAO_Y))
    D.line(cen, (255, 130, 30), (0, CHAO_Y), (LARGURA, CHAO_Y), 4)
    for _ in range(18):
        x0, y0 = rng.randint(0, LARGURA), rng.randint(CHAO_Y + 10, ALTURA - 10)
        D.line(cen, (255, 140, 30), (x0, y0), (x0 + rng.randint(-60, 60), y0 + rng.randint(-8, 8)), 2)
    for _ in range(60):
        D.circle(cen, (255, 200, 90), (rng.randint(0, LARGURA), rng.randint(0, CHAO_Y)), rng.randint(1, 2))
    return cen


_CENARIOS = {"palco": _cenario_palco, "cidade": _cenario_cidade,
             "floresta": _cenario_floresta, "vulcao": _cenario_vulcao}


def criar_cenario(nome):
    return _CENARIOS[nome]()
