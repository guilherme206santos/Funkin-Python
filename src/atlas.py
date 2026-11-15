"""Leitor de folhas de sprites no formato Sparrow (.png + .xml), o mesmo usado pelo FNF.

O XML descreve cada quadro: a posição dentro do PNG (x, y, width, height) e, quando o
desenho foi recortado, o deslocamento dentro do quadro original (frameX, frameY,
frameWidth, frameHeight). Manter esse deslocamento é o que alinha as animações.
"""
import xml.etree.ElementTree as ET


def ler_quadros(caminho_xml) -> dict:
    """{nome: (x, y, w, h, frameX, frameY, frameW, frameH)} — não precisa de Pygame."""
    quadros = {}
    for s in ET.parse(caminho_xml).getroot().iter("SubTexture"):
        a = s.attrib
        x, y, w, h = (int(float(a[k])) for k in ("x", "y", "width", "height"))
        fx = int(float(a.get("frameX", 0)))
        fy = int(float(a.get("frameY", 0)))
        fw = int(float(a.get("frameWidth", w)))
        fh = int(float(a.get("frameHeight", h)))
        quadros[a["name"]] = (x, y, w, h, fx, fy, fw, fh)
    return quadros


class Atlas:
    def __init__(self, caminho_png, caminho_xml):
        import pygame
        self._pg = pygame
        self.imagem = pygame.image.load(str(caminho_png)).convert_alpha()
        self.quadros = ler_quadros(caminho_xml)

    def tem(self, nome: str) -> bool:
        return nome in self.quadros

    def quadro(self, nome: str, escala: float = 1.0):
        """Superfície com o quadro inteiro (inclui as margens), já na escala pedida."""
        pg = self._pg
        x, y, w, h, fx, fy, fw, fh = self.quadros[nome]
        sup = pg.Surface((fw, fh), pg.SRCALPHA)
        sup.blit(self.imagem, (-fx, -fy), pg.Rect(x, y, w, h))
        if escala != 1.0:
            sup = pg.transform.smoothscale(
                sup, (max(1, round(fw * escala)), max(1, round(fh * escala))))
        return sup
