import unittest
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa
from engine import Simulacao

class TesteExecucaoCompleta(unittest.TestCase):

    def test_execucao_conclusao_e_cpu_desligada(self):
        # T1 tem duração 2 e período 5
        t1 = TCB(id_tarefa=1, cor="FF0000", ingresso=0, duracao=2, periodo=5, prazo=5)
        cpus = [Cpu(id_cpu=0)]
        estado_0 = EstadoSimulacao(tick=0, tarefas=[t1], cpus=cpus, quantum=0)
        sim = Simulacao(estado_0, "RM")

        # Tick 0 -> 1: T1 executa 1/2
        sim.avancar(1)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].estado_tarefa, EstadoTarefa.EXECUTANDO)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].tempo_exec_instancia, 1)
        self.assertEqual(sim.historico[sim.instante_atual].cpus[0].id_tarefa_alocada, 1)

        # Tick 1 -> 2: T1 executa 2/2, conclui 1ª instância e vai para AGUARDANDO
        sim.avancar(1)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].tempo_exec_instancia, 2)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].instancias_concluidas, 1)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)

        # Tick 2 -> 3: Nenhuma tarefa pronta, CPU 0 deve ficar desligada (+1 tick)
        sim.avancar(1)
        self.assertIsNone(sim.historico[sim.instante_atual].cpus[0].id_tarefa_alocada)
        self.assertEqual(sim.historico[sim.instante_atual].cpus[0].tempo_desligada, 1)

    def test_perda_de_prazo_sem_abortar(self):
        # T1 precisa de 3 ticks de duração, mas o prazo é de apenas 2 ticks!
        t1 = TCB(id_tarefa=1, cor="FF0000", ingresso=0, duracao=3, periodo=10, prazo=2)
        cpus = [Cpu(id_cpu=0)]
        estado_0 = EstadoSimulacao(tick=0, tarefas=[t1], cpus=cpus, quantum=0)
        sim = Simulacao(estado_0, "EDF")

        # Avança 2 ticks (chega em t=2): T1 executou 2/3 e atingiu o prazo (2) -> perdeu_prazo = True
        sim.avancar(2)
        self.assertTrue(sim.historico[sim.instante_atual].tarefas[0].perdeu_prazo)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].estado_tarefa, EstadoTarefa.EXECUTANDO)

        # Avança mais 1 tick (chega em t=3): T1 não foi abortada e conclui 3/3!
        sim.avancar(1)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].instancias_concluidas, 1)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)

if __name__ == "__main__":
    unittest.main()