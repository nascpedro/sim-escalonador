import copy
import unittest

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB


class TestConfiguracaoSistema(unittest.TestCase):
    def criar(self):
        sim = Simulacao(EstadoSimulacao(0, [TCB(1, '112233', 0, 8, 10, 10),
            TCB(2, '445566', 0, 8, 20, 20)], [Cpu(0), Cpu(1)], 4), 'RM')
        sim.avancar(3)
        sim.retroceder()
        return sim

    def test_sem_mudancas_e_rejeicao_preservam_futuro(self):
        sim = self.criar()
        antes = copy.deepcopy(sim.historico)
        futuro = sim.historico[-1]
        self.assertFalse(sim.configurar_sistema('rm', 4, 2))
        for args in [('FIFO', 1, 2), ('RM', -1, 2), ('RM', True, 2), ('RM', 1, 0)]:
            with self.assertRaises(ValueError):
                sim.configurar_sistema(*args)
        self.assertIs(sim.historico[-1], futuro)
        for atual, antigo in zip(sim.historico, antes):
            self.assertEqual(atual.quantum, antigo.quantum)
            self.assertEqual([vars(t) for t in atual.tarefas], [vars(t) for t in antigo.tarefas])

    def test_algoritmo_no_snapshot_e_reducao_interrompe_fatia(self):
        sim = self.criar()
        passado = sim.historico[1]
        self.assertTrue(sim.configurar_sistema('EDF', 4, 1))
        self.assertEqual(len(sim.historico), 3)
        self.assertEqual(sim.algoritmo, 'EDF')
        atual = sim.historico[2]
        t = next(t for t in atual.tarefas if t.id == 2)
        self.assertEqual(t.estado_tarefa, EstadoTarefa.PRONTA)
        self.assertEqual(t.tempo_exec_quantum, 0)
        self.assertIsNone(t.id_cpu_atual)
        sim.retroceder()
        self.assertIs(sim.historico[1], passado)
        self.assertEqual(sim.algoritmo, 'RM')
        self.assertEqual(len(passado.cpus), 2)
        sim.avancar()
        self.assertEqual(sim.algoritmo, 'EDF')
        sim.configurar_sistema('EDF', 10000, 3)
        self.assertEqual([c.id_cpu for c in sim.historico[2].cpus], [0, 1, 2])
        self.assertTrue(all(t.tempo_exec_quantum == 0 for t in sim.historico[2].tarefas))
