import copy
import unittest
from unittest.mock import patch

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa


class TesteEventosAtivacao(unittest.TestCase):
    def test_chegada_inicial_no_ingresso_adiado_sem_antecipacao(self):
        tarefa = TCB(7, 'FF0000', 3, 1, 4, 4)
        inicial = EstadoSimulacao(0, [tarefa], [Cpu(0)], 0)
        sim = Simulacao(inicial, 'RM')

        sim.avancar(3)
        self.assertEqual(sim.historico[-1].tick, 3)
        for estado in sim.historico:
            self.assertFalse(any(e['tipo'] == 'chegada' for e in estado.eventos))
        self.assertEqual(sim.historico[-1].tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)

        sim.avancar()
        chegadas = [e for e in sim.historico[-1].eventos if e['tipo'] == 'chegada']
        self.assertEqual(chegadas, [{'tipo': 'chegada', 'tick': 3, 'id_tarefa': 7}])
        self.assertEqual(sim.historico[-1].tick, 4)
        self.assertEqual(inicial.eventos, [])
        self.assertEqual(inicial.tarefas[0].estado_tarefa, EstadoTarefa.AGUARDANDO)


    def test_primeira_ativacao_e_distinta_da_chegada_no_mesmo_tick(self):
        for algoritmo in ['RM', 'EDF']:
            with self.subTest(algoritmo=algoritmo):
                tarefa = TCB(7, 'FF0000', 0, 2, 4, 3)
                sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), algoritmo)

                sim.avancar()
                estado = sim.historico[-1]
                self.assertEqual(estado.eventos[:2], [
                    {'tipo': 'chegada', 'tick': 0, 'id_tarefa': 7},
                    {'tipo': 'ativacao', 'tick': 0, 'id_tarefa': 7},
                ])
                self.assertEqual(estado.tick, 1)
                self.assertEqual(estado.tarefas[0].prazo_absoluto, 3)
                self.assertEqual(estado.tarefas[0].tempo_exec_instancia, 1)


    def test_reativa_dez_ocorrencias_sem_repetir_chegada(self):
        tarefa = TCB(7, 'FF0000', 2, 1, 3, 2)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.executar_completa()
        sim.avancar(4)  # Mesmo após a décima conclusão, não há novas ativações.

        chegadas = []
        ativacoes = []
        for estado in sim.historico:
            for evento in estado.eventos:
                if evento['tipo'] == 'chegada':
                    chegadas.append(evento)
                if evento['tipo'] == 'ativacao':
                    ativacoes.append(evento)
                    self.assertEqual(estado.tick, evento['tick'] + 1)
        self.assertEqual(chegadas, [{'tipo': 'chegada', 'tick': 2, 'id_tarefa': 7}])
        self.assertEqual(ativacoes, [
            {'tipo': 'ativacao', 'tick': tick, 'id_tarefa': 7}
            for tick in range(2, 30, 3)
        ])
        self.assertEqual(sim.historico[-1].tarefas[0].instancias_concluidas, 10)

    def test_ocorrencia_pendente_nao_gera_ativacao_nem_reinicia_progresso(self):
        for estado_pendente in [EstadoTarefa.EXECUTANDO, EstadoTarefa.PRONTA, EstadoTarefa.SUSPENSA]:
            with self.subTest(estado=estado_pendente):
                tarefa = TCB(7, 'FF0000', 0, 5, 2, 1)
                cpus = [] if estado_pendente == EstadoTarefa.PRONTA else [Cpu(0)]
                sim = Simulacao(EstadoSimulacao(0, [tarefa], cpus, 0), 'RM')
                sim.avancar(2)
                if estado_pendente == EstadoTarefa.SUSPENSA:
                    sim.modificar_tarefa_em_execucao(7, estado_tarefa=EstadoTarefa.SUSPENSA)
                anterior = copy.deepcopy(sim.historico[-1])
                self.assertEqual(anterior.tarefas[0].estado_tarefa, estado_pendente)

                sim.avancar()  # t=2 é um novo múltiplo do período, mas há ocorrência pendente.
                atual = sim.historico[-1]
                self.assertFalse(any(e['tipo'] in ['chegada', 'ativacao'] for e in atual.eventos))
                progresso = 1 if estado_pendente == EstadoTarefa.EXECUTANDO else 0
                self.assertEqual(atual.tarefas[0].tempo_exec_instancia,
                                 anterior.tarefas[0].tempo_exec_instancia + progresso)
                self.assertEqual(atual.tarefas[0].prazo_absoluto, 1)
                self.assertTrue(atual.tarefas[0].perdeu_prazo)
                self.assertEqual(atual.tarefas[0].instancias_concluidas, 0)
                self.assertEqual(atual.tarefas[0].estado_tarefa, estado_pendente)
                ativacoes = [e for estado in sim.historico for e in estado.eventos
                             if e['tipo'] == 'ativacao']
                self.assertEqual(ativacoes, [{'tipo': 'ativacao', 'tick': 0, 'id_tarefa': 7}])

    def test_novos_ticks_preservam_snapshots_e_eventos_anteriores(self):
        tarefa = TCB(7, 'FF0000', 0, 1, 3, 2)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.avancar()
        primeiro = sim.historico[1]
        eventos_salvos = copy.deepcopy(primeiro.eventos)
        self.assertEqual(primeiro.eventos[:2], [
            {'tipo': 'chegada', 'tick': 0, 'id_tarefa': 7},
            {'tipo': 'ativacao', 'tick': 0, 'id_tarefa': 7},
        ])

        sim.avancar(3)
        self.assertIs(sim.historico[1], primeiro)
        self.assertEqual(primeiro.eventos, eventos_salvos)
        self.assertEqual(primeiro.tick, 1)
        self.assertEqual(primeiro.tarefas[0].instancias_concluidas, 1)
        self.assertEqual(sim.historico[0].eventos, [])
        self.assertIsNot(primeiro.eventos, sim.historico[-1].eventos)
        self.assertIn({'tipo': 'ativacao', 'tick': 3, 'id_tarefa': 7}, sim.historico[-1].eventos)

    def test_replay_reutiliza_snapshots_sem_recalcular_ou_duplicar_eventos(self):
        tarefa = TCB(7, 'FF0000', 1, 1, 3, 2)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.avancar(6)
        snapshots = list(sim.historico)
        eventos_salvos = [copy.deepcopy(estado.eventos) for estado in sim.historico]
        sim.retroceder(6)

        with patch.object(sim, '_executar_um_tick', wraps=sim._executar_um_tick) as executar:
            sim.avancar(6)
            executar.assert_not_called()
        self.assertEqual(sim.instante_atual, 6)
        self.assertEqual(len(sim.historico), len(snapshots))
        for indice, estado in enumerate(sim.historico):
            self.assertIs(estado, snapshots[indice])
            self.assertEqual(estado.eventos, eventos_salvos[indice])

    def test_edicao_descarta_futuro_e_recalcula_eventos_na_nova_linha(self):
        tarefa = TCB(7, 'FF0000', 1, 1, 3, 2)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'RM')
        sim.avancar(6)
        futuro_antigo = list(sim.historico[2:])
        eventos_antigos = [copy.deepcopy(estado.eventos) for estado in futuro_antigo]
        sim.retroceder(5)
        prefixo = list(sim.historico[:2])
        sim.modificar_tarefa_em_execucao(7, cor='00FF00')
        self.assertEqual(len(sim.historico), 2)

        sim.avancar(5)
        for indice, estado in enumerate(prefixo):
            self.assertIs(sim.historico[indice], estado)
        for indice, antigo in enumerate(futuro_antigo):
            self.assertIsNot(sim.historico[indice + 2], antigo)
            self.assertEqual(antigo.eventos, eventos_antigos[indice])
        eventos = [e for estado in sim.historico for e in estado.eventos
                   if e['tipo'] in ['chegada', 'ativacao']]
        self.assertEqual(eventos, [
            {'tipo': 'chegada', 'tick': 1, 'id_tarefa': 7},
            {'tipo': 'ativacao', 'tick': 1, 'id_tarefa': 7},
            {'tipo': 'ativacao', 'tick': 4, 'id_tarefa': 7},
        ])
        self.assertEqual(sim.historico[-1].tarefas[0].cor, '00FF00')


if __name__ == '__main__':
    unittest.main()
