import unittest

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa


class TesteExecucaoTick(unittest.TestCase):
    def test_conclusao_no_prazo_e_registro_do_intervalo_em_duas_cpus(self):
        t1 = TCB(1, 'FF0000', 0, 1, 5, 1)
        t2 = TCB(2, '00FF00', 0, 1, 10, 1)
        inicial = EstadoSimulacao(0, [t1, t2], [Cpu(4), Cpu(7)], 0)
        sim = Simulacao(inicial, 'RM')
        sim.avancar()
        atual = sim.historico[sim.instante_atual]
        for tarefa in atual.tarefas:
            self.assertEqual(tarefa.tempo_exec_instancia, 1)
            self.assertEqual(tarefa.instancias_concluidas, 1)
            self.assertEqual(tarefa.estado_tarefa, EstadoTarefa.AGUARDANDO)
            self.assertFalse(tarefa.perdeu_prazo)
            self.assertIsNone(tarefa.id_cpu_atual)
        self.assertTrue(all(cpu.id_tarefa_alocada is None for cpu in atual.cpus))
        self.assertTrue(all(cpu.tempo_desligada == 0 for cpu in atual.cpus))
        execucoes = [e for e in atual.eventos if e['tipo'] == 'execucao']
        self.assertEqual(execucoes, [
            {'tipo': 'execucao', 'tick': 0, 'id_tarefa': 1, 'id_cpu': 4},
            {'tipo': 'execucao', 'tick': 0, 'id_tarefa': 2, 'id_cpu': 7}
        ])
        conclusoes = [e for e in atual.eventos if e['tipo'] == 'conclusao']
        self.assertEqual([e['tick'] for e in conclusoes], [1, 1])
        self.assertEqual(inicial.tarefas[0].tempo_exec_instancia, 0)

    def test_tarefa_pronta_perde_prazo_uma_vez_e_depois_conclui(self):
        t1 = TCB(1, 'FF0000', 0, 3, 5, 5)
        t2 = TCB(2, '00FF00', 0, 1, 10, 1)
        sim = Simulacao(EstadoSimulacao(0, [t1, t2], [Cpu(0)], 0), 'RM')
        sim.avancar()
        atual = sim.historico[sim.instante_atual]
        self.assertEqual(atual.tarefas[1].estado_tarefa, EstadoTarefa.PRONTA)
        self.assertTrue(atual.tarefas[1].perdeu_prazo)
        self.assertIn({'tipo': 'perda_prazo', 'tick': 1, 'id_tarefa': 2}, atual.eventos)
        sim.avancar(3)
        atual = sim.historico[sim.instante_atual]
        self.assertEqual(atual.tarefas[1].instancias_concluidas, 1)
        self.assertEqual(atual.tarefas[1].estado_tarefa, EstadoTarefa.AGUARDANDO)
        perdas = [e for estado in sim.historico for e in estado.eventos
                  if e['tipo'] == 'perda_prazo' and e['id_tarefa'] == 2]
        self.assertEqual(len(perdas), 1)

    def test_reativa_e_finaliza_apos_dez_ocorrencias(self):
        tarefa = TCB(1, 'FF0000', 0, 1, 3, 1)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.avancar(28)
        final = sim.historico[sim.instante_atual]
        self.assertEqual(final.tarefas[0].instancias_concluidas, 10)
        self.assertEqual(final.tarefas[0].estado_tarefa, EstadoTarefa.FINALIZADA)
        self.assertEqual(final.tarefas[0].prazo_absoluto, 28)
        self.assertFalse(final.tarefas[0].perdeu_prazo)
        self.assertEqual(final.cpus[0].tempo_desligada, 18)
        sim.avancar(3)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].instancias_concluidas, 10)
        self.assertEqual(final.cpus[0].tempo_desligada, 18)
        sim.retroceder(3)
        self.assertIs(sim.historico[sim.instante_atual], final)


if __name__ == '__main__':
    unittest.main()
