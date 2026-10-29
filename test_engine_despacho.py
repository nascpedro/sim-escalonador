import unittest

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa


class TesteDespacho(unittest.TestCase):
    def test_distribui_por_prioridade_sem_duplicar_tarefas(self):
        t1 = TCB(1, 'FF0000', 0, 2, 10, 10)
        t2 = TCB(2, '00FF00', 0, 2, 5, 5)
        t3 = TCB(3, '0000FF', 0, 2, 20, 20)
        inicial = EstadoSimulacao(0, [t1, t2, t3], [Cpu(4), Cpu(7)], 0)
        sim = Simulacao(inicial, 'RM')

        sim.avancar()
        atual = sim.historico[sim.instante_atual]

        self.assertEqual([cpu.id_tarefa_alocada for cpu in atual.cpus], [2, 1])
        self.assertEqual(atual.tarefas[0].id_cpu_atual, 7)
        self.assertEqual(atual.tarefas[1].id_cpu_atual, 4)
        self.assertEqual(atual.tarefas[0].estado_tarefa, EstadoTarefa.EXECUTANDO)
        self.assertEqual(atual.tarefas[1].estado_tarefa, EstadoTarefa.EXECUTANDO)
        self.assertEqual(atual.tarefas[2].estado_tarefa, EstadoTarefa.PRONTA)
        self.assertIsNone(atual.tarefas[2].id_cpu_atual)
        self.assertEqual([t.tempo_exec_instancia for t in atual.tarefas], [1, 1, 0])
        self.assertTrue(all(cpu.id_tarefa_alocada is None for cpu in inicial.cpus))
        self.assertTrue(all(t.estado_tarefa == EstadoTarefa.AGUARDANDO for t in inicial.tarefas))

    def test_chegada_prioritaria_retira_tarefa_da_cpu(self):
        t1 = TCB(1, 'FF0000', 0, 2, 10, 10)
        t2 = TCB(2, '00FF00', 1, 2, 5, 5)
        sim = Simulacao(EstadoSimulacao(0, [t1, t2], [Cpu(0)], 0), 'RM')
        sim.avancar()
        anterior = sim.historico[sim.instante_atual]
        self.assertEqual(anterior.cpus[0].id_tarefa_alocada, 1)

        sim.avancar()
        atual = sim.historico[sim.instante_atual]
        self.assertEqual(atual.cpus[0].id_tarefa_alocada, 2)
        self.assertEqual(atual.tarefas[0].estado_tarefa, EstadoTarefa.PRONTA)
        self.assertIsNone(atual.tarefas[0].id_cpu_atual)
        self.assertEqual(atual.tarefas[1].estado_tarefa, EstadoTarefa.EXECUTANDO)
        self.assertEqual(atual.tarefas[1].id_cpu_atual, 0)
        self.assertEqual(anterior.tarefas[0].estado_tarefa, EstadoTarefa.EXECUTANDO)
        sim.retroceder()
        self.assertIs(sim.historico[sim.instante_atual], anterior)

    def test_cpus_excedentes_ou_sem_candidatas_ficam_livres(self):
        tarefa = TCB(1, 'FF0000', 0, 2, 5, 5)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0), Cpu(1)], 0), 'RM')
        sim.avancar()
        atual = sim.historico[sim.instante_atual]
        self.assertEqual(atual.cpus[0].id_tarefa_alocada, 1)
        self.assertIsNone(atual.cpus[1].id_tarefa_alocada)
        self.assertEqual(atual.cpus[1].tempo_desligada, 1)

        # Uma suspensão manual exige retirar os vínculos de execução no próximo despacho.
        atual.tarefas[0].estado_tarefa = EstadoTarefa.SUSPENSA
        sim.avancar()
        atual = sim.historico[sim.instante_atual]
        self.assertTrue(all(cpu.id_tarefa_alocada is None for cpu in atual.cpus))
        self.assertIsNone(atual.tarefas[0].id_cpu_atual)
        self.assertEqual(atual.tarefas[0].estado_tarefa, EstadoTarefa.SUSPENSA)


if __name__ == '__main__':
    unittest.main()
