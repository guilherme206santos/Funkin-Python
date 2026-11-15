"""Testes de configurações, recordes, catálogo, efeitos, atlas e alfabeto (sem Pygame)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import alfabeto  # noqa: E402
import atlas  # noqa: E402
import config  # noqa: E402
import musicas  # noqa: E402
import ritmo  # noqa: E402

RAIZ = os.path.join(os.path.dirname(__file__), "..")


class TestTeclas(unittest.TestCase):
    def test_padroes_wasd_e_setas(self):
        c = config.Config()
        self.assertEqual([l[0] for l in c.teclas], ["a", "s", "w", "d"])
        self.assertEqual([l[0] for l in c.teclas2], ["left", "down", "up", "right"])
        self.assertEqual(c.mapa_teclas(0)["w"], 2)
        self.assertEqual(c.mapa_teclas(1)["right"], 3)
        self.assertNotIn("", c.mapa_teclas(0))

    def test_troca_entre_jogadores(self):
        c = config.Config()
        # 'd' (J1, direita) vai para J1 esquerda: as duas posições trocam de tecla
        self.assertTrue(c.definir_tecla(0, 0, "d", jogador=0))
        self.assertEqual(c.teclas[0][0], "d")
        self.assertEqual(c.teclas[3][0], "a")
        # tecla do jogador 2 em uma posição do jogador 1: também troca
        self.assertTrue(c.definir_tecla(1, 0, "right", jogador=0))
        self.assertEqual(c.teclas2[3][0], "s")

    def test_recusa_deixar_seta_sem_tecla(self):
        c = config.Config()
        # 'left' (única tecla da seta esquerda do J2) para a 2ª tecla do J1: o J2 ficaria sem tecla
        antes = (c.teclas, c.teclas2)
        import copy
        antes = copy.deepcopy(antes)
        self.assertFalse(c.definir_tecla(0, 1, "left", jogador=0))
        self.assertEqual((c.teclas, c.teclas2), antes)
        self.assertFalse(c.limpar_tecla(0, 0, jogador=0))          # única tecla da seta
        self.assertTrue(c.definir_tecla(0, 1, "q"))
        self.assertTrue(c.limpar_tecla(0, 1))
        self.assertEqual(c.teclas[0][1], "")

    def test_sem_teclas_repetidas(self):
        c = config.Config()
        for _ in range(20):
            c.definir_tecla(_ % 4, _ % 2, "abcd"[_ % 4], jogador=_ % 2)
            todas = [k for t in (c.teclas, c.teclas2) for l in t for k in l if k]
            self.assertEqual(len(todas), len(set(todas)))


class TestConfigArquivo(unittest.TestCase):
    def test_salvar_carregar_tudo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "c.json")
            c = config.Config(caminho)
            c.alternar("ghost_tapping")
            c.alternar("efeitos_camera")
            c.alternar("downscroll")
            c.ajustar("vel_mult", 3)
            c.ajustar("vol_efeitos", -3)
            c.ajustar("resolucao", 2)
            c.definir_ajuste(35)
            c.definir_tecla(0, 1, "q", jogador=1)
            c.salvar()
            lido = config.Config.carregar(caminho)
        self.assertEqual(lido.para_dict(), c.para_dict())
        self.assertEqual(lido.resolucao, "media")

    def test_config_antiga_volta_as_teclas_novas(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "c.json")
            with open(caminho, "w") as f:      # formato antigo: D F J K + setas, sem versão
                json.dump({"teclas": [["d", "left"], ["f", "down"], ["j", "up"], ["k", "right"]],
                           "fps": 120}, f)
            c = config.Config.carregar(caminho)
        self.assertEqual(c.teclas, config.PADRAO["teclas"])
        self.assertEqual(c.fps, 120)

    def test_valores_invalidos_sao_ignorados(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "c.json")
            with open(caminho, "w") as f:
                json.dump({"versao": config.VERSAO, "vel_mult": 7.3, "vol_musica": 55, "downscroll": 1,
                           "ajuste_ms": "oi", "resolucao": "gigante",
                           "teclas": [["a", ""]] * 4, "teclas2": config.PADRAO["teclas2"]}, f)
            c = config.Config.carregar(caminho)
        self.assertEqual((c.vel_mult, c.vol_musica, c.downscroll, c.ajuste_ms, c.resolucao),
                         (1.0, 100, False, 0, "auto"))
        self.assertEqual(c.teclas, config.PADRAO["teclas"])         # 'a' repetida => descarta

    def test_restaurar_mantem_calibracao(self):
        c = config.Config()
        c.definir_ajuste(40)
        c.alternar("downscroll")
        c.definir_tecla(0, 1, "q")
        c.restaurar()
        self.assertFalse(c.downscroll)
        self.assertEqual(c.teclas, config.PADRAO["teclas"])
        self.assertEqual(c.ajuste_ms, 40)

    def test_listas_e_limites(self):
        c = config.Config()
        for _ in range(30):
            c.ajustar("vel_mult", 1)
        self.assertEqual(c.vel_mult, config.VEL_OPCOES[-1])
        for _ in range(30):
            c.ajustar("vol_musica", -1)
        self.assertEqual(c.vol_musica, 0)
        c.fps = config.FPS_OPCOES[-1]
        c.mudar_fps(1)
        self.assertEqual(c.fps, config.FPS_OPCOES[0])
        c.definir_ajuste(9999)
        self.assertEqual(c.ajuste_ms, config.AJUSTE_MAX)
        self.assertEqual(set(config.RESOLUCOES), set(config.ESCALA_RESOLUCAO))


class TestPersonalizada(unittest.TestCase):
    def test_lembra_o_ultimo_arquivo(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "c.json")
            c = config.Config(caminho)
            c.personalizada = "C:/musicas/minha.mp3"
            c.salvar()
            self.assertEqual(config.Config.carregar(caminho).personalizada, "C:/musicas/minha.mp3")
            c.restaurar()                                      # restaurar padrões não esquece a música
            self.assertEqual(c.personalizada, "C:/musicas/minha.mp3")
            with open(caminho, "w") as f:
                json.dump({"versao": config.VERSAO, "personalizada": 123}, f)
            self.assertEqual(config.Config.carregar(caminho).personalizada, "")


class TestRecordes(unittest.TestCase):
    def test_registrar(self):
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "r.json")
            r = config.Recordes(caminho)
            self.assertTrue(r.registrar("neon", "facil", 1000))
            self.assertFalse(r.registrar("neon", "facil", 900))
            self.assertEqual(config.Recordes(caminho).obter("neon", "facil"), 1000)
            self.assertEqual(r.obter("neon", "dificil"), 0)     # separado por dificuldade


class TestMusicas(unittest.TestCase):
    def test_catalogo(self):
        self.assertGreaterEqual(len(musicas.MUSICAS), 4)
        ids = [m.id for m in musicas.MUSICAS]
        self.assertEqual(len(ids), len(set(ids)))
        for m in musicas.MUSICAS:
            self.assertEqual(len(m.raizes), 4)
            self.assertEqual(len(m.escala), 4)
            for d in ritmo.ORDEM_DIFICULDADES:
                notas, dur = ritmo.gerar_chart(m.bpm, m.seed, d, m.blocos)
                self.assertGreater(sum(n.dono == "jogador" for n in notas), 20)
                self.assertLess(notas[-1].tempo, dur)


class TestEfeitos(unittest.TestCase):
    def test_todos_os_efeitos_geram_audio(self):
        import efeitos
        for nome in efeitos.EFEITOS:
            dados = efeitos.gerar(nome)
            self.assertGreater(len(dados), 500)
            self.assertEqual(len(dados) % 2, 0)             # 16 bits
            self.assertTrue(0 < efeitos.volume_base(nome) <= 1)

    def test_metronomo_tem_tamanho_exato(self):
        import efeitos
        dados = efeitos.metronomo(600, 8)
        self.assertEqual(len(dados) // 2, int(efeitos.SR * 0.6) * 8)


class TestAtlasEAlfabeto(unittest.TestCase):
    PASTA = os.path.join(RAIZ, "assets", "imgs", "fnf")

    def test_quadros_das_setas_existem(self):
        notas = atlas.ler_quadros(os.path.join(self.PASTA, "notes.xml"))
        strum = atlas.ler_quadros(os.path.join(self.PASTA, "noteStrumline.xml"))
        for d in ("Left", "Down", "Up", "Right"):
            self.assertIn(f"note{d}0001", notas)
            self.assertIn(f"static{d}0001", strum)
            self.assertIn(f"press{d}0003", strum)
            for i in (1, 2, 3, 4):
                self.assertIn(f"confirm{d}000{i}", strum)
        x, y, w, h, fx, fy, fw, fh = strum["staticDown0001"]
        self.assertGreater(fw, w)               # o recorte tem margem (frameX/frameWidth)
        self.assertTrue(os.path.exists(os.path.join(self.PASTA, "NOTE_hold_assets.png")))

    def test_todo_glifo_usado_existe_na_folha(self):
        quadros = atlas.ler_quadros(os.path.join(self.PASTA, "fonte_bold.xml"))
        textos = ["FUNKIN' PYTHON", "Escolha os personagens", "MÚSICA COMPLETA!", "OPÇÕES", "VÍDEO",
                  "ÁUDIO", "Você perdeu", "Pausado", "Vai!", "Pronto?", "Trabalho de Programação",
                  "Universidade Federal de Sergipe", "UFS"]
        textos += [m.nome for m in musicas.MUSICAS]
        for t in textos:
            self.assertTrue(alfabeto.suporta(t), t)
            for ch in t:
                nome, _ = alfabeto.decompor(ch)
                if nome != "espaco":
                    self.assertIn(nome + "0000", quadros, (t, ch, nome))

    def test_icone_do_jogo(self):
        self.assertTrue(os.path.exists(os.path.join(self.PASTA, "..", "icone.png")))
        ico = os.path.join(self.PASTA, "..", "icone.ico")
        self.assertTrue(os.path.exists(ico))
        with open(ico, "rb") as f:
            cab = f.read(6)
        self.assertEqual(cab[:4], b"\x00\x00\x01\x00")                     # assinatura de um arquivo .ico
        self.assertGreaterEqual(int.from_bytes(cab[4:6], "little"), 4)       # vários tamanhos

    def test_decompor(self):
        self.assertEqual(alfabeto.decompor("ã"), ("A", "til"))
        self.assertEqual(alfabeto.decompor("Ç"), ("C", "cedilha"))
        self.assertEqual(alfabeto.decompor("a"), ("A", None))
        self.assertIsNone(alfabeto.decompor("7"))                # números não existem na folha
        self.assertFalse(alfabeto.suporta("Fase 2"))


if __name__ == "__main__":
    unittest.main()
