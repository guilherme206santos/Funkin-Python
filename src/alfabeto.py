"""Mapeia caracteres para os glifos da fonte em imagens do FNF (sem Pygame).

A folha de sprites "bold" só tem maiúsculas, alguns símbolos e setas. Letras minúsculas
viram maiúsculas; acentos (Á, Ã, Ç...) são desenhados por código sobre a letra-base;
números e outros símbolos não existem na folha (o jogo usa outra fonte para eles).
"""

LETRAS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
DIRETOS = set("#$%()*+:;=@[]^_|~")
GLIFOS = {
    "'": "-apostraphie-", "’": "-apostraphie-", ".": "-period-", ",": "-comma-",
    "!": "-exclamation point-", "?": "-question mark-", "-": "-dash-", "&": "-andpersand-",
    "/": "-forward slash-", "\\": "-back slash-", "<": "-less than-", ">": "-greater than-",
    "×": "-multiply x-", "←": "-left arrow-", "→": "-right arrow-", "↑": "-up arrow-",
    "↓": "-down arrow-", "♥": "-heart-", '"': "-start quote-", "“": "-start quote-",
    "”": "-end quote-",
}
ACENTUADAS = {
    "Á": ("A", "agudo"), "À": ("A", "grave"), "Â": ("A", "circunflexo"), "Ã": ("A", "til"),
    "É": ("E", "agudo"), "È": ("E", "grave"), "Ê": ("E", "circunflexo"),
    "Í": ("I", "agudo"), "Ó": ("O", "agudo"), "Ô": ("O", "circunflexo"), "Õ": ("O", "til"),
    "Ú": ("U", "agudo"), "Ü": ("U", "trema"), "Ç": ("C", "cedilha"),
}
ALINHA_TOPO = {"-apostraphie-", "-start quote-", "-end quote-", "^", "*"}
ALINHA_MEIO = {"-dash-", "+", "=", "~", "-heart-", "-left arrow-", "-right arrow-", "-up arrow-",
               "-down arrow-", "<", "-less than-", "-greater than-", "-multiply x-"}


def decompor(caractere: str):
    """Devolve (nome_do_glifo, acento) ou ("espaco", None); None se não houver glifo."""
    if caractere == " ":
        return ("espaco", None)
    maiuscula = caractere.upper()
    if len(maiuscula) != 1:
        return None
    if maiuscula in LETRAS:
        return (maiuscula, None)
    if maiuscula in ACENTUADAS:
        return ACENTUADAS[maiuscula]
    if caractere in GLIFOS:
        return (GLIFOS[caractere], None)
    if caractere in DIRETOS:
        return (caractere, None)
    return None


def alinhamento(nome_glifo: str) -> str:
    """'topo', 'meio' ou 'base' (linha de base das letras)."""
    if nome_glifo in ALINHA_TOPO:
        return "topo"
    if nome_glifo in ALINHA_MEIO or nome_glifo.startswith("-"):
        return "meio" if nome_glifo in ALINHA_MEIO else "base"
    return "base"


def suporta(texto: str) -> bool:
    return all(decompor(c) is not None for c in texto)
