"""O desenho consulta o motor sem executar nem reescrever seu histórico."""
import unittest

from matplotlib.figure import Figure
from matplotlib.colors import to_rgba

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB


def retrato(sim):
    return repr([(s.tick, s.eventos, [vars(t) for t in s.tarefas],
                  [vars(c) for c in s.cpus]) for s in sim.historico])


def blocos(ax, tipo):
    return [c for c in ax.collections if (c.get_gid() or '').startswith(tipo + '-')]


def intervalos(bloco):
    return [(float(p.vertices[:, 0].min()), float(p.vertices[:, 0].max()))
            for p in bloco.get_paths()]


class TesteGantt(unittest.TestCase):
    def test_prefixo_real_cpus_cores_e_figure_reutilizada(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [
            TCB(2, 'FF0000', 0, 4, 10, 5),
            TCB(10, '00FF00', 0, 1, 20, 5)], [Cpu(4), Cpu(7)], 0), 'RM')
        sim.avancar(4)
        sim.retroceder(2)
        antes = retrato(sim)
        figura = Figure()
        ax = desenhar_gantt(sim, figura)
        execucoes = blocos(ax, 'execucao')
        self.assertEqual(sum(b-a for bloco in execucoes for a, b in intervalos(bloco)), 3)
        desenhados = []
        for bloco in execucoes:
            identidade = bloco.get_label().split(',')
            tarefa = int(identidade[0].rsplit(' ', 1)[1])
            cpu = int(identidade[1].rsplit(' ', 1)[1])
            for a, b in intervalos(bloco):
                desenhados.extend((tarefa, cpu, tick) for tick in range(int(a), int(b)))
        self.assertCountEqual(desenhados, [
            (e['id_tarefa'], e['id_cpu'], e['tick'])
            for s in sim.historico[1:3] for e in s.eventos if e['tipo'] == 'execucao'])
        self.assertEqual({b.get_label().split('CPU ')[1].split(',')[0]
                          for b in execucoes}, {'4', '7'})
        self.assertEqual(ax.get_xlim(), (-.04, 2.04))
        self.assertEqual([t.get_text() for t in ax.get_yticklabels()][:2], ['Tarefa 10', 'Tarefa 2'])
        self.assertTrue(blocos(ax, 'cpu_desligada'))
        self.assertEqual({tuple(b.get_facecolors()[0]) for b in execucoes},
                         {to_rgba('#FF0000'), to_rgba('#00FF00')})
        quantidade = len(ax.collections)
        novo_ax = desenhar_gantt(sim, figura)
        self.assertIs(novo_ax.figure, figura)
        self.assertEqual(len(figura.axes), 1)
        self.assertEqual(len(novo_ax.collections), quantidade)
        self.assertEqual(retrato(sim), antes)
        self.assertEqual(sim.instante_atual, 2)
        self.assertEqual(len(sim.historico), 5)

    def test_eventos_timestamps_suspensao_e_edicao_preservam_passado(self):
        from gantt import desenhar_gantt
        id_ = 'ação <x>&'
        sim = Simulacao(EstadoSimulacao(0, [
            TCB(id_, '112233', 0, 4, 20, 1),
            TCB(3, '336699', 0, 1, 30, 1),
            TCB(4, '669933', 0, 1, 30, 1)], [Cpu(0), Cpu(1)], 1), 'RM')
        sim.historico[0].tarefas[0].estado_tarefa = EstadoTarefa.SUSPENSA
        sim.avancar()
        sim.modificar_tarefa_em_execucao(id_, estado_tarefa=EstadoTarefa.PRONTA)
        sim.avancar()
        sim.modificar_tarefa_em_execucao(id_, cor='ABCDEF')
        sim.avancar(4)
        antes = retrato(sim)
        ax = desenhar_gantt(sim, Figure())
        suspensos = blocos(ax, 'suspensa')
        self.assertEqual([i for bloco in suspensos for i in intervalos(bloco)], [(0, 1)])
        self.assertTrue(suspensos[0].get_hatch())
        execucoes = [b for b in blocos(ax, 'execucao') if id_ in b.get_label()]
        self.assertEqual(tuple(execucoes[0].get_facecolors()[0]), to_rgba('#112233'))
        self.assertEqual(tuple(execucoes[-1].get_facecolors()[0]), to_rgba('#ABCDEF'))
        esperados = [(e['tipo'], e['tick']) for s in sim.historico[1:] for e in s.eventos
                     if e['tipo'] not in ('execucao', 'cpu_desligada')
                     for _ in (e['selecionadas'] if e['tipo'] == 'sorteio' else [e['id_tarefa']])]
        eventos = blocos(ax, 'evento')
        self.assertCountEqual([(e.get_gid().split('-')[1], ponto[0])
                               for e in eventos for ponto in e.get_offsets()], esperados)
        self.assertEqual({e.get_gid().split('-')[1] for e in eventos},
                         {'chegada', 'ativacao', 'conclusao', 'perda_prazo', 'sorteio', 'fim_quantum'})
        self.assertEqual(retrato(sim), antes)

    def test_eventos_recortados_no_zoom_sem_mover_timestamps(self):
        from gantt import EVENTOS, desenhar_gantt
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 4, 20, 20)], [Cpu(7)], 0), 'RM')
        eventos = [dict(tipo=tipo, tick=tick, id_tarefa=1, ordem=[1])
                   for tick in (0, 2, 4) for tipo in EVENTOS]
        sim.historico.append(EstadoSimulacao(4, sim.historico[0].tarefas, [Cpu(7)], 0))
        sim.historico[-1].eventos = eventos
        sim.instante_atual = 1
        antes = retrato(sim)
        figura = Figure(figsize=(6, 4), dpi=100)
        canvas = FigureCanvasAgg(figura)
        ax = desenhar_gantt(sim, figura)
        canvas.draw()
        artistas = blocos(ax, 'evento')
        pontos = [(a.get_gid().split('-')[1], tuple(p)) for a in artistas for p in a.get_offsets()]
        self.assertCountEqual([(tipo, p[0]) for tipo, p in pontos],
                              [(e['tipo'], e['tick']) for e in eventos])
        self.assertLess(len(artistas), len(eventos))
        for artista in artistas:
            self.assertTrue(artista.get_clip_on(), artista.get_gid())
            for ponto in artista.get_offsets():
                x = ax.transData.transform(ponto)[0]
                raio = ((artista.get_sizes()[0] ** .5 + artista.get_linewidths()[0])
                        * figura.dpi / 72 / 2)
                self.assertGreaterEqual(x - raio, ax.bbox.x0)
                self.assertLessEqual(x + raio, ax.bbox.x1)
        ax.set_xlim(1, 3)
        canvas.draw()
        for artista in artistas:
            self.assertTrue(artista.get_clip_on())
            self.assertIsNotNone(artista.get_clip_box())
            self.assertEqual(tuple(artista.get_clip_box().extents), tuple(ax.bbox.extents))
        self.assertEqual([(a.get_gid().split('-')[1], tuple(p))
                          for a in artistas for p in a.get_offsets()], pontos)
        self.assertEqual(retrato(sim), antes)

    def test_legenda_unica_interna_apos_redesenho_e_resize(self):
        from gantt import EVENTOS, desenhar_gantt
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 4, 20, 20)], [Cpu(7)], 1), 'RM')
        sim.avancar(4)
        sim.retroceder(2)
        antes = retrato(sim)
        figura = Figure(figsize=(6, 4), dpi=100, layout='tight')
        canvas = FigureCanvasAgg(figura)
        ax = desenhar_gantt(sim, figura)
        esperados = ['Execução: número no bloco = CPU', 'Suspensa', 'CPU ociosa',
                     'Pronta / aguardando: sem cor'] + [e[1] for e in EVENTOS.values()]
        for largura, altura in ((600, 400), (900, 500), (600, 400)):
            figura.set_size_inches(largura / 100, altura / 100)
            for redesenhar in (False, True):
                with self.subTest(tamanho=(largura, altura), redesenhar=redesenhar):
                    if redesenhar:
                        ax = desenhar_gantt(sim, figura)
                    canvas.draw()
                    self.assertEqual(figura.axes, [ax])
                    self.assertIsNone(ax.get_legend())
                    self.assertEqual(len(figura.legends), 1)
                    legenda = figura.legends[0]
                    self.assertEqual([t.get_text() for t in legenda.get_texts()], esperados)
                    limite = legenda.get_window_extent(canvas.get_renderer())
                    self.assertGreaterEqual(limite.x0, figura.bbox.x0)
                    self.assertGreaterEqual(limite.y0, figura.bbox.y0)
                    self.assertLessEqual(limite.x1, figura.bbox.x1)
                    self.assertLessEqual(limite.y1, figura.bbox.y1)
                    self.assertLess(limite.y1, ax.xaxis.label.get_window_extent(canvas.get_renderer()).y0)
                    self.assertGreater(ax.bbox.height, 100)
                    self.assertIn('histórico: 0 a 2 ticks', ax.get_title())
        self.assertEqual(retrato(sim), antes)

    def test_agrupamento_nao_atravessa_quantum_nem_ocorrencias(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 5, 5, 5)], [Cpu(0)], 2), 'RM')
        sim.avancar(7)
        ax = desenhar_gantt(sim, Figure())
        self.assertEqual([i for bloco in blocos(ax, 'execucao') for i in intervalos(bloco)],
                         [(0, 2), (2, 4), (4, 5), (5, 7)])

    def test_numero_cpu_mantem_fonte_legivel_ao_aproximar(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 4, 20, 20)], [Cpu(0)], 1), 'RM')
        sim.executar_completa()
        ax = desenhar_gantt(sim, Figure(figsize=(11, 5)))
        self.assertTrue(ax.texts)
        self.assertTrue(all(texto.get_fontsize() == 7 for texto in ax.texts))
        for texto in ax.texts:
            self.assertIsNotNone(texto.get_clip_box())
            self.assertIsNotNone(texto.get_bbox_patch().get_clip_box())
        ax.set_xlim(0, 5)
        self.assertTrue(all(texto.get_fontsize() == 7 for texto in ax.texts))

    def test_inicial_vazio_e_historia_longa_sem_milhares_de_ticks(self):
        from gantt import desenhar_gantt
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        sim = Simulacao(EstadoSimulacao(0, [], [], 0), 'EDF')
        figura = Figure()
        ax = desenhar_gantt(sim, figura)
        FigureCanvasAgg(figura).draw()
        self.assertFalse(ax.collections)
        sim.historico.append(EstadoSimulacao(10000, [], [], 0))
        sim.instante_atual = 1
        ax = desenhar_gantt(sim, figura)
        self.assertEqual(ax.get_xlim(), (-200, 10200))
        self.assertLess(len(ax.get_xticks()), 20)

    def test_mil_ticks_usam_poucas_colecoes_sem_perder_eventos_ou_cpu_no_zoom(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 1000, 2000, 2000)],
                                        [Cpu(7)], 1), 'RM')
        sim.avancar(1000)
        ax = desenhar_gantt(sim, Figure())
        self.assertLess(len(ax.collections), 10)
        self.assertEqual(len(blocos(ax, 'execucao')[0].get_paths()), 1000)
        quantuns = [c for c in ax.collections if c.get_gid().startswith('evento-fim_quantum-')]
        self.assertEqual(list(quantuns[0].get_offsets()[:, 0]), list(range(1, 1000)))
        self.assertEqual(len(ax.texts), 1)
        ax.set_xlim(0, 10)
        self.assertTrue(ax.texts[0].get_visible())
        self.assertEqual(ax.texts[0].get_position()[0], 5)
        ax.set_xlim(990, 1000)
        self.assertEqual(ax.texts[0].get_position()[0], 995)

    def test_sorteio_marca_apenas_selecionadas_e_ordem_fisica_dos_ids(self):
        from gantt import desenhar_gantt
        from unittest.mock import patch
        from matplotlib.backends.backend_agg import FigureCanvasAgg
        sim = Simulacao(EstadoSimulacao(0, [TCB(i, f'{i * 1000:06X}', 0, 3, 10, 10)
            for i in (1, 2, 3)], [Cpu(0), Cpu(1)], 0), 'RM')
        with patch('scheduler.random.shuffle', side_effect=lambda g: g.reverse()):
            sim.avancar()
        fig = Figure()
        ax = desenhar_gantt(sim, fig)
        sorteios = [c for c in ax.collections if c.get_gid().startswith('evento-sorteio-')]
        self.assertEqual({c.get_label() for c in sorteios}, {'Sorteio: tarefa 2', 'Sorteio: tarefa 3'})
        FigureCanvasAgg(fig).draw()
        posicoes = {t.get_text(): t.get_window_extent().y0 for t in ax.get_yticklabels()}
        self.assertGreater(posicoes['Tarefa 3'], posicoes['Tarefa 2'])
        self.assertGreater(posicoes['Tarefa 2'], posicoes['Tarefa 1'])


if __name__ == '__main__':
    unittest.main()
