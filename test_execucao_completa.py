import inspect
import unittest
from unittest.mock import patch

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa
import scheduler


class TesteModoCompleto(unittest.TestCase):
    def test_executa_ate_todas_as_tarefas_finalizarem_em_rm_e_edf(self):
        for algoritmo in ['RM', 'EDF']:
            with self.subTest(algoritmo=algoritmo):
                t1 = TCB(1, 'FF0000', 0, 1, 3, 2)
                t2 = TCB(2, '00FF00', 2, 2, 7, 1)
                inicial = EstadoSimulacao(0, [t1, t2], [Cpu(0), Cpu(1)], 0)
                sim = Simulacao(inicial, algoritmo)
                final = sim.executar_completa()
                self.assertIs(final, sim.historico[sim.instante_atual])
                self.assertTrue(all(t.estado_tarefa == EstadoTarefa.FINALIZADA for t in final.tarefas))
                self.assertEqual([t.instancias_concluidas for t in final.tarefas], [10, 10])
                self.assertEqual(final.tick, 67)
                self.assertEqual(len(sim.historico), 68)
                self.assertEqual(inicial.tarefas[0].instancias_concluidas, 0)
                self.assertTrue(any(e['tipo'] == 'perda_prazo' for estado in sim.historico for e in estado.eventos))

    def test_reutiliza_futuro_salvo_sem_refazer_sorteios(self):
        tarefas = [TCB(1, 'FF0000', 0, 1, 4, 4), TCB(2, '00FF00', 0, 1, 4, 4)]
        sim = Simulacao(EstadoSimulacao(0, tarefas, [Cpu(0)], 0), 'RM')
        with patch('scheduler.random.shuffle', wraps=scheduler.random.shuffle) as sorteio:
            final = sim.executar_completa()
            chamadas = sorteio.call_count
            tamanho = len(sim.historico)
            sim.retroceder(5)
            self.assertIs(sim.executar_completa(), final)
            self.assertEqual(sorteio.call_count, chamadas)
            self.assertEqual(len(sim.historico), tamanho)
            # Executar novamente após o término não cria ticks extras.
            self.assertIs(sim.executar_completa(), final)
            self.assertEqual(len(sim.historico), tamanho)

    def test_lista_vazia_ja_esta_concluida(self):
        inicial = EstadoSimulacao(0, [], [Cpu(0)], 0)
        sim = Simulacao(inicial, 'RM')
        self.assertIs(sim.executar_completa(), inicial)
        self.assertEqual(len(sim.historico), 1)

    def test_interrompe_se_tarefa_suspensa_ou_sem_cpus(self):
        for bloqueio in ['suspensa', 'sem_cpus']:
            with self.subTest(bloqueio=bloqueio):
                tarefa = TCB(1, 'FF0000', 0, 1, 3, 3)
                cpus = [Cpu(0)]
                if bloqueio == 'suspensa':
                    tarefa.estado_tarefa = EstadoTarefa.SUSPENSA
                else:
                    cpus = []
                inicial = EstadoSimulacao(0, [tarefa], cpus, 0)
                sim = Simulacao(inicial, 'RM')
                with self.assertRaisesRegex(RuntimeError, 'suspensa|CPU'):
                    sim.executar_completa()
                self.assertEqual(len(sim.historico), 1)
                self.assertIs(sim.historico[sim.instante_atual], inicial)

    def test_continua_do_estado_atual_sem_parametro_de_limite(self):
        self.assertEqual(list(inspect.signature(Simulacao.executar_completa).parameters), ['self'])
        tarefa = TCB(1, 'FF0000', 0, 1, 3, 3)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.avancar(2)
        self.assertEqual(sim.historico[sim.instante_atual].tick, 2)
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].instancias_concluidas, 1)
        self.assertEqual(sim.executar_completa().tarefas[0].instancias_concluidas, 10)

    def test_para_imediatamente_apos_concluir_a_decima_ocorrencia(self):
        tarefa = TCB(1, 'FF0000', 0, 1, 3, 3)
        tarefa.instancias_concluidas = 9
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        final = sim.executar_completa()
        self.assertEqual(final.tick, 1)
        self.assertEqual(final.tarefas[0].estado_tarefa, EstadoTarefa.FINALIZADA)


if __name__ == '__main__':
    unittest.main()
