import copy
import unittest

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa


class TesteQuantum(unittest.TestCase):
    def test_fim_quantum_registrado_e_mesma_tarefa_pode_continuar(self):
        for algoritmo in ('RM', 'EDF'):
            with self.subTest(algoritmo=algoritmo):
                tarefa = TCB(1, 'FF0000', 0, 5, 20, 20)
                sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(4)], 2), algoritmo)
                sim.avancar(3)
                self.assertIn(
                    {'tipo': 'fim_quantum', 'tick': 2, 'id_tarefa': 1, 'id_cpu': 4},
                    sim.historico[2].eventos
                )
                self.assertEqual(sim.historico[1].tarefas[0].tempo_exec_quantum, 1)
                self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_quantum, 0)
                self.assertEqual(sim.historico[3].tarefas[0].tempo_exec_quantum, 1)
                self.assertEqual(sim.historico[3].tarefas[0].tempo_exec_instancia, 3)
                self.assertEqual(sim.historico[3].tarefas[0].estado_tarefa, EstadoTarefa.EXECUTANDO)
                self.assertEqual(sim.historico[0].tarefas[0].tempo_exec_quantum, 0)

    def test_chegada_prioritaria_interrompe_antes_do_quantum_e_reinicia_fatia(self):
        for algoritmo in ('RM', 'EDF'):
            with self.subTest(algoritmo=algoritmo):
                a = TCB(1, 'FF0000', 0, 6, 20, 20)
                b = TCB(2, '00FF00', 1, 1, 5, 5)
                sim = Simulacao(EstadoSimulacao(0, [a, b], [Cpu(0)], 4), algoritmo)
                sim.avancar(2)
                self.assertIn({'tipo': 'execucao', 'tick': 1, 'id_tarefa': 2, 'id_cpu': 0},
                              sim.historico[2].eventos)
                self.assertEqual(sim.historico[2].tarefas[0].estado_tarefa, EstadoTarefa.PRONTA)
                self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_instancia, 1)
                self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_quantum, 0)
                sim.avancar()
                self.assertIn({'tipo': 'execucao', 'tick': 2, 'id_tarefa': 1, 'id_cpu': 0},
                              sim.historico[3].eventos)
                self.assertEqual(sim.historico[3].tarefas[0].tempo_exec_quantum, 1)

    def test_suspensao_e_retomada_manual_reiniciam_fatia_sem_apagar_progresso(self):
        tarefa = TCB(1, 'FF0000', 0, 6, 20, 20)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 3), 'RM')
        sim.avancar()
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.SUSPENSA)
        self.assertEqual(sim.historico[1].tarefas[0].tempo_exec_quantum, 0)
        self.assertEqual(sim.historico[1].tarefas[0].tempo_exec_instancia, 1)
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.PRONTA)
        sim.avancar()
        self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_quantum, 1)
        self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_instancia, 2)
        # Alterar uma característica sem sair de EXECUTANDO não interrompe a fatia.
        sim.modificar_tarefa_em_execucao(1, prazo=25)
        self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_quantum, 1)

    def test_ativacao_periodica_e_conclusao_reavaliam_sem_esperar_quantum(self):
        for algoritmo in ('RM', 'EDF'):
            with self.subTest(algoritmo=algoritmo):
                a = TCB(1, 'FF0000', 0, 1, 3, 3)
                b = TCB(2, '00FF00', 0, 8, 20, 20)
                sim = Simulacao(EstadoSimulacao(0, [a, b], [Cpu(0)], 5), algoritmo)
                sim.avancar(4)
                executadas = [e['id_tarefa'] for estado in sim.historico
                              for e in estado.eventos if e['tipo'] == 'execucao']
                self.assertEqual(executadas, [1, 2, 2, 1])
                self.assertEqual(sim.historico[3].tarefas[1].tempo_exec_quantum, 2)
                self.assertEqual(sim.historico[4].tarefas[1].tempo_exec_quantum, 0)

    def test_quantum_zero_sem_limite_e_conclusao_tem_precedencia_sobre_fim_quantum(self):
        for quantum, duracao in ((0, 3), (2, 2)):
            with self.subTest(quantum=quantum):
                tarefa = TCB(1, 'FF0000', 0, duracao, 5, 5)
                sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], quantum), 'RM')
                sim.executar_completa()
                self.assertEqual(sim.historico[-1].tarefas[0].instancias_concluidas, 10)
                self.assertFalse(any(e['tipo'] == 'fim_quantum'
                                     for estado in sim.historico for e in estado.eventos))
                self.assertEqual(sim.historico[-1].tarefas[0].tempo_exec_quantum, 0)

    def test_duas_cpus_tem_fatias_independentes(self):
        a = TCB(1, 'FF0000', 0, 5, 20, 20)
        b = TCB(2, '00FF00', 0, 3, 30, 30)
        sim = Simulacao(EstadoSimulacao(0, [a, b], [Cpu(4), Cpu(7)], 2), 'RM')
        sim.avancar(4)
        expiracoes = [(e['tick'], e['id_tarefa'], e['id_cpu'])
                      for estado in sim.historico for e in estado.eventos
                      if e['tipo'] == 'fim_quantum']
        self.assertEqual(expiracoes, [(2, 1, 4), (2, 2, 7), (4, 1, 4)])
        self.assertEqual(sim.historico[3].tarefas[1].tempo_exec_quantum, 0)
        self.assertEqual(sim.historico[4].cpus[1].tempo_desligada, 1)

    def test_retrocesso_reutiliza_contadores_e_eventos_salvos(self):
        tarefa = TCB(1, 'FF0000', 0, 6, 20, 20)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 2), 'RM')
        sim.avancar(4)
        snapshots = list(sim.historico)
        valores = copy.deepcopy([(s.tarefas[0].tempo_exec_quantum, s.eventos) for s in snapshots])
        sim.retroceder(3)
        sim.avancar(3)
        for atual, salvo in zip(sim.historico, snapshots):
            self.assertIs(atual, salvo)
        self.assertEqual([(s.tarefas[0].tempo_exec_quantum, s.eventos) for s in sim.historico], valores)

    def test_fim_quantum_preserva_desempate_de_quem_executava(self):
        for algoritmo in ('RM', 'EDF'):
            with self.subTest(algoritmo=algoritmo):
                a = TCB(1, 'FF0000', 0, 5, 20, 20)
                b = TCB(2, '00FF00', 1, 1, 20, 19)
                sim = Simulacao(EstadoSimulacao(0, [a, b], [Cpu(0)], 1), algoritmo)
                sim.avancar(2)
                self.assertIn({'tipo': 'execucao', 'tick': 1, 'id_tarefa': 1, 'id_cpu': 0},
                              sim.historico[2].eventos)
                self.assertEqual(sim.historico[2].tarefas[1].estado_tarefa, EstadoTarefa.PRONTA)


if __name__ == '__main__':
    unittest.main()
