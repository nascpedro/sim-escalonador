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


def intervalo(bloco):
    xs = bloco.get_paths()[0].vertices[:, 0]
    return float(xs.min()), float(xs.max())


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
        self.assertEqual(sum(b-a for a, b in map(intervalo, execucoes)), 3)
        desenhados = []
        for bloco in execucoes:
            identidade = bloco.get_label().split(',')
            tarefa = int(identidade[0].rsplit(' ', 1)[1])
            cpu = int(identidade[1].rsplit(' ', 1)[1])
            a, b = intervalo(bloco)
            desenhados.extend((tarefa, cpu, tick) for tick in range(int(a), int(b)))
        self.assertCountEqual(desenhados, [
            (e['id_tarefa'], e['id_cpu'], e['tick'])
            for s in sim.historico[1:3] for e in s.eventos if e['tipo'] == 'execucao'])
        self.assertEqual({b.get_label().split('CPU ')[1].split(',')[0]
                          for b in execucoes}, {'4', '7'})
        self.assertEqual(ax.get_xlim(), (0, 2))
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
        self.assertEqual(list(map(intervalo, suspensos)), [(0, 1)])
        self.assertTrue(suspensos[0].get_hatch())
        execucoes = [b for b in blocos(ax, 'execucao') if id_ in b.get_label()]
        self.assertEqual(tuple(execucoes[0].get_facecolors()[0]), to_rgba('#112233'))
        self.assertEqual(tuple(execucoes[-1].get_facecolors()[0]), to_rgba('#ABCDEF'))
        esperados = [(e['tipo'], e['tick']) for s in sim.historico[1:] for e in s.eventos
                     if e['tipo'] not in ('execucao', 'cpu_desligada')]
        eventos = blocos(ax, 'evento')
        self.assertCountEqual([(e.get_gid().split('-')[1], e.get_offsets()[0, 0])
                               for e in eventos], esperados)
        self.assertEqual({e.get_gid().split('-')[1] for e in eventos},
                         {'chegada', 'ativacao', 'conclusao', 'perda_prazo', 'sorteio', 'fim_quantum'})
        self.assertEqual(retrato(sim), antes)

    def test_agrupamento_nao_atravessa_quantum_nem_ocorrencias(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 5, 5, 5)], [Cpu(0)], 2), 'RM')
        sim.avancar(7)
        ax = desenhar_gantt(sim, Figure())
        self.assertEqual(list(map(intervalo, blocos(ax, 'execucao'))),
                         [(0, 2), (2, 4), (4, 5), (5, 7)])

    def test_numero_cpu_mantem_fonte_legivel_ao_aproximar(self):
        from gantt import desenhar_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '123456', 0, 4, 20, 20)], [Cpu(0)], 1), 'RM')
        sim.executar_completa()
        ax = desenhar_gantt(sim, Figure(figsize=(11, 5)))
        self.assertTrue(ax.texts)
        self.assertTrue(all(texto.get_fontsize() == 7 for texto in ax.texts))
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
        self.assertEqual(ax.get_xlim(), (0, 10000))
        self.assertLess(len(ax.get_xticks()), 20)


if __name__ == '__main__':
    unittest.main()
