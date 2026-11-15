"""Testes da lógica pura (sem Pygame). Execute:  python -m unittest discover tests"""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
import ritmo  # noqa: E402


class TestJulgamento(unittest.TestCase):
    def test_janelas(self):
        self.assertEqual(ritmo.julgar(0), "SICK")
        self.assertEqual(ritmo.julgar(-44), "SICK")
        self.assertEqual(ritmo.julgar(80), "GOOD")
        self.assertEqual(ritmo.julgar(-120), "BAD")
        self.assertEqual(ritmo.julgar(159), "SHIT")
        self.assertIsNone(ritmo.julgar(161))

    def test_escolher_nota_mais_proxima(self):
        notas = [ritmo.Nota(1000, 0, "jogador"), ritmo.Nota(1100, 0, "jogador")]
        self.assertIs(ritmo.escolher_nota(notas, 0, 1090), notas[1])
        self.assertIsNone(ritmo.escolher_nota(notas, 1, 1000))      # outra lane
        self.assertIsNone(ritmo.escolher_nota(notas, 0, 5000))      # longe demais

    def test_ignora_notas_do_oponente(self):
        notas = [ritmo.Nota(1000, 2, "oponente")]
        self.assertIsNone(ritmo.escolher_nota(notas, 2, 1000))

    def test_varrer_perdidas(self):
        notas = [ritmo.Nota(1000, 0, "jogador"), ritmo.Nota(3000, 1, "jogador")]
        self.assertEqual(ritmo.varrer_perdidas(notas, 1100), [])
        perdidas = ritmo.varrer_perdidas(notas, 1000 + ritmo.JANELA_MAX + 1)
        self.assertEqual(len(perdidas), 1)
        self.assertEqual(ritmo.varrer_perdidas(notas, 1500), [])    # não repete

    def test_varrer_oponente(self):
        notas = [ritmo.Nota(500, 0, "oponente"), ritmo.Nota(500, 1, "jogador")]
        tocadas = ritmo.varrer_oponente(notas, 500)
        self.assertEqual(len(tocadas), 1)
        self.assertFalse(notas[1].acertada)


class TestPlacar(unittest.TestCase):
    def test_combo_e_pontos(self):
        p = ritmo.Placar()
        p.acertar("SICK")
        p.acertar("GOOD")
        self.assertEqual(p.combo, 2)
        self.assertEqual(p.pontos, 350 + 200)
        p.errar()
        self.assertEqual(p.combo, 0)
        self.assertEqual(p.combo_max, 2)

    def test_derrota(self):
        p = ritmo.Placar()
        for _ in range(10):
            p.errar()
        self.assertTrue(p.derrota)
        self.assertEqual(p.vida, 0.0)

    def test_rank(self):
        p = ritmo.Placar()
        for _ in range(20):
            p.acertar("SICK")
        self.assertEqual(p.rank, "S")
        p.errar(); p.errar(); p.errar(); p.errar(); p.errar()
        self.assertIn(p.rank, "ABC")


class TestDificuldades(unittest.TestCase):
    def test_mais_setas_e_mais_velocidade(self):
        qtd = {d: len(ritmo.gerar_chart(120, 7, d)[0]) for d in ritmo.ORDEM_DIFICULDADES}
        self.assertLess(qtd["facil"], qtd["medio"])
        self.assertLess(qtd["medio"], qtd["dificil"])
        vel = [ritmo.DIFICULDADES[d]["velocidade"] for d in ritmo.ORDEM_DIFICULDADES]
        self.assertEqual(vel, sorted(vel))
        self.assertEqual(len(set(vel)), 3)

    def test_notas_ficam_na_grade_do_ritmo(self):
        for bpm in (100, 120, 160):
            passo = ritmo.ms_por_batida(bpm) / 4
            for d in ritmo.ORDEM_DIFICULDADES:
                for n in ritmo.gerar_chart(bpm, 5, d)[0]:
                    self.assertAlmostEqual(n.tempo / passo, round(n.tempo / passo), places=6)

    def test_facil_so_nas_batidas(self):
        batida = ritmo.ms_por_batida(140)
        for n in ritmo.gerar_chart(140, 3, "facil")[0]:
            self.assertAlmostEqual(n.tempo / batida, round(n.tempo / batida), places=6)

    def test_sem_duplas_no_facil_e_medio(self):
        for d in ("facil", "medio"):
            tempos = [n.tempo for n in ritmo.gerar_chart(120, 7, d)[0]]
            self.assertEqual(len(tempos), len(set(tempos)))

    def test_duracao_depende_do_bpm(self):
        self.assertGreater(ritmo.gerar_chart(100)[1], ritmo.gerar_chart(160)[1])


class TestSustain(unittest.TestCase):
    def test_existem_notas_longas_sem_sobrepor_a_mesma_lane(self):
        for d in ritmo.ORDEM_DIFICULDADES:
            notas, _ = ritmo.gerar_chart(140, 21, d)
            longas = [n for n in notas if n.duracao > 0]
            self.assertGreater(len(longas), 3)
            for h in longas:
                for o in notas:
                    if o is not h and o.dono == h.dono and o.lane == h.lane:
                        self.assertFalse(h.tempo < o.tempo < h.tempo + h.duracao)
                if not ritmo.DIFICULDADES[d]["sustain_livre"]:
                    for o in notas:
                        if o is not h and o.dono == h.dono:
                            self.assertFalse(h.tempo < o.tempo < h.tempo + h.duracao)

    def test_completar_segurando_ate_o_fim(self):
        n = ritmo.Nota(1000, 0, "jogador", duracao=1000, acertada=True, segurando=True)
        p = ritmo.Placar()
        ev = ritmo.atualizar_sustains([n], 1500, [True, False, False, False], p, 16)
        self.assertEqual(ev, [])
        self.assertGreater(p.pontos, 0)
        ev = ritmo.atualizar_sustains([n], 1950, [True, False, False, False], p, 16)
        self.assertEqual(ev[0][0], "completo")
        self.assertEqual(p.sustains_ok, 1)
        self.assertFalse(n.segurando)

    def test_soltar_cedo_quebra(self):
        n = ritmo.Nota(1000, 2, "jogador", duracao=1000, acertada=True, segurando=True)
        p = ritmo.Placar()
        p.combo = 5
        ev = ritmo.atualizar_sustains([n], 1300, [False] * 4, p, 16)
        self.assertEqual(ev[0][0], "quebrado")
        self.assertEqual(p.combo, 0)
        self.assertEqual(p.sustains_quebrados, 1)

    def test_soltar_na_tolerancia_conta_como_completo(self):
        n = ritmo.Nota(1000, 1, "jogador", duracao=500, acertada=True, segurando=True)
        p = ritmo.Placar()
        ev = ritmo.atualizar_sustains([n], 1000 + 500 - ritmo.TOLERANCIA_SUSTAIN + 1, [False] * 4, p, 16)
        self.assertEqual(ev[0][0], "completo")

    def test_chart_antigo_e_detectado(self):
        import json
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as pasta:
            antigo = os.path.join(pasta, "a.json")
            with open(antigo, "w") as f:
                json.dump({"bpm": 120, "duracao_ms": 1, "notas": []}, f)
            self.assertFalse(ritmo.chart_atual(antigo))
            novo = os.path.join(pasta, "b.json")
            notas, dur = ritmo.gerar_chart()
            ritmo.salvar_chart(novo, notas, dur)
            self.assertTrue(ritmo.chart_atual(novo))
            lidas, _ = ritmo.carregar_chart(novo)
            self.assertEqual([n.duracao for n in lidas], [n.duracao for n in notas])


class TestResultados(unittest.TestCase):
    def test_histograma(self):
        cont, media = ritmo.histograma([-150, -10, -5, 5, 10, 200, -300])
        self.assertEqual(sum(cont), 7)
        self.assertEqual(len(cont), 16)
        self.assertEqual(cont[0], 2)       # -300 é limitado à primeira faixa
        self.assertEqual(cont[-1], 1)      # 200 vai para a última
        self.assertEqual(ritmo.histograma([])[1], 0.0)
        self.assertAlmostEqual(media, sum([-150, -10, -5, 5, 10, 200, -300]) / 7)

    def test_placar_guarda_desvios(self):
        p = ritmo.Placar()
        p.acertar("SICK", -12.5)
        p.acertar("GOOD", 30)
        self.assertEqual(p.desvios, [-12.5, 30])

    def test_inicio_de_bloco(self):
        self.assertEqual(ritmo.inicio_bloco_ms(0, 120), ritmo.COMPASSOS_INTRO * 2000)
        self.assertEqual(ritmo.inicio_bloco_ms(1, 120), (ritmo.COMPASSOS_INTRO + 4) * 2000)


class TestChart(unittest.TestCase):
    def test_deterministico_e_ordenado(self):
        a, da = ritmo.gerar_chart(seed=3)
        b, db = ritmo.gerar_chart(seed=3)
        self.assertEqual([(n.tempo, n.lane, n.dono) for n in a],
                         [(n.tempo, n.lane, n.dono) for n in b])
        self.assertEqual(da, db)
        self.assertEqual([n.tempo for n in a], sorted(n.tempo for n in a))

    def test_notas_validas(self):
        notas, dur = ritmo.gerar_chart()
        inicio = ritmo.COMPASSOS_INTRO * 4 * ritmo.ms_por_batida()
        for n in notas:
            self.assertIn(n.lane, range(ritmo.LANES))
            self.assertIn(n.dono, ("oponente", "jogador"))
            self.assertGreaterEqual(n.tempo, inicio)
            self.assertLess(n.tempo, dur)
        self.assertGreater(sum(n.dono == "jogador" for n in notas), 30)

    def test_salvar_e_carregar(self):
        notas, dur = ritmo.gerar_chart()
        with tempfile.TemporaryDirectory() as pasta:
            caminho = os.path.join(pasta, "c.json")
            ritmo.salvar_chart(caminho, notas, dur)
            lidas, dur2 = ritmo.carregar_chart(caminho)
        self.assertEqual(len(lidas), len(notas))
        self.assertEqual(dur, dur2)


if __name__ == "__main__":
    unittest.main()
