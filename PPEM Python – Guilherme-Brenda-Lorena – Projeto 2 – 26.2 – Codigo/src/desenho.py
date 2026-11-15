"""Desenho independente de resolução.

O jogo inteiro é escrito em "unidades de projeto" (uma tela de 1000 x 640). Estas funções
multiplicam tudo por ``K`` antes de desenhar, então a mesma lógica gera uma imagem de
1000x640, 1688x1080 ou 2250x1440 sem ficar pixelada: em tela cheia o jogo é desenhado
direto na resolução do monitor, em vez de esticar uma imagem pequena.

Regras:
  * tuplas e números são unidades de projeto;
  * ``pygame.Rect`` e superfícies já estão em pixels reais.
"""
import pygame

LARGURA, ALTURA = 1000, 640
K = 1.0


def definir_escala(k: float) -> None:
    global K
    K = float(k)


def px(valor) -> int:
    """Comprimento de projeto -> pixels reais."""
    return int(round(valor * K))


def pt(ponto):
    """Ponto de projeto -> pixels reais (int, int)."""
    return (int(round(ponto[0] * K)), int(round(ponto[1] * K)))


def tamanho_real():
    return (px(LARGURA), px(ALTURA))


def _pts(pontos):
    return [(x * K, y * K) for x, y in pontos]


def _larg(largura) -> int:
    return 0 if not largura else max(1, px(largura))


def Rect(x, y, w, h):
    """Retângulo real a partir de medidas de projeto."""
    x0, y0 = round(x * K), round(y * K)
    return pygame.Rect(x0, y0, max(1, round((x + w) * K) - x0), max(1, round((y + h) * K) - y0))


def rect_centro(cx, cy, w, h):
    r = Rect(0, 0, w, h)
    r.center = pt((cx, cy))
    return r


def Surface(tamanho, flags=0):
    return pygame.Surface((max(1, px(tamanho[0])), max(1, px(tamanho[1]))), flags)


def _r(ret):
    return ret if isinstance(ret, pygame.Rect) else Rect(*ret)


def polygon(surf, cor, pontos, largura=0):
    pygame.draw.polygon(surf, cor, _pts(pontos), _larg(largura))


def circle(surf, cor, centro, raio, largura=0):
    pygame.draw.circle(surf, cor, (round(centro[0] * K), round(centro[1] * K)),
                       max(1, px(raio)), _larg(largura))


def rect(surf, cor, ret, largura=0, border_radius=0):
    pygame.draw.rect(surf, cor, _r(ret), _larg(largura), border_radius=px(border_radius))


def line(surf, cor, a, b, largura=1):
    pygame.draw.line(surf, cor, (a[0] * K, a[1] * K), (b[0] * K, b[1] * K), max(1, px(largura)))


def lines(surf, cor, fechada, pontos, largura=1):
    pygame.draw.lines(surf, cor, fechada, _pts(pontos), max(1, px(largura)))


def ellipse(surf, cor, ret, largura=0):
    pygame.draw.ellipse(surf, cor, _r(ret), _larg(largura))


def arc(surf, cor, ret, inicio, fim, largura=1):
    pygame.draw.arc(surf, cor, _r(ret), inicio, fim, max(1, px(largura)))


def blit(destino, origem, pos):
    destino.blit(origem, (round(pos[0] * K), round(pos[1] * K)))


def blit_centro(destino, origem, centro):
    destino.blit(origem, origem.get_rect(center=pt(centro)))
