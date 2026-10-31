"""Casos do capítulo e invariantes de ocorrências sobrepostas."""
import copy
import unittest

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB


class TestOcorrencias(unittest.TestCase):
    def criar(self, algoritmo='RM', cpus=1):
        return Simulacao(EstadoSimulacao(0, [TCB(1, '112233', 0, 5, 3, 4)],
                                        [Cpu(i) for i in range(cpus)], 2), algoritmo)

    def test_fila_preserva_ativacao_prazo_e_dez_conclusoes_em_duas_cpus(self):
        for algoritmo in ('RM', 'EDF'):
            sim = self.criar(algoritmo, cpus=2)
            final = sim.executar_completa()
            eventos = [e for s in sim.historico for e in s.eventos]
            self.assertEqual(final.tick, 50)
            self.assertEqual([e['tick'] for e in eventos if e['tipo'] == 'ativacao'], list(range(0, 30, 3)))
            self.assertEqual([e['tick'] for e in eventos if e['tipo'] == 'conclusao'], list(range(5, 51, 5)))
            self.assertEqual(len([e for e in eventos if e['tipo'] == 'perda_prazo']), 10)
            self.assertEqual(final.tarefas[0].ocorrencias_pendentes, [])
            self.assertEqual(final.tarefas[0].estado_tarefa, EstadoTarefa.FINALIZADA)
            for s in sim.historico:
                self.assertLessEqual(len([e for e in s.eventos if e['tipo'] == 'execucao']), 1)

    def test_prazo_vence_na_fila_uma_vez_e_replay_nao_altera_fila(self):
        sim = self.criar()
        sim.modificar_tarefa_em_execucao(1, duracao=12)
        sim.avancar(10)
        salvo = copy.deepcopy(sim.historico)
        perdas = [e for s in sim.historico for e in s.eventos if e['tipo'] == 'perda_prazo']
        self.assertIn(dict(tipo='perda_prazo', tick=7, id_tarefa=1, ativacao=3), perdas)
        sim.retroceder(5)
        sim.avancar(5)
        self.assertEqual(sim.historico[-1].tarefas[0].ocorrencias_pendentes,
                         salvo[-1].tarefas[0].ocorrencias_pendentes)
        sim.modificar_tarefa_em_execucao(1, prazo=20)
        self.assertEqual([o.prazo_absoluto for o in sim.historico[-1].tarefas[0].ocorrencias_pendentes],
                         [23, 26, 29])
        self.assertEqual(salvo[-1].tarefas[0].ocorrencias_pendentes[0].prazo_absoluto, 7)

    def test_aguardando_abandona_fila_sem_contar_conclusoes(self):
        sim = self.criar()
        sim.avancar(4)
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.AGUARDANDO)
        t = sim.historico[-1].tarefas[0]
        self.assertEqual(t.ocorrencias_pendentes, [])
        self.assertEqual(t.instancias_concluidas, 0)
        sim.executar_completa()
        self.assertEqual(sim.historico[-1].tarefas[0].instancias_concluidas, 10)

    def test_figura_2_5_rm_e_figura_2_6_edf(self):
        tarefas = [TCB('A', 'FF0000', 0, 20, 100, 100),
                   TCB('B', '00FF00', 0, 40, 150, 150),
                   TCB('C', '0000FF', 0, 100, 350, 350)]
        sim = Simulacao(EstadoSimulacao(0, tarefas, [Cpu(0)], 0), 'RM')
        sim.avancar(240)
        esperado = (['A'] * 20 + ['B'] * 40 + ['C'] * 40 + ['A'] * 20 +
                    ['C'] * 30 + ['B'] * 40 + ['C'] * 10 + ['A'] * 20 + ['C'] * 20)
        self.assertEqual([e['id_tarefa'] for s in sim.historico for e in s.eventos
                          if e['tipo'] == 'execucao'], esperado)
        for algoritmo, perdas in (('RM', [50]), ('EDF', [])):
            sim = Simulacao(EstadoSimulacao(0, [TCB('A', 'FF0000', 0, 10, 20, 20),
                TCB('B', '00FF00', 0, 25, 50, 50)], [Cpu(0)], 0), algoritmo)
            sim.avancar(60)
            self.assertEqual([e['tick'] for s in sim.historico for e in s.eventos
                              if e['tipo'] == 'perda_prazo'], perdas)
            self.assertEqual([e['tick'] for s in sim.historico for e in s.eventos
                              if e['tipo'] == 'ativacao' and e['id_tarefa'] == 'B'], [0, 50])
            # Com RM, B continua em 55..60: sua segunda ocorrência não desaparece.
            self.assertTrue(any(e['tipo'] == 'execucao' and e['tick'] == 59
                                for e in sim.historico[-1].eventos))
