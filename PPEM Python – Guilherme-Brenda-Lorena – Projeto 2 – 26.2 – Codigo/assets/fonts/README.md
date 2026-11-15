# Fontes

- `texto.ttf` — fonte dos textos de menus, HUD e pontuação (aqui, a *VCR OSD Mono* do FNF).
- `titulo.ttf` / `titulo.otf` — **opcional**. Se existir, substitui as letras em imagens dos títulos.
  Sem ela, os títulos usam o alfabeto em imagens de `assets/imgs/fnf/fonte_bold.png` (só maiúsculas;
  os acentos são desenhados por código).

Se um texto tiver um símbolo que a fonte principal não tem (por exemplo números nos títulos), o jogo
desenha aquele texto com Arial, com contorno, em vez de mostrar quadradinhos.

Os tamanhos são definidos em `reconstruir_recursos()` no `src/main.py`.
Confira a licença da fonte antes de publicar o jogo.
