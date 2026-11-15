"""Gera o ícone do jogo (assets/imgs/icone.png e icone.ico) a partir das setas do FNF.

Uso (precisa do Pillow:  python -m pip install pillow):
    python src/gerar_icone.py
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

RAIZ = Path(__file__).resolve().parent.parent
PASTA = RAIZ / "assets" / "imgs"
TAM = 1024                                   # desenha grande e reduz (bordas mais suaves)


def _xml_quadro(caminho_xml, nome):
    import xml.etree.ElementTree as ET
    for s in ET.parse(caminho_xml).getroot().iter("SubTexture"):
        if s.attrib["name"] == nome:
            a = s.attrib
            return int(a["x"]), int(a["y"]), int(a["width"]), int(a["height"])
    raise KeyError(nome)


def _fundo():
    """Quadrado arredondado roxo com brilho no centro."""
    img = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    grad = Image.new("RGBA", (TAM, TAM))
    px = grad.load()
    for y in range(TAM):
        k = y / TAM
        cor = (int(34 + 70 * k), int(10 + 24 * k), int(72 + 70 * k), 255)
        for x in range(TAM):
            px[x, y] = cor
    mascara = Image.new("L", (TAM, TAM), 0)
    ImageDraw.Draw(mascara).rounded_rectangle((16, 16, TAM - 16, TAM - 16), radius=210, fill=255)
    img.paste(grad, (0, 0), mascara)
    brilho = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    ImageDraw.Draw(brilho).ellipse((212, 212, TAM - 212, TAM - 212), fill=(255, 120, 230, 120))
    brilho = brilho.filter(ImageFilter.GaussianBlur(110))
    img.alpha_composite(brilho)
    img.putalpha(Image.composite(img.split()[3], Image.new("L", (TAM, TAM), 0), mascara))
    borda = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    ImageDraw.Draw(borda).rounded_rectangle((16, 16, TAM - 16, TAM - 16), radius=210,
                                            outline=(255, 255, 255, 70), width=10)
    img.alpha_composite(borda)
    return img


def gerar():
    notas = Image.open(PASTA / "fnf" / "notes.png").convert("RGBA")
    xml = PASTA / "fnf" / "notes.xml"
    img = _fundo()
    lado = 330                                           # tamanho de cada seta
    c = TAM // 2
    desloc = 262
    posicoes = {"Up": (c, c - desloc), "Down": (c, c + desloc),
                "Left": (c - desloc, c), "Right": (c + desloc, c)}
    camada = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    brilho = Image.new("RGBA", (TAM, TAM), (0, 0, 0, 0))
    for nome, (cx, cy) in posicoes.items():
        x, y, w, h = _xml_quadro(xml, f"note{nome}0001")
        seta = notas.crop((x, y, x + w, y + h))
        seta = seta.resize((lado, int(lado * h / w)), Image.LANCZOS)
        pos = (cx - seta.width // 2, cy - seta.height // 2)
        camada.alpha_composite(seta, pos)
        luz = Image.new("RGBA", seta.size, (255, 255, 255, 0))
        luz.putalpha(seta.split()[3])
        brilho.alpha_composite(luz, pos)
    brilho = brilho.filter(ImageFilter.GaussianBlur(26))
    img.alpha_composite(brilho)
    img.alpha_composite(camada)
    # miolo: disco de vinil com furo
    d = ImageDraw.Draw(img)
    r = 92
    d.ellipse((c - r - 10, c - r - 10, c + r + 10, c + r + 10), fill=(255, 255, 255, 255))
    d.ellipse((c - r, c - r, c + r, c + r), fill=(22, 12, 40, 255))
    for rr in (70, 52):
        d.ellipse((c - rr, c - rr, c + rr, c + rr), outline=(90, 50, 130, 255), width=4)
    d.ellipse((c - 30, c - 30, c + 30, c + 30), fill=(255, 220, 80, 255))
    d.ellipse((c - 9, c - 9, c + 9, c + 9), fill=(22, 12, 40, 255))
    return img


if __name__ == "__main__":
    grande = gerar()
    png = grande.resize((256, 256), Image.LANCZOS)
    png.save(PASTA / "icone.png")
    tamanhos = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]
    grande.resize((256, 256), Image.LANCZOS).save(PASTA / "icone.ico", sizes=tamanhos)
    print("Gerado:", PASTA / "icone.png", "e", PASTA / "icone.ico")
