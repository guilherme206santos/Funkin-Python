"""Testes da análise de ritmo (modo personalizado). Precisam de numpy; sem ele, são ignorados."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

try:
    import numpy as np
    import analise
    import audio
except ImportError:                                             # pragma: no cover
    np = None

import musicas  # noqa: E402
import ritmo  # noqa: E402

SR = 22050


def musica_sintetica(bpm=120.0, dur=40.0, sustentadas=False, seed=1):
    """Bumbo nas batidas ímpares, caixa nas pares, chimbal em colcheias (e notas longas opcionais)."""
    rng = np.random.default_rng(seed)
    n = int(SR * dur)
    x = np.zeros(n, np.float32)
    batida = 60.0 / bpm
    reais = []

    def somar(t, sinal):
        i = int(t * SR)
        if 0 <= i and i + len(sinal) < n:
            x[i:i + len(sinal)] += sinal

    tt = np.arange(int(0.2 * SR)) / SR
    bumbo = (np.sin(2 * np.pi * (50 + 100 * np.exp(-tt * 30)) * tt) * np.exp(-tt * 15) * 0.8).astype(np.float32)
    tt2 = np.arange(int(0.15 * SR)) / SR
    for b in range(int(dur / batida) - 4):
        t = b * batida
        if b % 2 == 0:
            somar(t, bumbo)
        else:
            somar(t, (rng.standard_normal(len(tt2)) * np.exp(-tt2 * 28) * 0.4).astype(np.float32))
        reais.append(t * 1000)
        if sustentadas and b % 8 == 0 and b >= 8:
            d = 2 * batida
            t3 = np.arange(int(d * SR)) / SR
            env = np.minimum(1, t3 / 0.005) * np.minimum(1, (d - t3) / 0.05)
            somar(t, (np.sin(2 * np.pi * 440 * t3) * env * 0.5).astype(np.float32))
    return x, reais


@unittest.skipIf(np is None, "numpy não instalado")
class TestAnalise(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.x, cls.reais = musica_sintetica()
        cls.an = analise.analisar(cls.x)

    def test_andamento_e_metodo(self):
        self.assertAlmostEqual(self.an.bpm, 120.0, delta=1.0)
        self.assertEqual(self.an.metodo, "batidas")
        self.assertGreater(self.an.regularidade, 0.5)
        self.assertGreater(len(self.an.batidas_ms), 60)

    def test_ataques_no_tempo_certo(self):
        det = np.array([c[0] for c in self.an.candidatos])
        erros = [min(abs(det - r)) for r in self.reais[2:-2]]
        self.assertLess(float(np.median(erros)), 12.0)           # ms
        self.assertGreater(sum(e < 30 for e in erros) / len(erros), 0.9)

    def test_dificuldades(self):
        n = {d: analise.montar_chart(self.an, d)[0] for d in ritmo.ORDEM_DIFICULDADES}
        self.assertLess(len(n["facil"]), len(n["medio"]))
        self.assertLess(len(n["medio"]), len(n["dificil"]))
        for d, notas in n.items():
            self.assertTrue(all(isinstance(x, ritmo.Nota) and x.dono == "jogador" for x in notas))
            self.assertTrue(all(0 <= x.lane < 4 for x in notas))
            self.assertEqual([x.tempo for x in notas], sorted(x.tempo for x in notas))
            gap = analise.PARAMETROS[d]["gap"]
            simples = sorted({x.tempo for x in notas})
            self.assertTrue(all(b - a >= gap - 1 for a, b in zip(simples, simples[1:])))
            self.assertGreaterEqual(len({x.lane for x in notas}), 3)       # usa várias lanes

    def test_deterministico(self):
        a = analise.montar_chart(self.an, "dificil", "x")[0]
        b = analise.montar_chart(self.an, "dificil", "x")[0]
        self.assertEqual([(n.tempo, n.lane, n.duracao) for n in a], [(n.tempo, n.lane, n.duracao) for n in b])

    def test_notas_longas_nao_se_sobrepoem(self):
        x, _ = musica_sintetica(110, 60, sustentadas=True)
        an = analise.analisar(x)
        total = 0
        for d in ritmo.ORDEM_DIFICULDADES:
            notas, dur = analise.montar_chart(an, d)
            longas = [n for n in notas if n.duracao > 0]
            total += len(longas)
            for h in longas:
                self.assertLess(h.tempo + h.duracao, dur)
                for o in notas:
                    if o is not h and h.tempo < o.tempo < h.tempo + h.duracao:
                        self.assertNotEqual(o.lane, h.lane)
                        if d != "dificil":
                            self.fail("nota dentro de uma nota longa no " + d)
        self.assertGreater(total, 5)

    def test_sinais_sem_musica(self):
        with self.assertRaises(analise.ErroAnalise):
            analise.analisar(np.zeros(SR * 20, np.float32))             # silêncio
        with self.assertRaises(analise.ErroAnalise):
            analise.analisar(self.x[:SR * 2])                           # curta demais
        tom = (0.3 * np.sin(2 * np.pi * 220 * np.arange(SR * 30) / SR)).astype(np.float32)
        with self.assertRaises(analise.ErroAnalise):
            analise.analisar(tom)                                       # tom contínuo
        ruido = (0.3 * np.random.default_rng(2).standard_normal(SR * 30)).astype(np.float32)
        with self.assertRaises(analise.ErroAnalise):
            analise.analisar(ruido)

    def test_andamento_que_acelera(self):
        x, _ = musica_sintetica(120, 60)
        n = len(x)
        vel = np.linspace(1.0, 1.08, n)
        pos = np.cumsum(vel)
        pos = pos / pos[-1] * (n - 1)
        an = analise.analisar(np.interp(pos, np.arange(n), x).astype(np.float32))
        ini = np.median(np.diff(an.batidas_ms[:12]))
        fim = np.median(np.diff(an.batidas_ms[-12:]))
        self.assertLess(fim, ini * 0.97)                                # as batidas acompanham a aceleração

    def test_cache_e_hash(self):
        with tempfile.TemporaryDirectory() as pasta:
            analise.salvar_cache(pasta, "abc", self.an)
            lida = analise.carregar_cache(pasta, "abc")
            self.assertEqual(lida.bpm, self.an.bpm)
            self.assertEqual(len(lida.candidatos), len(self.an.candidatos))
            self.assertIsNone(analise.carregar_cache(pasta, "nao_existe"))
            a, b = os.path.join(pasta, "a.bin"), os.path.join(pasta, "b.bin")
            for caminho, conteudo in ((a, b"1234" * 1000), (b, b"1235" * 1000)):
                with open(caminho, "wb") as f:
                    f.write(conteudo)
            self.assertEqual(analise.hash_arquivo(a), analise.hash_arquivo(a))
            self.assertNotEqual(analise.hash_arquivo(a), analise.hash_arquivo(b))

    def test_nivel_na_grade(self):
        batidas = [i * 500.0 for i in range(10)]
        self.assertEqual(analise.nivel_na_grade(1000.0, batidas), (1000.0, 0))
        self.assertEqual(analise.nivel_na_grade(1250.0, batidas)[1], 1)          # colcheia
        self.assertEqual(analise.nivel_na_grade(1125.0, batidas)[1], 2)          # semicolcheia
        self.assertEqual(analise.nivel_na_grade(1010.0, batidas), (1000.0, 0))   # "cola" na grade
        self.assertEqual(analise.nivel_na_grade(1075.0, batidas)[1], 3)          # fora da grade


@unittest.skipIf(np is None, "numpy não instalado")
class TestAudioEModelo(unittest.TestCase):
    def test_buffer_para_mixer(self):
        mono = np.arange(1000, dtype=np.int16).tobytes()
        self.assertEqual(len(audio.buffer_para_mixer(mono, 22050, 1)), 2000)
        est = audio.buffer_para_mixer(mono, 44100, 2)
        self.assertEqual(len(est), 1000 * 2 * 2 * 2)                              # 2x amostras, 2 canais, 2 bytes
        v = np.frombuffer(est, dtype=np.int16).reshape(-1, 2)
        self.assertTrue((v[:, 0] == v[:, 1]).all())
        flt = audio.buffer_para_mixer(mono, 44100, 2, 32)
        self.assertEqual(len(flt), 1000 * 2 * 2 * 4)

    def test_reamostrar(self):
        x = np.ones(44100, np.float32)
        self.assertEqual(len(audio.reamostrar(x, 44100, 22050)), 22050)
        self.assertEqual(len(audio.reamostrar(np.ones(48000, np.float32), 48000, 22050)), 22050)
        self.assertIs(audio.reamostrar(x, 22050, 22050), x)

    def test_extensoes_comuns(self):
        for ext in (".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac", ".wma", ".opus"):
            self.assertIn(ext, audio.EXTENSOES)

    def test_modelo_personalizada(self):
        vazio = musicas.modelo_personalizada()
        self.assertTrue(vazio.personalizada)
        m = musicas.criar_personalizada("Minha música", 128.0, "abcdef0123456789", "/x/y.mp3", visual=1)
        self.assertEqual((m.id, m.nome, m.bpm, m.arquivo), ("custom-abcdef01", "Minha música", 128.0, "/x/y.mp3"))
        self.assertEqual(m.cenario, musicas.MUSICAS[1].cenario)
        self.assertEqual(musicas.criar_personalizada("a", 100, "00", "x", visual=len(musicas.MUSICAS)).cenario,
                         musicas.MUSICAS[0].cenario)                              # o índice dá a volta


if __name__ == "__main__":
    unittest.main()
