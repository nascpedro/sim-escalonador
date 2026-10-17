import unittest
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa
from engine import Simulacao

class TesteMotorPassos1e2(unittest.TestCase):

    def test_chegada_tarefas_e_historico(self):
        # Cria duas tarefas: T1 chega no tick 0, T2 só chega no tick 2
        t1 = TCB(id_tarefa=1, cor="FF0000", ingresso=0, duracao=2, periodo=5, prazo=5)
        t2 = TCB(id_tarefa=2, cor="00FF00", ingresso=2, duracao=1, periodo=5, prazo=5)
        cpus = [Cpu(id_cpu=0)]

        estado_0 = EstadoSimulacao(tick=0, tarefas=[t1, t2], cpus=cpus, quantum=0)
        sim = Simulacao(estado_inicial=estado_0, algoritmo="RM")

        # No início (tick 0), antes de rodar, ambas estão AGUARDANDO
        self.assertEqual(sim.estado_atual.tick, 0)
        self.assertEqual(sim.estado_atual.tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)
        self.assertEqual(sim.estado_atual.tarefas[1].estado_tarefa, EstadoTarefa.AGUARDANDO)

        # Avança 1 tick: executa o intervalo [0, 1)
        sim.avancar(1)
        self.assertEqual(sim.estado_atual.tick, 1)
        # T1 chegou em t=0, então deve estar PRONTA; T2 ainda está AGUARDANDO
        self.assertEqual(sim.estado_atual.tarefas[0].estado_tarefa, EstadoTarefa.PRONTA)
        self.assertEqual(sim.estado_atual.tarefas[1].estado_tarefa, EstadoTarefa.AGUARDANDO)

        # Avança até o tick 3 (passando pelo intervalo [2, 3) onde T2 chega em t=2)
        sim.avancar(2)
        self.assertEqual(sim.estado_atual.tick, 3)
        self.assertEqual(sim.estado_atual.tarefas[1].estado_tarefa, EstadoTarefa.PRONTA)
        self.assertEqual(sim.estado_atual.tarefas[1].prazo_absoluto, 7) # t=2 + prazo=5

        # Testa retroceder para o tick 0 e garante que o passado não foi alterado
        sim.retroceder(3)
        self.assertEqual(sim.estado_atual.tick, 0)
        self.assertEqual(sim.estado_atual.tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)

if __name__ == "__main__":
    unittest.main()