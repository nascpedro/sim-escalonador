import unittest
from unittest.mock import patch

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa
from scheduler import escalonar


class TesteIntegracaoEscalonamento(unittest.TestCase):
    def test_seleciona_candidatas_do_novo_estado_e_aplica_politica(self):
        for algoritmo, ordem_esperada in [('RM', [2, 1]), ('EDF', [1, 2])]:
            with self.subTest(algoritmo=algoritmo):
                # T1 ativa neste tick; T2 já executava e também deve disputar CPU.
                t1 = TCB(1, 'FF0000', 0, 2, 10, 3)
                t2 = TCB(2, '00FF00', 0, 2, 5, 8)
                t2.estado_tarefa = EstadoTarefa.EXECUTANDO
                t3 = TCB(3, '0000FF', 5, 2, 10, 10)
                t4 = TCB(4, 'FFFF00', 0, 2, 10, 10)
                t4.estado_tarefa = EstadoTarefa.SUSPENSA
                t5 = TCB(5, 'FF00FF', 0, 2, 10, 10)
                t5.instancias_concluidas = 10
                t5.estado_tarefa = EstadoTarefa.FINALIZADA
                inicial = EstadoSimulacao(0, [t1, t2, t3, t4, t5], [Cpu(0)], 0)
                sim = Simulacao(inicial, algoritmo)
                ordens = []

                # Observa a integração, mas executa a função real de escalonamento.
                def observar(candidatas, politica, sorteios):
                    ordenadas = escalonar(candidatas, politica, sorteios)
                    ordens.append([tarefa.id for tarefa in ordenadas])
                    return ordenadas

                with patch('engine.escalonar', side_effect=observar, create=True) as chamada:
                    sim.avancar()

                chamada.assert_called_once()
                candidatas, politica, sorteios = chamada.call_args.args
                self.assertEqual(politica, algoritmo)
                self.assertEqual([tarefa.id for tarefa in candidatas], [1, 2])
                self.assertEqual(ordens, [ordem_esperada])
                novo = sim.historico[sim.instante_atual]
                self.assertIs(candidatas[0], novo.tarefas[0])
                self.assertIs(candidatas[1], novo.tarefas[1])
                self.assertIsNot(candidatas[0], t1)
                self.assertEqual(t1.estado_tarefa, EstadoTarefa.AGUARDANDO)
                self.assertEqual(t2.estado_tarefa, EstadoTarefa.EXECUTANDO)
                self.assertEqual(novo.cpus[0].id_tarefa_alocada, ordem_esperada[0])
                # Somente a tarefa selecionada consome uma unidade de CPU.
                self.assertEqual(novo.tarefas[0].tempo_exec_instancia, 1 if algoritmo == 'EDF' else 0)


if __name__ == '__main__':
    unittest.main()
