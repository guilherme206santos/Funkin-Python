"""Funkin' Python — jogo de ritmo no estilo Friday Night Funkin' (Pygame).

Menus: ↑ ↓ ← → e ENTER.  Jogador 1: WASD; jogador 2: setas (mude em Opções).
No jogo: ESC / P pausa, R reinicia, F11 alterna tela cheia.
"""
import bisect
import math
import os
import random
import sys
import threading
import time
import wave
from pathlib import Path

import pygame

import analise
import audio
import config as cfgmod
import desenho as D
import efeitos
import gerar_assets
import musicas
import ritmo
import visual
from atlas import Atlas
from desenho import ALTURA, LARGURA
from visual import CORES_DIFICULDADE, CORES_LANE, CORES_RATING, texto

# ------------------------------------------------------------ configuração ---
if getattr(sys, "frozen", False):      # rodando como .exe (PyInstaller)
    RAIZ = Path(sys.executable).resolve().parent               # áudio e dados gerados
    RECURSOS = Path(getattr(sys, "_MEIPASS", RAIZ))            # imagens e fontes embutidas
else:
    RAIZ = Path(__file__).resolve().parent.parent
    RECURSOS = RAIZ

PASTA_CUSTOM = RAIZ / "dados" / "personalizadas"     # análises já feitas das músicas do jogador
ALVO_Y = 85                    # receptores no topo (setas sobem)
ALVO_Y_BAIXO = ALTURA - 135    # receptores embaixo (downscroll)
ESPACO = 82                    # distância entre lanes
INTERVALO_METRONOMO_MS = 600   # calibração: um toc a cada 600 ms
FADE_MS = 170                  # duração de cada metade da transição entre telas
INTRO_MS = 9200                # duração da introdução
MUSICA_MENU_VOL = 0.7          # volume final da música do menu (como no FNF)

LADO_ESQ = [70 + i * ESPACO for i in range(4)]
LADO_DIR = [LARGURA - 70 - (3 - i) * ESPACO for i in range(4)]
CENTROS = {"oponente": LADO_ESQ, "jogador": LADO_DIR}
RESERVADAS = {pygame.K_ESCAPE, pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_F11}
SIMBOLOS = {"left": "←", "right": "→", "up": "↑", "down": "↓", "space": "ESPAÇO", "": "—"}
ICONES_LANE = ("←", "↓", "↑", "→")

OP_CATEGORIAS = [("Controles - Jogador 1", "controles1"), ("Controles - Jogador 2", "controles2"),
                 ("Vídeo", "video"), ("Jogabilidade", "jogo"), ("Áudio", "audio"),
                 ("Restaurar padrões", "padrao"), ("Voltar", "voltar")]
OP_PAGINAS = {
    "controles1": ["ctl0", "ctl1", "ctl2", "ctl3", "voltar"],
    "controles2": ["ctl0", "ctl1", "ctl2", "ctl3", "voltar"],
    "video": ["fps", "tela", "resolucao", "camera", "voltar"],
    "jogo": ["vel", "down", "ghost", "calibrar", "voltar"],
    "audio": ["vol_musica", "vol_efeitos", "voltar"],
}
ROTULOS = {
    "fps": "FPS", "tela": "Tela cheia", "resolucao": "Resolução",
    "camera": "Efeitos de câmera", "vel": "Velocidade", "down": "Direção das setas",
    "ghost": "Ghost tapping", "calibrar": "Calibrar áudio",
    "vol_musica": "Volume da música", "vol_efeitos": "Volume dos efeitos",
}
AJUDAS = {
    "resolucao": "Maior = mais nítido em tela cheia, porém mais pesado.",
    "vel": "Multiplica a velocidade da dificuldade (vale no multijogador).",
    "ghost": "Desligado: apertar sem nota na tela conta como erro.",
    "calibrar": "Compensa o atraso do som/tela do seu aparelho.",
    "camera": "Zoom nas batidas e tremor quando você erra.",
    "down": "Para baixo: as setas descem até receptores no fundo.",
}
TITULOS_PAGINA = {"controles1": "Controles - Jogador um", "controles2": "Controles - Jogador dois",
                  "video": "Vídeo", "jogo": "Jogabilidade", "audio": "Áudio"}
RANK_CORES = {"S": (255, 215, 80), "A": (120, 255, 160), "B": (100, 200, 255),
              "C": (255, 190, 80), "D": (255, 100, 100)}
COR_JOGADOR = {0: (255, 120, 170), 1: (110, 190, 255)}
NOMES_NUM = ("UM", "DOIS")          # por extenso: a fonte dos títulos não tem números

INICIANDO, INTRO, TITULO, PERSONAGENS, SELECAO = "iniciando", "intro", "titulo", "personagens", "selecao"
OPCOES, CALIBRACAO, CARREGANDO = "opcoes", "calibracao", "carregando"
ANALISANDO = "analisando"
JOGANDO, PAUSA, FIM, DERROTA = "jogando", "pausa", "fim", "derrota"
ESTADOS_MENU = {INTRO, TITULO, PERSONAGENS, SELECAO, OPCOES, CARREGANDO, ANALISANDO}
ENTER = (pygame.K_RETURN, pygame.K_KP_ENTER)

BRANCO, AMARELO, CINZA = (255, 255, 255), (255, 230, 90), (170, 170, 190)


def nome_tecla(nome):
    return SIMBOLOS.get(nome, nome.upper())


def envelope(t, inicio, subida, segura, descida):
    """0 -> 1 -> 0 ao longo do tempo (usado nos fades da introdução)."""
    if t < inicio:
        return 0.0
    t -= inicio
    if t < subida:
        return t / subida
    t -= subida
    if t < segura:
        return 1.0
    t -= segura
    if t < descida:
        return 1.0 - t / descida
    return 0.0


class Jogador:
    """Estado de quem está jogando: suas notas, placar e animações."""

    def __init__(self, indice, centros, estilo, notas):
        self.indice = indice
        self.centros = centros
        self.estilo = estilo
        self.notas = notas
        self.placar = ritmo.Placar()
        self.pressionada = [False] * 4
        self.hit = [-9999.0] * 4          # instante do último acerto em cada lane
        self.segurando = [False] * 4      # lanes com nota longa em andamento
        self.pose = (None, -9999.0)
        self.popups = []


class Jogo:
    def __init__(self):
        pygame.mixer.pre_init(44100, -16, 2, 512)       # estéreo: as músicas do jogador tocam com qualidade
        pygame.init()
        pygame.mixer.set_reserved(4)          # canais 0-2: música da partida; 3: menu; resto: efeitos
        pygame.display.set_caption("Funkin' Python")
        self.cfg = cfgmod.Config.carregar(RAIZ / "dados" / "config.json")
        self.recordes = cfgmod.Recordes(RAIZ / "dados" / "recordes.json")
        self.relogio = pygame.time.Clock()
        self.teclas_down = set()
        self.mapas = [{}, {}]
        self.atlas_letras = None
        self.logo = None
        self.sfx = {nome: self.som_de_buffer(efeitos.gerar(nome)) for nome in efeitos.EFEITOS}
        self.som_metronomo = None
        self.menu_som, self.menu_vol = None, 0.0
        self.menu_canal = pygame.mixer.Channel(3)
        self.definir_icone()
        self.aplicar_tela()                   # define a escala e cria fontes, cenários e imagens
        self.aplicar_volumes()
        self.reconstruir_teclas()

        self.transicao = None
        self.idx_titulo = 0
        self.idx_musica = 0
        self.idx_dif = 1
        self.pratica = False
        self.pratica_bloco = 0
        self.modo_mp = False
        self.mp_idx = [0, 1]
        self.mp_pronto = [False, False]
        self.mp_estilos = ["bf", "diabinho"]
        self.op_cat = 0
        self.op_pag = None
        self.op_sel = 0
        self.op_slot = 0
        self.capturando = False
        self.aviso_msg, self.aviso_ate, self.aviso_cor = "", 0, (255, 140, 140)
        self.cache_info = {}
        self.thread, self.erro_carga = None, None
        self.musica, self.dif = musicas.MUSICAS[0], "medio"
        self.t0 = self.rel_congelado = 0.0
        self.dt = 0.016
        self.cal = None
        self.intro_ini = 0
        self.custom = None                    # música do modo personalizado (arquivo + análise)
        self.analise_info = None
        self.limpar_partida()
        self.restaurar_personalizada()

        # abertura: gera a música do menu na primeira vez e começa a introdução
        if gerar_assets.caminho_menu(RAIZ).exists():
            self.preparar_menu_som()
            self.iniciar_intro()
        else:
            self.estado = INICIANDO
            self.thread, self.erro_carga = None, None

            def tarefa():
                try:
                    gerar_assets.garantir_menu(RAIZ)
                except Exception as exc:
                    self.erro_carga = exc

            self.thread = threading.Thread(target=tarefa, daemon=True)
            self.thread.start()

    # ------------------------------------------------------- tela e recursos ---
    @staticmethod
    def definir_icone():
        """Ícone da janela e da barra de tarefas (assets/imgs/icone.png)."""
        try:
            pygame.display.set_icon(pygame.image.load(str(RECURSOS / "assets" / "imgs" / "icone.png")))
        except (OSError, pygame.error):
            pass

    def calcular_escala(self):
        """Fator K: quantos pixels reais há em cada unidade de projeto."""
        try:
            dw, dh = pygame.display.get_desktop_sizes()[0]
        except (AttributeError, IndexError, pygame.error):
            info = pygame.display.Info()
            dw, dh = info.current_w, info.current_h
        if dw <= 0 or dh <= 0:
            dw, dh = 1280, 720
        if self.cfg.tela_cheia:
            limite = min(dh / ALTURA, dw / LARGURA)
        else:
            limite = min(dh * 0.88 / ALTURA, dw * 0.95 / LARGURA)
        pedido = cfgmod.ESCALA_RESOLUCAO[self.cfg.resolucao]
        return max(0.75, round(min(pedido, limite, 2.25), 3))

    def aplicar_tela(self):
        D.definir_escala(self.calcular_escala())
        flags = pygame.SCALED | (pygame.FULLSCREEN if self.cfg.tela_cheia else 0)
        tam = D.tamanho_real()
        try:
            self.tela = pygame.display.set_mode(tam, flags)
        except pygame.error:
            self.tela = pygame.display.set_mode(tam)
        self.reconstruir_recursos()

    def alternar_tela(self):
        self.cfg.alternar("tela_cheia")
        self.aplicar_tela()
        self.cfg.salvar()

    def carregar_fonte(self, nome, tamanho):
        """titulo: fonte de sprites do FNF (ou assets/fonts/titulo.ttf). texto: VCR (ou texto.ttf)."""
        px = max(8, D.px(tamanho))
        reserva = pygame.font.SysFont("arial", px, bold=True)
        for extensao in (".ttf", ".otf"):
            caminho = RECURSOS / "assets" / "fonts" / (nome + extensao)
            if caminho.exists():
                try:
                    return visual.Fonte(pygame.font.Font(str(caminho), px), reserva)
                except (OSError, pygame.error):
                    break
        if nome == "titulo" and self.atlas_letras is not None:
            return visual.Fonte(visual.FonteSprites(self.atlas_letras, tamanho * 0.9), reserva, contorno=3)
        return visual.Fonte(reserva)

    def reconstruir_recursos(self):
        """Recria tudo que depende da resolução (fontes, cenários, imagens)."""
        pasta_fnf = RECURSOS / "assets" / "imgs" / "fnf"
        if self.atlas_letras is None:
            try:
                self.atlas_letras = Atlas(pasta_fnf / "fonte_bold.png", pasta_fnf / "fonte_bold.xml")
            except (OSError, KeyError, pygame.error, ValueError):
                self.atlas_letras = None
        self.f_titulo = self.carregar_fonte("titulo", 76)
        self.f_grande = self.carregar_fonte("titulo", 56)
        self.f_media = self.carregar_fonte("texto", 34)
        self.f_peq = self.carregar_fonte("texto", 22)
        reserva = pygame.font.SysFont("arial", max(8, D.px(22)), bold=True)
        if self.atlas_letras is not None:
            self.f_logo = visual.Fonte(visual.FonteSprites(self.atlas_letras, 30), reserva, contorno=2)
        else:
            self.f_logo = visual.Fonte(reserva)
        visual.carregar_estilo_setas(pasta_fnf)

        self.cenarios = {n: visual.criar_cenario(n) for n in
                         {"palco"} | {m.cenario for m in musicas.MUSICAS}}
        mini = (D.px(432), D.px(276))
        self.miniaturas = {n: pygame.transform.smoothscale(s, mini) for n, s in self.cenarios.items()}
        self.mundo = pygame.Surface(self.tela.get_size())      # cenário + personagens (recebe zoom)
        self.fade = pygame.Surface(self.tela.get_size())
        self.fade.fill((0, 0, 0))
        self.logo = self.carregar_logo()
        self.intro_texto = [self.f_titulo.render("TRABALHO DE", True, BRANCO),
                            self.f_titulo.render("PROGRAMAÇÃO", True, BRANCO)]

    def carregar_logo(self):
        """assets/imgs/logo_ufs.(png|jpg): se não existir, a introdução usa um logo provisório."""
        for nome in ("logo_ufs.png", "logo_ufs.jpg", "logo_ufs.jpeg"):
            caminho = RECURSOS / "assets" / "imgs" / nome
            if caminho.exists():
                try:
                    img = pygame.image.load(str(caminho)).convert_alpha()
                except (OSError, pygame.error):
                    return None
                w, h = img.get_size()
                fator = min(D.px(300) / h, D.px(700) / w)
                return pygame.transform.smoothscale(img, (max(1, int(w * fator)), max(1, int(h * fator))))
        return None

    def reconstruir_teclas(self):
        self.mapas = [{}, {}]
        for jogador in (0, 1):
            for nome, lane in self.cfg.mapa_teclas(jogador).items():
                try:
                    self.mapas[jogador][pygame.key.key_code(nome)] = lane
                except ValueError:
                    pass
        self.atualizar_pressionadas()

    def atualizar_pressionadas(self):
        for j in getattr(self, "jg", []):
            mapa = self.mapas[j.indice]
            j.pressionada = [any(mapa.get(k) == lane for k in self.teclas_down) for lane in range(4)]

    def avisar(self, msg, ms=1800, cor=(255, 140, 140)):
        self.aviso_msg, self.aviso_ate, self.aviso_cor = msg, pygame.time.get_ticks() + ms, cor

    # ------------------------------------------------------------------- som ---
    def aplicar_volumes(self):
        for nome, som in self.sfx.items():
            som.set_volume(efeitos.volume_base(nome) * self.cfg.vol_efeitos / 100)
        for atributo in ("som_inst", "som_op", "som_jg", "menu_som"):
            som = getattr(self, atributo, None)
            if som is not None:
                som.set_volume(self.cfg.vol_musica / 100)

    @staticmethod
    def som_de_buffer(dados_mono_22k):
        """Cria um Sound a partir de áudio mono de 22050 Hz, convertendo para o formato do mixer."""
        freq, formato, canais = pygame.mixer.get_init()
        return pygame.mixer.Sound(buffer=audio.buffer_para_mixer(dados_mono_22k, freq, canais, formato))

    def tocar_sfx(self, nome):
        som = self.sfx.get(nome)
        if som is not None:
            som.play()

    def previa_volume(self, campo):
        """Toca um som curto no volume que acabou de ser escolhido."""
        if campo == "vol_musica":
            som = self.sfx["ok"]
            som.set_volume(self.cfg.vol_musica / 100)
            som.play()
            self.aplicar_volumes()
        else:
            self.tocar_sfx("ok")

    def carregar_som(self, caminho, inicio_ms=0.0):
        if inicio_ms <= 0:
            som = pygame.mixer.Sound(str(caminho))
        else:                                   # modo prática: começa no meio da música
            with wave.open(str(caminho), "rb") as w:
                w.setpos(min(w.getnframes() - 1, int(w.getframerate() * inicio_ms / 1000.0)))
                dados = w.readframes(w.getnframes())
            som = self.som_de_buffer(dados)
        som.set_volume(self.cfg.vol_musica / 100)
        return som

    # ---- música do menu
    def preparar_menu_som(self):
        try:
            self.menu_som = self.carregar_som(gerar_assets.caminho_menu(RAIZ))
        except (OSError, pygame.error, EOFError, wave.Error):
            self.menu_som = None

    def atualizar_musica_menu(self):
        """Toca o tema do menu em loop. Na introdução o volume sobe aos poucos (como no FNF)."""
        if self.menu_som is None or self.estado not in ESTADOS_MENU:
            return
        if not self.menu_canal.get_busy():
            self.menu_canal.play(self.menu_som, loops=-1)
            self.menu_vol = 0.0
        if self.estado == INTRO:
            idade = pygame.time.get_ticks() - self.intro_ini
            self.menu_vol = MUSICA_MENU_VOL * min(1.0, idade / INTRO_MS)
        else:
            self.menu_vol = min(MUSICA_MENU_VOL, self.menu_vol + self.dt * 0.8)
        self.menu_canal.set_volume(self.menu_vol)

    # --------------------------------------------------------- transições ---
    def ir_para(self, estado, acao=None):
        """Escurece a tela, troca de estado (ou executa ``acao``) e clareia."""
        if self.transicao is None:
            self.transicao = {"destino": estado, "acao": acao, "dur": FADE_MS,
                              "ini": pygame.time.get_ticks(), "trocou": False}

    def desenhar_transicao(self):
        tr = self.transicao
        if tr is None:
            return
        dur = tr["dur"]
        idade = pygame.time.get_ticks() - tr["ini"]
        if not tr["trocou"]:
            k = min(1.0, idade / dur)
            if k >= 1.0:
                if tr["destino"] is not None:
                    self.estado = tr["destino"]
                if tr["acao"] is not None:
                    tr["acao"]()
                tr["trocou"] = True
                tr["ini"] = pygame.time.get_ticks()
        else:
            k = 1.0 - min(1.0, idade / dur)
            if idade >= dur:
                self.transicao = None
        if k > 0:
            self.fade.set_alpha(int(255 * k))
            self.tela.blit(self.fade, (0, 0))

    def clarear(self, dur=600):
        """Começa uma tela já escura e clareia aos poucos."""
        self.transicao = {"destino": None, "acao": None, "dur": dur,
                          "ini": pygame.time.get_ticks(), "trocou": True}

    # ------------------------------------------------------------ introdução ---
    def iniciar_intro(self):
        self.estado = INTRO
        self.intro_ini = pygame.time.get_ticks()

    def terminar_intro(self):
        self.estado = TITULO
        self.clarear(600)

    def checar_inicio(self):
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            self.preparar_menu_som()
            self.iniciar_intro()

    def desenhar_intro(self):
        idade = pygame.time.get_ticks() - self.intro_ini
        self.tela.fill((0, 0, 0))
        a_texto = envelope(idade, 700, 800, 2200, 800)
        if a_texto > 0:
            for i, img in enumerate(self.intro_texto):
                img.set_alpha(int(255 * a_texto))
                D.blit_centro(self.tela, img, (LARGURA // 2, 260 + i * 105))
        a_logo = envelope(idade, 5000, 800, 2300, 800)
        if a_logo > 0:
            if self.logo is not None:
                self.logo.set_alpha(int(255 * a_logo))
                D.blit_centro(self.tela, self.logo, (LARGURA // 2, ALTURA // 2))
            else:                                   # logo provisório (coloque assets/imgs/logo_ufs.png)
                for img, y in ((self.f_titulo.render("UFS", True, BRANCO), 270),
                               (self.f_logo.render("UNIVERSIDADE FEDERAL DE SERGIPE", True, BRANCO), 370)):
                    img.set_alpha(int(255 * a_logo))
                    D.blit_centro(self.tela, img, (LARGURA // 2, y))
        if idade >= INTRO_MS:
            self.terminar_intro()

    # -------------------------------------------------------------------- partida ---
    def limpar_partida(self):
        self.jg = []
        self.notas, self.duracao = [], 0.0
        self.brilho_op = [-9999.0] * 4
        self.op_hit = [-9999.0] * 4
        self.op_ate = [-9999.0] * 4        # até quando o oponente segura cada nota longa
        self.pose_op = (None, -9999.0)
        self.particulas = []
        self.mudo_ate = None
        self.audio_tocando = False
        self.novo_recorde = False
        self.canal_jg = None
        self.velocidade = 0.5
        self.batida = 500.0
        self.abertura = 2000.0
        self.inicio_ms = 0.0
        self.batidas_ms = []                 # batidas reais da música personalizada
        self.alvo_y, self.direcao = ALVO_Y, 1
        self.passo_contagem = -1
        self.ultima_batida = -1
        self.zoom_pulso = 0.0
        self.tremor_ms = 0.0
        self.em_pratica = False

    @property
    def placar(self):
        return self.jg[0].placar if self.jg else ritmo.Placar()

    # ------------------------------------------------------------ modo personalizado ---
    def catalogo(self):
        """Músicas do jogo + o cartão do modo personalizado (sempre o último)."""
        extra = self.musica_personalizada() if self.custom else musicas.modelo_personalizada()
        return musicas.MUSICAS + (extra,)

    def musica_personalizada(self):
        c = self.custom
        return musicas.criar_personalizada(c["nome"], c["analise"].bpm, c["hash"], c["arquivo"], c["visual"])

    @staticmethod
    def nome_da_musica(caminho):
        nome = Path(caminho).stem.replace("_", " ").strip() or "Música"
        return nome if len(nome) <= 40 else nome[:39] + "…"

    def restaurar_personalizada(self):
        """Lembra a última música do jogador (se o arquivo e a análise ainda existirem)."""
        caminho = self.cfg.personalizada
        if not caminho or not os.path.isfile(caminho):
            return
        try:
            id_hash = analise.hash_arquivo(caminho)
        except OSError:
            return
        an = analise.carregar_cache(PASTA_CUSTOM, id_hash)
        if an is not None:
            self.custom = {"arquivo": caminho, "nome": self.nome_da_musica(caminho), "hash": id_hash,
                           "analise": an, "som": None, "visual": 0}

    def abrir_seletor(self):
        """Janela de arquivos do sistema (sai da tela cheia para ela não ficar escondida)."""
        era_cheia = self.cfg.tela_cheia
        if era_cheia:
            self.cfg.tela_cheia = False
            self.aplicar_tela()
        try:
            caminho, erro = audio.escolher_arquivo()
        finally:
            if era_cheia:
                self.cfg.tela_cheia = True
                self.aplicar_tela()
        self.teclas_down.clear()
        self.atualizar_pressionadas()
        if erro:
            self.avisar(erro, 5000)
        elif caminho:
            self.iniciar_analise(caminho)

    def iniciar_analise(self, caminho):
        """Lê o arquivo e analisa o ritmo em segundo plano (a janela continua respondendo)."""
        caminho = str(caminho)
        info = {"etapa": "Lendo o arquivo de áudio...", "prog": 0.0, "erro": None, "resultado": None,
                "nome": self.nome_da_musica(caminho)}
        self.analise_info = info
        self.estado = ANALISANDO

        def tarefa():
            try:
                if not os.path.isfile(caminho):
                    raise audio.ErroAudio("Arquivo não encontrado")
                id_hash = analise.hash_arquivo(caminho)
                som = audio.carregar_som(caminho)
                an = analise.carregar_cache(PASTA_CUSTOM, id_hash)
                if an is None:
                    info["etapa"] = "Analisando o ritmo..."
                    x = audio.som_para_mono(som)
                    an = analise.analisar(x, lambda v: info.__setitem__("prog", v))
                    analise.salvar_cache(PASTA_CUSTOM, id_hash, an)
                som.set_volume(self.cfg.vol_musica / 100)
                info["resultado"] = {"arquivo": caminho, "nome": info["nome"], "hash": id_hash,
                                     "analise": an, "som": som}
            except (audio.ErroAudio, analise.ErroAnalise) as exc:
                info["erro"] = str(exc)
            except Exception as exc:                 # qualquer outra falha vira mensagem, não trava o jogo
                info["erro"] = f"Não consegui usar esse arquivo ({type(exc).__name__})"

        self.thread = threading.Thread(target=tarefa, daemon=True)
        self.thread.start()

    def checar_analise(self):
        info = self.analise_info
        if self.thread is None or self.thread.is_alive():
            return
        self.thread = None
        self.estado = SELECAO
        if info["erro"]:
            self.avisar(info["erro"], 5000)
            return
        visual_atual = self.custom["visual"] if self.custom else 0
        self.custom = dict(info["resultado"], visual=visual_atual)
        self.cfg.personalizada = self.custom["arquivo"]
        self.cfg.salvar()
        self.idx_musica = len(musicas.MUSICAS)
        self.pratica = False
        an = self.custom["analise"]
        self.avisar(f"Pronto! {an.bpm:.0f} BPM" + ("" if an.metodo == "batidas" else " (ritmo livre)"),
                    3000, (130, 255, 190))

    def escolher_e_iniciar(self):
        self.musica = self.catalogo()[self.idx_musica]
        self.dif = ritmo.ORDEM_DIFICULDADES[self.idx_dif]
        if self.musica.personalizada:
            if self.custom is None:
                self.abrir_seletor()
                return
            if self.custom["som"] is not None:
                self.iniciar_partida()
                return
            self.estado = CARREGANDO               # recarrega o áudio (ex.: música lembrada de outra sessão)
            self.erro_carga = None

            def tarefa_audio():
                try:
                    som = audio.carregar_som(self.custom["arquivo"])
                    som.set_volume(self.cfg.vol_musica / 100)
                    self.custom["som"] = som
                except Exception as exc:
                    self.erro_carga = exc

            self.thread = threading.Thread(target=tarefa_audio, daemon=True)
            self.thread.start()
            return
        if gerar_assets.pronto(RAIZ, self.musica, self.dif):
            self.iniciar_partida()
            return
        self.estado = CARREGANDO
        self.erro_carga = None

        def tarefa():
            try:
                gerar_assets.garantir(RAIZ, self.musica, self.dif)
            except Exception as exc:          # mostra o erro em vez de travar
                self.erro_carga = exc

        self.thread = threading.Thread(target=tarefa, daemon=True)
        self.thread.start()

    def checar_carga(self):
        if self.thread is not None and not self.thread.is_alive():
            self.thread = None
            if self.erro_carga is not None:
                self.avisar(str(self.erro_carga) if isinstance(self.erro_carga, audio.ErroAudio)
                            else "Erro ao preparar a música", 5000)
                self.estado = SELECAO
            else:
                self.iniciar_partida()

    def iniciar_partida(self):
        m, dif, mp = self.musica, self.dif, self.modo_mp
        pratica, bloco = self.pratica and not mp and not m.personalizada, self.pratica_bloco
        pygame.mixer.stop()
        self.limpar_partida()
        self.em_pratica = pratica
        if m.personalizada:                        # setas criadas a partir da análise da música do jogador
            an = self.custom["analise"]
            notas, self.duracao = analise.montar_chart(an, dif, m.id)
            self.batida = an.batida_ms
            self.batidas_ms = list(an.batidas_ms)
        else:
            notas, self.duracao = ritmo.carregar_chart(gerar_assets.caminho_chart(RAIZ, m, dif))
            self.batida = ritmo.ms_por_batida(m.bpm)
        if pratica and bloco > 0:                # começa 1 compasso antes do bloco escolhido
            self.inicio_ms = max(0.0, ritmo.inicio_bloco_ms(bloco, m.bpm) - 4 * self.batida)
            for n in notas:
                if n.tempo < self.inicio_ms:
                    n.acertada = True
        if mp:
            # cada jogador joga a música inteira (notas do oponente + do jogador) na sua lateral
            def copia():
                return [ritmo.Nota(n.tempo, n.lane, "jogador", n.duracao) for n in notas]
            self.jg = [Jogador(0, LADO_ESQ, self.mp_estilos[0], copia()),
                       Jogador(1, LADO_DIR, self.mp_estilos[1], copia())]
        else:
            self.notas = notas
            self.jg = [Jogador(0, LADO_DIR, "bf", self.notas)]
        if m.personalizada:                        # uma faixa só: a música original, sem vozes separadas
            self.som_inst = self.custom["som"]
            self.som_inst.set_volume(self.cfg.vol_musica / 100)
            self.som_op = self.som_jg = None
        else:
            self.som_inst = self.carregar_som(gerar_assets.caminho_inst(RAIZ, m), self.inicio_ms)
            self.som_op = self.carregar_som(gerar_assets.caminho_voz(RAIZ, m, dif, "op"), self.inicio_ms)
            self.som_jg = self.carregar_som(gerar_assets.caminho_voz(RAIZ, m, dif, "jg"), self.inicio_ms)
        self.velocidade = ritmo.DIFICULDADES[dif]["velocidade"] * self.cfg.vel_mult
        self.alvo_y, self.direcao = (ALVO_Y_BAIXO, -1) if self.cfg.downscroll else (ALVO_Y, 1)
        self.abertura = min(3200.0, 4 * self.batida)
        self.t0 = time.perf_counter() + self.abertura / 1000.0
        self.teclas_down.clear()
        self.atualizar_pressionadas()
        self.estado = JOGANDO

    def posicao_batida(self, t):
        """(índice, fase 0..1) da batida atual; nas músicas personalizadas usa as batidas detectadas."""
        b = self.batidas_ms
        if b:
            k = bisect.bisect_right(b, t) - 1
            if 0 <= k < len(b) - 1:
                return k, (t - b[k]) / (b[k + 1] - b[k])
        return int(t // self.batida), (t % self.batida) / self.batida

    def tempo_rel(self):
        """Milissegundos desde o início da música (negativo durante a contagem)."""
        if self.estado == PAUSA:
            return self.rel_congelado
        return (time.perf_counter() - self.t0) * 1000.0

    def tempo(self):
        """Relógio do jogo: já inclui o início do trecho (prática) e a calibração."""
        return self.tempo_rel() + self.inicio_ms - self.cfg.ajuste_ms

    def tocar_musica(self):
        pygame.mixer.Channel(0).play(self.som_inst)
        if self.som_op is not None:
            pygame.mixer.Channel(1).play(self.som_op)
        if self.som_jg is not None:
            self.canal_jg = pygame.mixer.Channel(2)
            self.canal_jg.play(self.som_jg)
            self.canal_jg.set_volume(1.0)
        self.audio_tocando = True

    def pausar(self):
        self.rel_congelado = self.tempo_rel()
        self.estado = PAUSA
        pygame.mixer.pause()

    def retomar(self):
        self.t0 = time.perf_counter() - self.rel_congelado / 1000.0
        self.estado = JOGANDO
        pygame.mixer.unpause()

    def mutar_jogador(self, t, ms=350):
        if self.canal_jg is not None:
            self.canal_jg.set_volume(0.0)
        self.mudo_ate = t + ms

    def popup(self, j, rating):
        j.popups.append((rating, pygame.time.get_ticks()))

    def tremer(self, ms=250):
        if self.cfg.efeitos_camera and not self.modo_mp:
            self.tremor_ms = max(self.tremor_ms, ms)

    def faiscas(self, j, lane, quantidade):
        cx = j.centros[lane]
        for _ in range(quantidade):
            ang = random.uniform(0, math.tau)
            vel = random.uniform(80, 260)
            self.particulas.append({"x": cx, "y": self.alvo_y, "vx": math.cos(ang) * vel,
                                    "vy": math.sin(ang) * vel - 60, "vida": 0.55, "max": 0.55,
                                    "cor": random.choice((CORES_LANE[lane], BRANCO, AMARELO))})

    # --------------------------------------------------------------------- eventos ---
    def tratar_evento(self, ev):
        if ev.type == pygame.QUIT:
            pygame.quit()
            sys.exit()
        if ev.type == pygame.KEYUP:
            self.teclas_down.discard(ev.key)
            self.atualizar_pressionadas()
            return
        if ev.type == getattr(pygame, "DROPFILE", -1) and self.estado == SELECAO and self.transicao is None:
            self.idx_musica = len(musicas.MUSICAS)             # arrastou um arquivo: vai para o modo personalizado
            self.iniciar_analise(ev.file)
            return
        if ev.type != pygame.KEYDOWN or self.transicao is not None:
            return
        self.teclas_down.add(ev.key)
        self.atualizar_pressionadas()
        if ev.key == pygame.K_F11 and not self.capturando:
            self.alternar_tela()
            return
        self.som_de_menu(ev.key)

        tratador = {
            INTRO: self.tecla_intro, TITULO: self.tecla_titulo, PERSONAGENS: self.tecla_personagens,
            SELECAO: self.tecla_selecao, OPCOES: self.tecla_opcoes, CALIBRACAO: self.tecla_calibracao,
            JOGANDO: self.tecla_jogando, PAUSA: self.tecla_pausa, FIM: self.tecla_fim,
            DERROTA: self.tecla_fim,
        }.get(self.estado)
        if tratador:
            tratador(ev.key)

    def som_de_menu(self, k):
        if self.estado not in (TITULO, PERSONAGENS, SELECAO, OPCOES) or self.capturando:
            return
        if k in (pygame.K_UP, pygame.K_DOWN, pygame.K_LEFT, pygame.K_RIGHT):
            self.tocar_sfx("mover")
        elif k in ENTER or k == pygame.K_SPACE:
            self.tocar_sfx("ok")
        elif k == pygame.K_ESCAPE:
            self.tocar_sfx("voltar")

    def tecla_intro(self, k):
        if k in ENTER or k in (pygame.K_SPACE, pygame.K_ESCAPE):
            self.terminar_intro()

    def tecla_titulo(self, k):
        n = 4
        if k == pygame.K_UP:
            self.idx_titulo = (self.idx_titulo - 1) % n
        elif k == pygame.K_DOWN:
            self.idx_titulo = (self.idx_titulo + 1) % n
        elif k in ENTER or k == pygame.K_SPACE:
            if self.idx_titulo == 0:
                self.modo_mp = False
                self.ir_para(SELECAO)
            elif self.idx_titulo == 1:
                self.mp_pronto = [False, False]
                self.ir_para(PERSONAGENS)
            elif self.idx_titulo == 2:
                self.op_pag, self.capturando = None, False
                self.ir_para(OPCOES)
            else:
                pygame.quit()
                sys.exit()
        elif k == pygame.K_ESCAPE:
            pygame.quit()
            sys.exit()

    # ---- multijogador: escolha dos personagens
    def entrar_selecao_mp(self):
        self.modo_mp = True
        self.mp_estilos = [visual.ORDEM_PERSONAGENS[i] for i in self.mp_idx]

    def tecla_personagens(self, k):
        if k == pygame.K_ESCAPE:
            self.ir_para(TITULO)
            return
        n = len(visual.ORDEM_PERSONAGENS)
        # jogador 1: A / D escolhem, S confirma, W cancela.  Jogador 2: ← / → escolhem, ↓ confirma, ↑ cancela
        teclas = (dict(esq=pygame.K_a, dir=pygame.K_d, ok=pygame.K_s, voltar=pygame.K_w),
                  dict(esq=pygame.K_LEFT, dir=pygame.K_RIGHT, ok=pygame.K_DOWN, voltar=pygame.K_UP))
        for i, t in enumerate(teclas):
            if k == t["esq"] and not self.mp_pronto[i]:
                self.mp_idx[i] = (self.mp_idx[i] - 1) % n
            elif k == t["dir"] and not self.mp_pronto[i]:
                self.mp_idx[i] = (self.mp_idx[i] + 1) % n
            elif k == t["ok"]:
                self.mp_pronto[i] = True
                self.tocar_sfx("ok")
            elif k == t["voltar"]:
                self.mp_pronto[i] = False
        if all(self.mp_pronto) or (k in ENTER and all(self.mp_pronto)):
            self.ir_para(SELECAO, self.entrar_selecao_mp)

    def tecla_selecao(self, k):
        cat = self.catalogo()
        n = len(cat)
        custom_sel = self.idx_musica == len(musicas.MUSICAS)          # cartão do modo personalizado
        if k in (pygame.K_LEFT, pygame.K_RIGHT):
            self.idx_musica = (self.idx_musica + (1 if k == pygame.K_RIGHT else -1)) % n
            self.pratica_bloco = min(self.pratica_bloco, cat[self.idx_musica].blocos - 1)
        elif k == pygame.K_UP:
            self.idx_dif = max(0, self.idx_dif - 1)
        elif k == pygame.K_DOWN:
            self.idx_dif = min(2, self.idx_dif + 1)
        elif k == pygame.K_TAB:
            if custom_sel:
                if self.custom is not None:                         # troca cenário e oponente da sua música
                    self.custom["visual"] = (self.custom["visual"] + 1) % len(musicas.VISUAIS_PERSONALIZADA)
                    self.tocar_sfx("mover")
            elif not self.modo_mp:
                self.pratica = not self.pratica
                self.tocar_sfx("mover")
        elif k == pygame.K_o and custom_sel:
            self.abrir_seletor()
        elif k == pygame.K_PAGEUP and self.pratica and not self.modo_mp and not custom_sel:
            self.pratica_bloco = max(0, self.pratica_bloco - 1)
        elif k == pygame.K_PAGEDOWN and self.pratica and not self.modo_mp and not custom_sel:
            self.pratica_bloco = min(cat[self.idx_musica].blocos - 1, self.pratica_bloco + 1)
        elif k in ENTER or k == pygame.K_SPACE:
            if custom_sel and self.custom is None:
                self.abrir_seletor()
            else:
                self.ir_para(None, self.escolher_e_iniciar)
        elif k == pygame.K_ESCAPE:
            if self.modo_mp:
                self.mp_pronto = [False, False]
                self.ir_para(PERSONAGENS)
            else:
                self.ir_para(TITULO)

    # ---- opções
    def valor_opcao(self, linha):
        c = self.cfg
        return {
            "fps": str(c.fps),
            "tela": "Sim" if c.tela_cheia else "Não",
            "resolucao": cfgmod.ROTULO_RESOLUCAO[c.resolucao],
            "camera": "Sim" if c.efeitos_camera else "Não",
            "vel": f"x{c.vel_mult:.2f}".rstrip("0").rstrip(".") if c.vel_mult != 1.0 else "x1 (normal)",
            "down": "Para baixo" if c.downscroll else "Para cima",
            "ghost": "Ligado" if c.ghost_tapping else "Desligado",
            "calibrar": f"{c.ajuste_ms:+d} ms",
            "vol_musica": f"{c.vol_musica}%",
            "vol_efeitos": f"{c.vol_efeitos}%",
        }[linha]

    def mudar_opcao(self, linha, passo):
        c = self.cfg
        if linha == "fps":
            c.mudar_fps(passo)
        elif linha == "tela":
            self.alternar_tela()
            return
        elif linha == "resolucao":
            c.ajustar("resolucao", passo, circular=True)
            c.salvar()
            self.aplicar_tela()
            return
        elif linha == "camera":
            c.alternar("efeitos_camera")
        elif linha == "down":
            c.alternar("downscroll")
        elif linha == "ghost":
            c.alternar("ghost_tapping")
        elif linha == "vel":
            c.ajustar("vel_mult", passo)
        elif linha in ("vol_musica", "vol_efeitos"):
            c.ajustar(linha, passo)
            self.aplicar_volumes()
            self.previa_volume(linha)
        c.salvar()

    def restaurar_padroes(self):
        antes = (self.cfg.tela_cheia, self.cfg.resolucao)
        self.cfg.restaurar()
        self.cfg.salvar()
        self.reconstruir_teclas()
        self.aplicar_volumes()
        if antes != (self.cfg.tela_cheia, self.cfg.resolucao):
            self.aplicar_tela()
        self.avisar("Padrões restaurados (a calibração foi mantida)")

    def tecla_opcoes(self, k):
        if self.op_pag is None:                           # lista de categorias
            if k == pygame.K_UP:
                self.op_cat = (self.op_cat - 1) % len(OP_CATEGORIAS)
            elif k == pygame.K_DOWN:
                self.op_cat = (self.op_cat + 1) % len(OP_CATEGORIAS)
            elif k == pygame.K_ESCAPE:
                self.ir_para(TITULO)
            elif k in ENTER or k == pygame.K_RIGHT:
                destino = OP_CATEGORIAS[self.op_cat][1]
                if destino == "padrao":
                    if k in ENTER:
                        self.restaurar_padroes()
                elif destino == "voltar":
                    self.ir_para(TITULO)
                else:
                    self.op_pag, self.op_sel, self.op_slot = destino, 0, 0
            return

        ids = OP_PAGINAS[self.op_pag]
        linha = ids[self.op_sel]
        if self.capturando:
            jogador = int(self.op_pag[-1]) - 1
            lane = int(linha[3])
            if k == pygame.K_ESCAPE:
                self.capturando = False
            elif k in RESERVADAS:
                self.avisar("Essa tecla é reservada (ESC, ENTER, F11)")
            elif k in (pygame.K_BACKSPACE, pygame.K_DELETE):
                if self.cfg.limpar_tecla(lane, self.op_slot, jogador):
                    self.cfg.salvar()
                    self.reconstruir_teclas()
                    self.capturando = False
                else:
                    self.avisar("Cada seta precisa de ao menos uma tecla")
            else:
                nome = pygame.key.name(k)
                if nome:
                    if self.cfg.definir_tecla(lane, self.op_slot, nome, jogador):
                        self.cfg.salvar()
                        self.reconstruir_teclas()
                        self.capturando = False
                    else:
                        self.avisar("Cada seta precisa de ao menos uma tecla")
            return
        if k == pygame.K_UP:
            self.op_sel = (self.op_sel - 1) % len(ids)
        elif k == pygame.K_DOWN:
            self.op_sel = (self.op_sel + 1) % len(ids)
        elif k == pygame.K_ESCAPE:
            self.op_pag = None
        elif linha.startswith("ctl"):
            if k in (pygame.K_LEFT, pygame.K_RIGHT):
                self.op_slot = 1 - self.op_slot
            elif k in ENTER:
                self.capturando = True
        elif linha == "voltar":
            if k in ENTER:
                self.op_pag = None
        elif linha == "calibrar":
            if k in ENTER:
                self.iniciar_calibracao()
        elif k == pygame.K_LEFT:
            self.mudar_opcao(linha, -1)
        elif k == pygame.K_RIGHT or k in ENTER:
            self.mudar_opcao(linha, 1)

    # ---- calibração de áudio
    def iniciar_calibracao(self):
        if self.som_metronomo is None:
            self.som_metronomo = self.som_de_buffer(efeitos.metronomo(INTERVALO_METRONOMO_MS))
            self.som_metronomo.set_volume(0.8)
        self.cal = {"inicio": time.perf_counter(), "taps": [], "valor": float(self.cfg.ajuste_ms)}
        pygame.mixer.stop()
        self.som_metronomo.play(loops=-1)
        self.estado = CALIBRACAO

    def sair_calibracao(self):
        pygame.mixer.stop()
        self.cal = None
        self.estado = OPCOES

    def tecla_calibracao(self, k):
        cal = self.cal
        if k == pygame.K_ESCAPE:
            self.sair_calibracao()
        elif k in ENTER:
            self.cfg.definir_ajuste(cal["valor"])
            self.cfg.salvar()
            self.avisar(f"Calibração salva: {self.cfg.ajuste_ms:+d} ms")
            self.sair_calibracao()
        elif k == pygame.K_LEFT:
            cal["valor"] = max(cfgmod.AJUSTE_MIN, cal["valor"] - 5)
        elif k == pygame.K_RIGHT:
            cal["valor"] = min(cfgmod.AJUSTE_MAX, cal["valor"] + 5)
        elif k == pygame.K_r:
            cal["taps"].clear()
            cal["valor"] = float(self.cfg.ajuste_ms)
        elif k == pygame.K_SPACE or k in self.mapas[0]:
            intervalo = INTERVALO_METRONOMO_MS / 1000.0
            x = (time.perf_counter() - cal["inicio"]) % intervalo
            if x > intervalo / 2:
                x -= intervalo
            cal["taps"] = (cal["taps"] + [x * 1000.0])[-12:]
            if len(cal["taps"]) >= 6:
                ordenado = sorted(cal["taps"])
                meio = len(ordenado) // 2
                mediana = ordenado[meio] if len(ordenado) % 2 else (ordenado[meio - 1] + ordenado[meio]) / 2
                cal["valor"] = max(cfgmod.AJUSTE_MIN, min(cfgmod.AJUSTE_MAX, round(mediana)))

    # ---- jogo
    def tecla_jogando(self, k):
        for j in self.jg:
            lane = self.mapas[j.indice].get(k)
            if lane is not None:
                self.apertar(j, lane)
                return
        if k in (pygame.K_ESCAPE, pygame.K_p):
            self.pausar()
        elif k == pygame.K_r:
            self.iniciar_partida()

    def tecla_pausa(self, k):
        if k in (pygame.K_ESCAPE, pygame.K_p) or k in ENTER:
            self.retomar()
        elif k == pygame.K_r:
            self.iniciar_partida()
        elif k == pygame.K_q:
            self.ir_para(SELECAO, pygame.mixer.stop)

    def tecla_fim(self, k):
        if k == pygame.K_r or k in ENTER:
            self.iniciar_partida()
        elif k == pygame.K_ESCAPE:
            self.ir_para(SELECAO)

    def penalizar_erro(self, j, t):
        j.placar.errar()
        self.popup(j, "MISS")
        self.tocar_sfx("erro")
        if not self.modo_mp:
            self.mutar_jogador(t)
            self.tremer()

    def apertar(self, j, lane):
        t = self.tempo()
        nota = ritmo.escolher_nota(j.notas, lane, t)
        if nota is None:
            if not self.cfg.ghost_tapping and self.audio_tocando:
                self.penalizar_erro(j, t)         # sem ghost tapping: apertar à toa é erro
            return
        desvio = t - nota.tempo
        rating = ritmo.julgar(desvio)
        nota.acertada = True
        nota.segurando = nota.duracao > 0
        j.placar.acertar(rating, desvio)
        self.popup(j, rating)
        j.pose = (lane, t)
        j.hit[lane] = t
        if not self.modo_mp:
            self.mudo_ate = None
            if self.canal_jg is not None:
                self.canal_jg.set_volume(1.0)
        if rating == "SICK":
            self.faiscas(j, lane, 12)
        elif rating == "GOOD":
            self.faiscas(j, lane, 5)

    # ------------------------------------------------------------------- atualizar ---
    def atualizar(self):
        rel = self.tempo_rel()
        t = self.tempo()
        dt_ms = min(50.0, self.dt * 1000.0)

        if rel < 0:                                        # contagem regressiva
            passo = int((rel + self.abertura) / (self.abertura / 4))
            if 0 <= passo <= 3 and passo > self.passo_contagem:
                self.passo_contagem = passo
                self.tocar_sfx("contagem")
        elif not self.audio_tocando:
            self.tocar_musica()
            self.tocar_sfx("vai")

        if rel >= 0:
            batida, _ = self.posicao_batida(t)
            if batida != self.ultima_batida:
                self.ultima_batida = batida
                if batida % 4 == 0:
                    self.zoom_pulso = 1.0
                if self.musica.personalizada and not self.modo_mp:     # o oponente só "dança" no ritmo
                    self.pose_op = (batida % 4, t)

        if not self.modo_mp:                               # oponente controlado pelo jogo
            for n in ritmo.varrer_oponente(self.notas, t):
                self.op_hit[n.lane] = t
                self.pose_op = (n.lane, t)
                self.op_ate[n.lane] = n.tempo + n.duracao
            for lane in range(4):                          # nota longa do oponente: segue acesa
                if t < self.op_ate[lane]:
                    self.pose_op = (lane, t)

        for j in self.jg:
            for _ in ritmo.varrer_perdidas(j.notas, t):
                self.penalizar_erro(j, t)
            for tipo, nota in ritmo.atualizar_sustains(j.notas, t, j.pressionada, j.placar, dt_ms):
                if tipo == "quebrado":
                    self.tocar_sfx("quebra")
                    if not self.modo_mp:
                        self.mutar_jogador(t, 500)
                        self.tremer(180)
                else:
                    self.faiscas(j, nota.lane, 14)
            j.segurando = [False] * 4
            for n in j.notas:
                if n.tempo > t + ritmo.JANELA_MAX:
                    break
                if n.segurando:
                    j.segurando[n.lane] = True

        if self.mudo_ate is not None and t >= self.mudo_ate:
            if self.canal_jg is not None:
                self.canal_jg.set_volume(1.0)
            self.mudo_ate = None

        if not self.modo_mp:
            if self.em_pratica:
                self.placar.vida = max(self.placar.vida, 0.1)   # na prática não dá para perder
            if self.placar.derrota:
                pygame.mixer.stop()
                self.tocar_sfx("derrota")
                self.estado = DERROTA
                return
        if t > self.duracao:                               # no multijogador só a música termina a partida
            pygame.mixer.stop()
            self.tocar_sfx("fim")
            if not self.modo_mp and not self.em_pratica:
                self.novo_recorde = self.recordes.registrar(self.musica.id, self.dif, self.placar.pontos)
            self.estado = FIM

    def atualizar_efeitos(self):
        """Partículas, pulso de zoom e tremor (congelam durante a pausa)."""
        if self.estado == PAUSA:
            return
        dt = self.dt
        self.zoom_pulso = max(0.0, self.zoom_pulso - dt * 3.5)
        self.tremor_ms = max(0.0, self.tremor_ms - dt * 1000.0)
        vivas = []
        for p in self.particulas:
            p["vida"] -= dt
            if p["vida"] <= 0:
                continue
            p["vy"] += 700 * dt
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            vivas.append(p)
        self.particulas = vivas

    # --------------------------------------------------------------------- desenho ---
    def desenhar_cena(self, t):
        efeitos_on = self.cfg.efeitos_camera
        alvo = self.mundo if efeitos_on else self.tela
        alvo.blit(self.cenarios[self.musica.cenario], (0, 0))
        _, fase = self.posicao_batida(t)
        agora = pygame.time.get_ticks()

        def pose_ativa(par):
            lane, ini = par
            return lane if (lane is not None and 0 <= t - ini < 230) else None

        if self.modo_mp and len(self.jg) == 2:
            j1, j2 = self.jg
            visual.desenhar_personagem(alvo, 395, 520, j1.estilo, pose_ativa(j1.pose), fase, True, agora)
            visual.desenhar_personagem(alvo, 605, 520, j2.estilo, pose_ativa(j2.pose), fase, False, agora)
        else:
            jg = self.jg[0] if self.jg else None
            visual.desenhar_personagem(alvo, 395, 520, self.musica.oponente,
                                       pose_ativa(self.pose_op), fase, True, agora)
            visual.desenhar_personagem(alvo, 605, 520, "bf",
                                       pose_ativa(jg.pose) if jg else None, fase, False, agora)
        if efeitos_on:                                     # zoom nas batidas + tremor ao errar
            rw, rh = self.mundo.get_size()
            z = 1.04 + 0.03 * self.zoom_pulso ** 2
            w, h = int(rw * z), int(rh * z)
            leve = self.cfg.fps <= 90 and D.K <= 1.4
            escalar = pygame.transform.smoothscale if leve else pygame.transform.scale
            ox, oy = (rw - w) // 2, (rh - h) // 2
            if self.tremor_ms > 0:
                amp = D.px(7) * min(1.0, self.tremor_ms / 250.0)
                ox += int(random.uniform(-amp, amp))
                oy += int(random.uniform(-amp, amp))
            self.tela.blit(escalar(self.mundo, (w, h)), (ox, oy))

    def y_de(self, tempo, t):
        return self.alvo_y + self.direcao * (tempo - t) * self.velocidade

    def estado_receptor(self, j, lane, t):
        """(estado, idade_ms) do receptor de um jogador."""
        if j is None:                                      # oponente do modo 1 jogador
            idade = t - self.op_hit[lane]
            if 0 <= idade < 150 or t < self.op_ate[lane]:
                return ("confirm", max(0.0, idade))
            return ("parado", 0)
        idade = t - j.hit[lane]
        if j.segurando[lane] or 0 <= idade < 150:
            return ("confirm", max(0.0, idade))
        return ("press", 0) if j.pressionada[lane] else ("parado", 0)

    def desenhar_faixa(self, t, notas, centros, dono, j):
        for lane in range(4):
            estado, idade = self.estado_receptor(j, lane, t)
            visual.desenhar_receptor(self.tela, centros[lane], self.alvo_y, lane, estado, idade)

        horizonte = (ALTURA + 100) / self.velocidade
        for n in notas:
            if n.tempo - t > horizonte:
                break
            if dono is not None and n.dono != dono:
                continue
            em_hold = n.segurando or (dono == "oponente" and n.acertada and t < n.tempo + n.duracao)
            if n.acertada and not em_hold:
                continue
            y_cab = self.y_de(n.tempo, t)
            if em_hold and (y_cab - self.alvo_y) * self.direcao < 0:
                y_cab = self.alvo_y                        # a cabeça "gruda" no receptor
            y_cauda = self.y_de(n.tempo + n.duracao, t) if n.duracao > 0 else y_cab
            if max(y_cab, y_cauda) < -60 or min(y_cab, y_cauda) > ALTURA + 60:
                continue
            cx = centros[n.lane]
            if n.duracao > 0:
                visual.desenhar_sustain(self.tela, cx, y_cab, y_cauda, n.lane, n.perdida, em_hold)
            if not n.acertada:
                visual.desenhar_seta(self.tela, cx, y_cab, n.lane, apagada=n.perdida)

    def desenhar_notas(self, t):
        if self.modo_mp:
            for j in self.jg:
                self.desenhar_faixa(t, j.notas, j.centros, None, j)
        else:
            self.desenhar_faixa(t, self.notas, LADO_ESQ, "oponente", None)
            self.desenhar_faixa(t, self.notas, LADO_DIR, "jogador", self.jg[0])
        for p in self.particulas:
            raio = max(1, int(5 * p["vida"] / p["max"]))
            D.circle(self.tela, p["cor"], (p["x"], p["y"]), raio)

    def desenhar_hud(self, t):
        nome_dif = ritmo.DIFICULDADES[self.dif]["nome"]
        extra = "   [PRÁTICA]" if self.em_pratica else ""
        texto(self.tela, self.f_peq, f"{self.musica.nome}  -  {nome_dif}{extra}",
              CORES_DIFICULDADE[self.dif], centro=(LARGURA // 2, 22))
        if self.modo_mp:
            self.desenhar_hud_mp()
            return
        bx, bl, by, ba = 250, 500, ALTURA - 76, 18
        cor_op = visual.cor_do_estilo(self.musica.oponente)
        D.rect(self.tela, (0, 0, 0), (bx - 4, by - 4, bl + 8, ba + 8), border_radius=6)
        D.rect(self.tela, cor_op, (bx, by, bl, ba), border_radius=4)
        larg = int(bl * self.placar.vida)
        D.rect(self.tela, (80, 210, 120), (bx + bl - larg, by, larg, ba), border_radius=4)
        fronteira = bx + bl - larg
        esc = 1.0 + 0.15 * max(0.0, 1 - self.posicao_batida(t)[1] * 3)
        visual.desenhar_icone(self.tela, fronteira - 34, by + ba // 2, cor_op, self.placar.vida > 0.8, esc)
        visual.desenhar_icone(self.tela, fronteira + 34, by + ba // 2, (60, 140, 235), self.placar.vida < 0.2, esc)
        p = self.placar
        resumo = f"Pontos: {p.pontos}   Combo: {p.combo}   Erros: {p.erros}   Precisão: {p.precisao * 100:.0f}%"
        texto(self.tela, self.f_peq, resumo, BRANCO, centro=(LARGURA // 2, ALTURA - 18))

    def desenhar_hud_mp(self):
        j1, j2 = self.jg
        faixa = D.Surface((LARGURA, 74), pygame.SRCALPHA)
        faixa.fill((0, 0, 0, 120))
        D.blit(self.tela, faixa, (0, ALTURA - 74))
        for j, cx in ((j1, 190), (j2, 810)):
            p = j.placar
            texto(self.tela, self.f_peq, f"JOGADOR {j.indice + 1}", COR_JOGADOR[j.indice], centro=(cx, 22))
            texto(self.tela, self.f_peq, f"PONTOS {p.pontos}   COMBO {p.combo}", BRANCO, centro=(cx, ALTURA - 50))
            texto(self.tela, self.f_peq, f"ACERTOS {p.acertos}  ERROS {p.erros}  PREC {p.precisao * 100:.0f}%",
                  BRANCO, centro=(cx, ALTURA - 22))
        # barra de disputa: quem está na frente
        p1, p2 = max(0, j1.placar.pontos), max(0, j2.placar.pontos)
        frac = p1 / (p1 + p2) if p1 + p2 > 0 else 0.5
        bx, bl, by, ba = 430, 140, ALTURA - 44, 16
        D.rect(self.tela, (0, 0, 0), (bx - 4, by - 4, bl + 8, ba + 8), border_radius=6)
        D.rect(self.tela, COR_JOGADOR[1], (bx, by, bl, ba), border_radius=4)
        D.rect(self.tela, COR_JOGADOR[0], (bx, by, max(2, int(bl * frac)), ba), border_radius=4)
        texto(self.tela, self.f_peq, "J1", COR_JOGADOR[0], centro=(bx - 20, by + ba // 2))
        texto(self.tela, self.f_peq, "J2", COR_JOGADOR[1], centro=(bx + bl + 20, by + ba // 2))

    def desenhar_popups(self):
        agora = pygame.time.get_ticks()
        for j in self.jg:
            cx = (j.centros[0] + j.centros[3]) / 2 if self.modo_mp else LARGURA // 2
            vivos = []
            for rating, ini in j.popups:
                idade = agora - ini
                if idade > 700:
                    continue
                vivos.append((rating, ini))
                img = self.f_media.render(rating + ("!!" if rating == "SICK" else ""), True, CORES_RATING[rating])
                img.set_alpha(int(255 * (1 - idade / 700)))
                D.blit_centro(self.tela, img, (cx, 300 - idade * 0.04))
            j.popups = vivos[-6:]
            if j.placar.combo >= 5:
                texto(self.tela, self.f_media, f"x{j.placar.combo}", BRANCO, centro=(cx, 345))

    def desenhar_contagem(self, rel):
        if rel >= 0:
            if rel < 500:
                texto(self.tela, self.f_grande, "VAI!", AMARELO, centro=(LARGURA // 2, 250))
            return
        passo = int((rel + self.abertura) / (self.abertura / 4))
        rotulo = ["3", "2", "1", "PRONTO?"][min(max(passo, 0), 3)]
        texto(self.tela, self.f_grande, rotulo, BRANCO, centro=(LARGURA // 2, 250))

    def desenhar_painel(self, titulo, cor_titulo, linhas):
        visual.veu(self.tela, 170)
        texto(self.tela, self.f_grande, titulo, cor_titulo, centro=(LARGURA // 2, 140))
        for i, (msg, cor) in enumerate(linhas):
            texto(self.tela, self.f_media if i < 2 else self.f_peq, msg, cor,
                  centro=(LARGURA // 2, 240 + i * 46))

    def desenhar_aviso(self):
        if pygame.time.get_ticks() < self.aviso_ate:
            linhas, atual = [], ""
            for palavra in self.aviso_msg.split():            # quebra em linhas de até ~62 caracteres
                if len(atual) + len(palavra) + 1 > 62 and atual:
                    linhas.append(atual)
                    atual = palavra
                else:
                    atual = (atual + " " + palavra).strip()
            linhas.append(atual)
            for i, linha in enumerate(linhas[:2]):
                texto(self.tela, self.f_peq, linha, self.aviso_cor,
                      centro=(LARGURA // 2, ALTURA - 62 + i * 26 - (len(linhas[:2]) - 1) * 13))

    def desenhar_lista(self, itens, sel, y0, passo):
        for i, item in enumerate(itens):
            ativo = i == sel
            texto(self.tela, self.f_media, ("►  " if ativo else "") + item,
                  AMARELO if ativo else BRANCO, centro=(LARGURA // 2, y0 + i * passo))

    # ---- resultados
    def desenhar_resultados(self):
        if self.modo_mp:
            self.desenhar_resultados_mp()
            return
        p = self.placar
        visual.veu(self.tela, 190)
        texto(self.tela, self.f_grande, "MÚSICA COMPLETA!", (120, 255, 160), centro=(LARGURA // 2, 48))
        nome_dif = ritmo.DIFICULDADES[self.dif]["nome"]
        modo = "   -   PRÁTICA (recorde não conta)" if self.em_pratica else ""
        texto(self.tela, self.f_peq, f"{self.musica.nome} - {nome_dif}{modo}", BRANCO, centro=(LARGURA // 2, 108))

        D.circle(self.tela, (25, 25, 45), (170, 215), 70)
        D.circle(self.tela, RANK_CORES[p.rank], (170, 215), 70, 5)
        texto(self.tela, self.f_titulo, p.rank, RANK_CORES[p.rank], centro=(170, 215))

        linhas = [
            (f"{p.pontos} pontos", self.f_media, BRANCO),
            (f"Precisão {p.precisao * 100:.1f}%     Combo máx. {p.combo_max}", self.f_peq, BRANCO),
            ("   ".join(f"{k} {v}" for k, v in p.contagem.items()) + f"     Erros {p.erros}", self.f_peq, (230, 230, 240)),
            (f"Notas longas: {p.sustains_ok} completas, {p.sustains_quebrados} quebradas", self.f_peq, (230, 230, 240)),
            ("NOVO RECORDE!" if self.novo_recorde else
             ("" if self.em_pratica else f"Recorde: {self.recordes.obter(self.musica.id, self.dif)}"),
             self.f_peq, AMARELO),
        ]
        for i, (msg, fonte, cor) in enumerate(linhas):
            if msg:
                texto(self.tela, fonte, msg, cor, topo_esq=(290, 156 + i * 36))
        self.desenhar_histograma(p)
        texto(self.tela, self.f_peq, "R jogar de novo     ESC escolher música", CINZA, centro=(LARGURA // 2, ALTURA - 22))

    def desenhar_histograma(self, p):
        x0, y0, larg, alt = 180, 368, 640, 130
        texto(self.tela, self.f_peq, "Precisão dos seus toques", BRANCO, centro=(LARGURA // 2, y0 - 22))
        D.rect(self.tela, (20, 20, 38), (x0 - 10, y0 - 6, larg + 20, alt + 52), border_radius=10)
        if not p.desvios:
            texto(self.tela, self.f_peq, "Sem acertos para mostrar", CINZA, centro=(LARGURA // 2, y0 + alt // 2))
            return
        cont, media = ritmo.histograma(p.desvios)
        n = len(cont)
        largura_barra = larg / n
        maior = max(cont) or 1
        for i, c in enumerate(cont):
            centro_ms = -ritmo.JANELA_MAX + (i + 0.5) * (2 * ritmo.JANELA_MAX / n)
            rating = ritmo.julgar(centro_ms) or "SHIT"
            h = int(alt * c / maior)
            D.rect(self.tela, CORES_RATING[rating],
                   (x0 + i * largura_barra + 3, y0 + alt - h, largura_barra - 6, h), border_radius=4)
        D.line(self.tela, BRANCO, (x0, y0 + alt), (x0 + larg, y0 + alt), 2)
        D.line(self.tela, BRANCO, (x0 + larg // 2, y0), (x0 + larg // 2, y0 + alt), 1)
        mx = x0 + larg / 2 + max(-ritmo.JANELA_MAX, min(ritmo.JANELA_MAX, media)) / ritmo.JANELA_MAX * (larg / 2)
        D.polygon(self.tela, AMARELO, [(mx, y0 + alt + 2), (mx - 7, y0 + alt + 14), (mx + 7, y0 + alt + 14)])
        for ms in (-160, -80, 0, 80, 160):
            texto(self.tela, self.f_peq, f"{ms:+d}" if ms else "0", CINZA, sombra=False,
                  centro=(x0 + larg / 2 + ms / ritmo.JANELA_MAX * (larg / 2), y0 + alt + 28))
        adiantados = sum(1 for d in p.desvios if d < -5)
        atrasados = sum(1 for d in p.desvios if d > 5)
        lado = "adiantado" if media < 0 else "atrasado"
        texto(self.tela, self.f_peq, f"◄ adiantados: {adiantados}", CINZA, topo_esq=(x0, y0 + 2), sombra=False)
        texto(self.tela, self.f_peq, f"atrasados: {atrasados} ►", CINZA, topo_esq=(x0 + larg - 190, y0 + 2), sombra=False)
        texto(self.tela, self.f_peq, f"Média: {media:+.0f} ms ({lado})", AMARELO, centro=(LARGURA // 2, y0 + alt + 48))

    @staticmethod
    def vencedor(j1, j2):
        """0, 1 ou None (empate): decide por pontos e, se igualar, por precisão."""
        a, b = j1.placar, j2.placar
        if a.pontos != b.pontos:
            return 0 if a.pontos > b.pontos else 1
        if abs(a.precisao - b.precisao) > 1e-9:
            return 0 if a.precisao > b.precisao else 1
        return None

    def desenhar_resultados_mp(self):
        j1, j2 = self.jg
        visual.veu(self.tela, 200)
        venc = self.vencedor(j1, j2)
        titulo = "EMPATE!" if venc is None else f"JOGADOR {NOMES_NUM[venc]} VENCEU!"
        cor = AMARELO if venc is None else COR_JOGADOR[venc]
        texto(self.tela, self.f_grande, titulo, cor, centro=(LARGURA // 2, 56))
        nome_dif = ritmo.DIFICULDADES[self.dif]["nome"]
        texto(self.tela, self.f_peq, f"{self.musica.nome} - {nome_dif}", BRANCO, centro=(LARGURA // 2, 106))
        for j, cx in ((j1, 260), (j2, 740)):
            p = j.placar
            ganhou = venc == j.indice
            D.rect(self.tela, (20, 20, 38), (cx - 215, 128, 430, 430), border_radius=14)
            D.rect(self.tela, COR_JOGADOR[j.indice] if ganhou else (90, 90, 120), (cx - 215, 128, 430, 430), 3 if ganhou else 2, border_radius=14)
            texto(self.tela, self.f_peq, f"JOGADOR {j.indice + 1} - {visual.NOMES_PERSONAGENS[j.estilo]}",
                  COR_JOGADOR[j.indice], centro=(cx, 156))
            D.circle(self.tela, (25, 25, 45), (cx, 245), 56)
            D.circle(self.tela, RANK_CORES[p.rank], (cx, 245), 56, 5)
            texto(self.tela, self.f_titulo, p.rank, RANK_CORES[p.rank], centro=(cx, 245))
            texto(self.tela, self.f_media, f"{p.pontos} pts", AMARELO if ganhou else BRANCO, centro=(cx, 330))
            linhas = [f"Precisão {p.precisao * 100:.1f}%",
                      f"Acertos {p.acertos}     Erros {p.erros}",
                      "  ".join(f"{k} {v}" for k, v in p.contagem.items()),
                      f"Combo máx. {p.combo_max}",
                      f"Notas longas {p.sustains_ok}/{p.sustains_ok + p.sustains_quebrados}"]
            for i, msg in enumerate(linhas):
                texto(self.tela, self.f_peq, msg, (230, 230, 240), centro=(cx, 380 + i * 34))
        texto(self.tela, self.f_peq, "R jogar de novo     ESC escolher música", CINZA, centro=(LARGURA // 2, ALTURA - 40))

    # ---- telas de menu
    def desenhar_titulo(self):
        t = pygame.time.get_ticks()
        self.tela.blit(self.cenarios["palco"], (0, 0))
        fase = (t % 500) / 500
        visual.desenhar_personagem(self.tela, 200, 520, "diabinho", int(t / 500) % 4, fase, True, t)
        visual.desenhar_personagem(self.tela, 800, 520, "bf", (int(t / 500) + 2) % 4, fase, False, t)
        texto(self.tela, self.f_titulo, "FUNKIN' PYTHON", BRANCO, centro=(LARGURA // 2, 105))
        for i in range(4):
            visual.desenhar_seta(self.tela, LARGURA // 2 - 123 + i * 82, 195, i)
        self.desenhar_lista(["Jogar", "Multijogador", "Opções", "Sair"], self.idx_titulo, 290, 58)
        texto(self.tela, self.f_peq, "↑ ↓ navegar     ENTER escolher", CINZA, centro=(LARGURA // 2, ALTURA - 30))

    def desenhar_personagens(self):
        t = pygame.time.get_ticks()
        self.tela.blit(self.cenarios["palco"], (0, 0))
        visual.veu(self.tela, 150)
        texto(self.tela, self.f_grande, "ESCOLHA OS PERSONAGENS", BRANCO, centro=(LARGURA // 2, 52))
        fase = (t % 500) / 500
        dicas = ("A D escolher   S ok   W voltar",
                 "← → escolher   ↓ ok   ↑ voltar")
        for i, cx in enumerate((250, 750)):
            estilo = visual.ORDEM_PERSONAGENS[self.mp_idx[i]]
            pronto = self.mp_pronto[i]
            texto(self.tela, self.f_media, f"JOGADOR {i + 1}", COR_JOGADOR[i], centro=(cx, 125))
            pose = int(t / 400) % 4 if pronto else None
            visual.desenhar_personagem(self.tela, cx, 440, estilo, pose, fase, i == 0, t)
            if not pronto:
                bate = 6 * abs(math.sin(t / 250))
                for lado in (-1, 1):
                    x = cx + lado * (150 + bate)
                    D.polygon(self.tela, AMARELO, [(x - lado * 10, 290), (x + lado * 10, 270), (x + lado * 10, 310)])
            texto(self.tela, self.f_media, visual.NOMES_PERSONAGENS[estilo], BRANCO, centro=(cx, 490))
            if pronto:
                texto(self.tela, self.f_media, "PRONTO!", (120, 255, 160), centro=(cx, 540))
            else:
                texto(self.tela, self.f_peq, dicas[i], CINZA, centro=(cx, 545))
        rodape = "A partida começa quando os dois estiverem prontos     ESC voltar"
        texto(self.tela, self.f_peq, rodape, CINZA, centro=(LARGURA // 2, ALTURA - 24))

    def info_notas(self, m, dif):
        k = (m.id, dif)
        if k not in self.cache_info:
            if m.personalizada:
                notas, _ = analise.montar_chart(self.custom["analise"], dif, m.id)
            else:
                notas, _ = ritmo.gerar_chart(m.bpm, m.seed, dif, m.blocos)
            self.cache_info[k] = (sum(1 for n in notas if n.dono == "jogador"),
                                  sum(1 for n in notas if n.dono == "jogador" and n.duracao > 0),
                                  len(notas), sum(1 for n in notas if n.duracao > 0))
        return self.cache_info[k]

    def desenhar_selecao(self):
        t = pygame.time.get_ticks()
        cat = self.catalogo()
        m = cat[self.idx_musica]
        dif = ritmo.ORDEM_DIFICULDADES[self.idx_dif]
        vazio = m.personalizada and self.custom is None                # modo personalizado sem arquivo ainda
        self.tela.blit(self.cenarios[m.cenario], (0, 0))
        visual.veu(self.tela, 120)
        texto(self.tela, self.f_grande, "MULTIJOGADOR" if self.modo_mp else "ESCOLHA A MÚSICA",
              BRANCO, centro=(LARGURA // 2, 48))

        fase = (t % 500) / 500
        if self.modo_mp:
            visual.desenhar_personagem(self.tela, 125, 430, self.mp_estilos[0], int(t / 500) % 4, fase, True, t)
            visual.desenhar_personagem(self.tela, 875, 430, self.mp_estilos[1], (int(t / 500) + 2) % 4, fase, False, t)
        else:
            visual.desenhar_personagem(self.tela, 125, 430, m.oponente, int(t / 500) % 4, fase, True, t)
            visual.desenhar_personagem(self.tela, 875, 430, "bf", (int(t / 500) + 2) % 4, fase, False, t)

        card = D.Rect(284, 100, 432, 276)
        if vazio:
            D.rect(self.tela, (18, 18, 36), card, border_radius=6)
            texto(self.tela, self.f_grande, "SUA MÚSICA", BRANCO, centro=(LARGURA // 2, 185))
            texto(self.tela, self.f_peq, "Qualquer arquivo de áudio", (200, 220, 255), centro=(LARGURA // 2, 245))
            texto(self.tela, self.f_media, "ENTER: escolher arquivo", AMARELO, centro=(LARGURA // 2, 305))
            texto(self.tela, self.f_peq, "ou arraste-o para a janela", CINZA, centro=(LARGURA // 2, 345))
        else:
            self.tela.blit(self.miniaturas[m.cenario], card.topleft)
            if m.personalizada:                                        # faixa com o nome do arquivo
                faixa = D.Surface((432, 44), pygame.SRCALPHA)
                faixa.fill((0, 0, 0, 170))
                D.blit(self.tela, faixa, (284, 332))
                texto(self.tela, self.f_peq, m.nome, BRANCO, centro=(LARGURA // 2, 354), sombra=False)
        pygame.draw.rect(self.tela, BRANCO, card.inflate(D.px(8), D.px(8)), max(1, D.px(4)), border_radius=D.px(6))
        bate = 6 * abs(math.sin(t / 250))
        for lado, cx in ((-1, 252), (1, 748)):
            D.polygon(self.tela, AMARELO, [(cx - lado * (12 + bate), 238), (cx + lado * (6 - bate), 218), (cx + lado * (6 - bate), 258)])
        for i in range(len(cat)):
            D.circle(self.tela, AMARELO if i == self.idx_musica else CINZA, (LARGURA // 2 - 10 * (len(cat) - 1) + i * 20, 398), 6 if i == self.idx_musica else 4)

        texto(self.tela, self.f_media, "Modo personalizado" if m.personalizada else m.nome, BRANCO, centro=(LARGURA // 2, 428))
        if vazio:
            sub = "Escolha uma música do seu computador"
        elif m.personalizada:
            seg = int(self.custom["analise"].duracao_ms // 1000)
            sub = f"{m.bpm:.0f} BPM   •   {seg // 60}:{seg % 60:02d}   •   vs. {m.nome_oponente}" if not self.modo_mp \
                else f"{m.bpm:.0f} BPM   •   {seg // 60}:{seg % 60:02d}"
        elif self.modo_mp:
            sub = f"{m.subtitulo}   •   {m.bpm:.0f} BPM"
        else:
            sub = f"{m.subtitulo}   •   vs. {m.nome_oponente}   •   {m.bpm:.0f} BPM"
        texto(self.tela, self.f_peq, sub, (220, 220, 235), centro=(LARGURA // 2, 458))

        for i, d in enumerate(ritmo.ORDEM_DIFICULDADES):
            ret = D.rect_centro(LARGURA // 2 + (i - 1) * 170, 502, 150, 40)
            cor = CORES_DIFICULDADE[d]
            nome = ritmo.DIFICULDADES[d]["nome"]
            if i == self.idx_dif:
                D.rect(self.tela, cor, ret, border_radius=10)
                texto(self.tela, self.f_peq, nome, (20, 20, 30), centro=(LARGURA // 2 + (i - 1) * 170, 502), sombra=False)
            else:
                D.rect(self.tela, (20, 20, 35), ret, border_radius=10)
                D.rect(self.tela, cor, ret, 2, border_radius=10)
                texto(self.tela, self.f_peq, nome, cor, centro=(LARGURA // 2 + (i - 1) * 170, 502), sombra=False)

        if vazio:
            info = "Formatos: MP3, WAV, OGG, FLAC, M4A e outros"
        else:
            setas, longas, total, total_longas = self.info_notas(m, dif)
            vel = ritmo.DIFICULDADES[dif]["velocidade"] * self.cfg.vel_mult / 0.5
            if self.modo_mp:
                info = f"Setas por jogador: {total} ({total_longas} longas)     Velocidade: x{vel:.1f}"
            else:
                info = (f"Setas: {setas} ({longas} longas)     Velocidade: x{vel:.1f}     "
                        f"Recorde: {self.recordes.obter(m.id, dif)}")
        texto(self.tela, self.f_peq, info, BRANCO, centro=(LARGURA // 2, 546))
        if pygame.time.get_ticks() < self.aviso_ate:
            pass                                                   # o aviso ocupa o lugar das dicas
        elif vazio:
            texto(self.tela, self.f_peq, "ENTER: escolher o arquivo     (ou arraste-o para a janela)",
                  (130, 255, 190), centro=(LARGURA // 2, 578))
        elif m.personalizada:
            texto(self.tela, self.f_peq, "O: trocar de música     TAB: trocar cenário e oponente",
                  (130, 255, 190), centro=(LARGURA // 2, 578))
        elif self.modo_mp:
            n1, n2 = (visual.NOMES_PERSONAGENS[e] for e in self.mp_estilos)
            texto(self.tela, self.f_peq, f"J1 (esquerda): {n1}      J2 (direita): {n2}",
                  (130, 255, 190), centro=(LARGURA // 2, 578))
        elif self.pratica:
            modo = f"Modo: PRÁTICA - começar no bloco {self.pratica_bloco + 1}/{m.blocos}  (PgUp / PgDn)"
            texto(self.tela, self.f_peq, modo, (130, 255, 190), centro=(LARGURA // 2, 578))
        else:
            texto(self.tela, self.f_peq, "Modo: NORMAL     (TAB: modo prática)", CINZA, centro=(LARGURA // 2, 578))
        texto(self.tela, self.f_peq, "← → música     ↑ ↓ dificuldade     ENTER jogar     ESC voltar",
              CINZA, centro=(LARGURA // 2, ALTURA - 20))
        self.desenhar_aviso()

    def desenhar_analisando(self):
        info = self.analise_info
        self.tela.blit(self.cenarios["palco"], (0, 0))
        visual.veu(self.tela, 190)
        pontos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        texto(self.tela, self.f_grande, "ANALISANDO A MÚSICA", BRANCO, centro=(LARGURA // 2, 150))
        texto(self.tela, self.f_media, info["nome"], AMARELO, centro=(LARGURA // 2, 240))
        texto(self.tela, self.f_media, info["etapa"].rstrip(".") + pontos, BRANCO, centro=(LARGURA // 2, 300))
        D.rect(self.tela, (30, 30, 55), (250, 340, 500, 22), border_radius=8)
        D.rect(self.tela, (120, 255, 160), (250, 340, max(8, int(500 * info["prog"])), 22), border_radius=8)
        texto(self.tela, self.f_peq, "Procurando as batidas e criando as setas. Leva alguns segundos;",
              CINZA, centro=(LARGURA // 2, 410))
        texto(self.tela, self.f_peq, "músicas longas demoram um pouco mais.", CINZA, centro=(LARGURA // 2, 438))

    def desenhar_opcoes(self):
        self.tela.blit(self.cenarios["palco"], (0, 0))
        visual.veu(self.tela, 190)
        if self.op_pag is None:
            texto(self.tela, self.f_grande, "OPÇÕES", BRANCO, centro=(LARGURA // 2, 62))
            self.desenhar_lista([nome for nome, _ in OP_CATEGORIAS], self.op_cat, 160, 56)
            texto(self.tela, self.f_peq, "↑ ↓ navegar     ENTER escolher     ESC voltar", CINZA, centro=(LARGURA // 2, ALTURA - 24))
            self.desenhar_aviso()
            return

        texto(self.tela, self.f_grande, TITULOS_PAGINA[self.op_pag].upper(), BRANCO, centro=(LARGURA // 2, 58))
        ids = OP_PAGINAS[self.op_pag]

        def fundo_linha(i, y):
            if i == self.op_sel:
                s = D.Surface((720, 50), pygame.SRCALPHA)
                D.rect(s, (255, 255, 255, 35), pygame.Rect(0, 0, *s.get_size()), border_radius=10)
                D.blit(self.tela, s, (140, y - 25))

        if self.op_pag.startswith("controles"):
            jogador = int(self.op_pag[-1]) - 1
            tabela = self.cfg.tabela(jogador)
            texto(self.tela, self.f_peq, "Tecla 1", CINZA, centro=(600, 128), sombra=False)
            texto(self.tela, self.f_peq, "Tecla 2", CINZA, centro=(740, 128), sombra=False)
            for i in range(4):
                y = 175 + i * 58
                fundo_linha(i, y)
                texto(self.tela, self.f_media, f"{ICONES_LANE[i]}  {cfgmod.NOMES_LANES[i]}",
                      AMARELO if i == self.op_sel else BRANCO, topo_esq=(210, y - 20))
                for slot in range(2):
                    cx = 600 + slot * 140
                    caixa = D.rect_centro(cx, y, 118, 38)
                    D.rect(self.tela, (40, 40, 72), caixa, border_radius=8)
                    foco = i == self.op_sel and slot == self.op_slot
                    if foco and self.capturando:
                        borda, rotulo = AMARELO, "..."
                    else:
                        borda = BRANCO if foco else (110, 110, 140)
                        rotulo = nome_tecla(tabela[i][slot])
                    D.rect(self.tela, borda, caixa, 3 if foco else 2, border_radius=8)
                    texto(self.tela, self.f_peq, rotulo, BRANCO, centro=(cx, y), sombra=False)
            y_voltar = 175 + 4 * 58
            fundo_linha(4, y_voltar)
            texto(self.tela, self.f_media, "Voltar", AMARELO if self.op_sel == 4 else BRANCO, centro=(LARGURA // 2, y_voltar))
            dica = ("Pressione a nova tecla  (ESC cancela, BACKSPACE apaga)" if self.capturando else
                    "↑ ↓ navegar    ← → Tecla 1/2    ENTER mudar tecla    ESC voltar")
            texto(self.tela, self.f_peq, "Estas teclas também valem no modo de 1 jogador." if jogador == 0
                  else "O jogador 2 só é usado no modo multijogador.", (200, 220, 255),
                  centro=(LARGURA // 2, ALTURA - 62))
        else:
            for i, linha in enumerate(ids):
                y = 180 + i * 66
                fundo_linha(i, y)
                cor = AMARELO if i == self.op_sel else BRANCO
                if linha == "voltar":
                    texto(self.tela, self.f_media, "Voltar", cor, centro=(LARGURA // 2, y))
                    continue
                texto(self.tela, self.f_media, ROTULOS[linha], cor, topo_esq=(190, y - 20))
                valor = self.valor_opcao(linha)
                texto(self.tela, self.f_media, valor if linha == "calibrar" else f"◄ {valor} ►", cor, centro=(735, y))
            ajuda = AJUDAS.get(ids[self.op_sel], "")
            if ajuda:
                texto(self.tela, self.f_peq, ajuda, (200, 220, 255), centro=(LARGURA // 2, ALTURA - 62))
            dica = "↑ ↓ navegar     ← → alterar     ENTER confirmar     ESC voltar"
        texto(self.tela, self.f_peq, dica, CINZA, centro=(LARGURA // 2, ALTURA - 24))
        self.desenhar_aviso()

    def desenhar_calibracao(self):
        cal = self.cal
        self.tela.blit(self.cenarios["palco"], (0, 0))
        visual.veu(self.tela, 200)
        texto(self.tela, self.f_grande, "CALIBRAR ÁUDIO", BRANCO, centro=(LARGURA // 2, 50))
        texto(self.tela, self.f_peq, "Ouça o toc e aperte ESPAÇO (ou uma das suas teclas de jogo) junto com ele.",
              BRANCO, centro=(LARGURA // 2, 100))
        texto(self.tela, self.f_peq, "Guie-se pelo SOM, não pela imagem. Faça pelo menos 6 toques.",
              CINZA, centro=(LARGURA // 2, 128))

        intervalo = INTERVALO_METRONOMO_MS / 1000.0
        fase = ((time.perf_counter() - cal["inicio"]) % intervalo) / intervalo
        brilho = max(0.0, 1.0 - fase * 6)
        D.circle(self.tela, (30, 30, 60), (LARGURA // 2, 240), 80)
        D.circle(self.tela, tuple(int(90 + 165 * brilho) for _ in range(3)), (LARGURA // 2, 240), 46 + int(26 * brilho))

        bx, by, bw = 200, 400, 600
        D.rect(self.tela, (30, 30, 55), (bx - 10, by - 36, bw + 20, 90), border_radius=10)
        D.line(self.tela, (120, 120, 150), (bx, by), (bx + bw, by), 2)
        D.line(self.tela, BRANCO, (bx + bw // 2, by - 24), (bx + bw // 2, by + 24), 3)
        texto(self.tela, self.f_peq, "cedo", CINZA, centro=(bx + 20, by + 40), sombra=False)
        texto(self.tela, self.f_peq, "tarde", CINZA, centro=(bx + bw - 24, by + 40), sombra=False)
        for i, d in enumerate(cal["taps"]):
            x = bx + bw / 2 + max(-150, min(150, d)) / 150 * (bw / 2)
            D.circle(self.tela, CORES_RATING["GOOD"] if i == len(cal["taps"]) - 1 else (110, 180, 140), (x, by), 8)
        x = bx + bw / 2 + max(-150, min(150, cal["valor"])) / 150 * (bw / 2)
        D.polygon(self.tela, AMARELO, [(x, by - 8), (x - 9, by - 26), (x + 9, by - 26)])

        n = len(cal["taps"])
        status = (f"Toques: {n}   -   mediana medida: {cal['valor']:+.0f} ms" if n >= 6
                  else f"Toques: {n}/6   -   ajuste atual: {cal['valor']:+.0f} ms")
        texto(self.tela, self.f_media, status, AMARELO, centro=(LARGURA // 2, 490))
        texto(self.tela, self.f_peq, "ENTER salvar     ← → ajuste fino (±5 ms)     R recomeçar     ESC cancelar",
              CINZA, centro=(LARGURA // 2, ALTURA - 24))
        self.desenhar_aviso()

    def desenhar_carregando(self):
        self.tela.blit(self.cenarios[self.musica.cenario], (0, 0))
        visual.veu(self.tela, 170)
        pontos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        texto(self.tela, self.f_grande, self.musica.nome if not self.musica.personalizada else "SUA MÚSICA", BRANCO, centro=(LARGURA // 2, 230))
        texto(self.tela, self.f_media, f"Preparando a música{pontos}", AMARELO, centro=(LARGURA // 2, 310))
        texto(self.tela, self.f_peq, "(só demora na primeira vez de cada dificuldade)", CINZA, centro=(LARGURA // 2, 355))

    def desenhar_iniciando(self):
        self.tela.fill((0, 0, 0))
        pontos = "." * (1 + (pygame.time.get_ticks() // 400) % 3)
        texto(self.tela, self.f_media, f"Preparando a música do menu{pontos}", BRANCO, centro=(LARGURA // 2, ALTURA // 2))

    def desenhar(self):
        telas = {INICIANDO: self.desenhar_iniciando, INTRO: self.desenhar_intro,
                 TITULO: self.desenhar_titulo, PERSONAGENS: self.desenhar_personagens,
                 SELECAO: self.desenhar_selecao, OPCOES: self.desenhar_opcoes,
                 CALIBRACAO: self.desenhar_calibracao, CARREGANDO: self.desenhar_carregando,
                 ANALISANDO: self.desenhar_analisando}
        if self.estado in telas:
            telas[self.estado]()
        else:
            self.desenhar_jogo()
        self.desenhar_transicao()

    def desenhar_jogo(self):
        t = self.tempo()
        self.desenhar_cena(t)
        if self.estado == FIM:                             # resultados: só o cenário ao fundo
            self.desenhar_resultados()
            return
        self.desenhar_notas(t)
        self.desenhar_hud(t)
        self.desenhar_popups()
        nome_dif = ritmo.DIFICULDADES[self.dif]["nome"]
        if self.estado == JOGANDO:
            self.desenhar_contagem(self.tempo_rel())
        elif self.estado == PAUSA:
            self.desenhar_painel("PAUSADO", BRANCO, [
                (f"{self.musica.nome} - {nome_dif}", BRANCO),
                ("ESC / ENTER: continuar", BRANCO),
                ("R: reiniciar     Q: escolher música", BRANCO)])
        elif self.estado == DERROTA:
            self.desenhar_painel("VOCÊ PERDEU", (255, 90, 90), [
                (f"{self.musica.nome} - {nome_dif}", BRANCO),
                (f"Pontos: {self.placar.pontos}", BRANCO),
                ("R: tentar de novo     ESC: escolher música", BRANCO),
                ("Dica: treine um trecho no modo prática (TAB na seleção).", CINZA)])

    # ------------------------------------------------------------------------ laço ---
    def executar(self):
        ultimo = time.perf_counter()
        while True:
            agora = time.perf_counter()
            self.dt = min(0.05, agora - ultimo)
            ultimo = agora
            for ev in pygame.event.get():
                self.tratar_evento(ev)
            if self.estado == JOGANDO:
                self.atualizar()
            elif self.estado == CARREGANDO:
                self.checar_carga()
            elif self.estado == INICIANDO:
                self.checar_inicio()
            elif self.estado == ANALISANDO:
                self.checar_analise()
            self.atualizar_efeitos()
            self.atualizar_musica_menu()
            self.desenhar()
            pygame.display.flip()
            self.relogio.tick(self.cfg.fps)


def main():
    Jogo().executar()


if __name__ == "__main__":
    main()
