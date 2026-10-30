import copy
import unittest

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa


class TesteEdicaoTarefas(unittest.TestCase):
    def criar_simulacao(self):
        tarefas = [TCB(1, 'FF0000', 0, 4, 10, 8), TCB(2, '00FF00', 0, 3, 20, 10)]
        sim = Simulacao(EstadoSimulacao(0, tarefas, [Cpu(4)], 0), 'RM')
        sim.avancar(3)
        sim.retroceder(2)
        return sim

    def conteudo(self, sim):
        return copy.deepcopy([
            (e.tick, [vars(t) for t in e.tarefas], [vars(c) for c in e.cpus], e.eventos)
            for e in sim.historico
        ])

    def rejeita_sem_modificar(self, sim, id_tarefa, motivo, **alteracoes):
        snapshots = list(sim.historico)
        conteudo = self.conteudo(sim)
        indice = sim.instante_atual
        with self.assertRaisesRegex(ValueError, motivo):
            sim.modificar_tarefa_em_execucao(id_tarefa, **alteracoes)
        self.assertEqual(sim.instante_atual, indice)
        self.assertEqual(self.conteudo(sim), conteudo)
        self.assertEqual(len(sim.historico), len(snapshots))
        for atual, anterior in zip(sim.historico, snapshots):
            self.assertIs(atual, anterior)

    def test_edita_apenas_campos_solicitados_preservando_passado(self):
        sim = self.criar_simulacao()
        passado = self.conteudo(sim)[0]
        sim.modificar_tarefa_em_execucao(1, cor='#123456', duracao=12)
        self.assertEqual(len(sim.historico), 2)
        tarefa = sim.historico[1].tarefas[0]
        self.assertEqual(tarefa.cor, '#123456')
        self.assertEqual(tarefa.duracao, 12)  # Maior que período é permitido.
        self.assertEqual(tarefa.periodo, 10)
        self.assertEqual(tarefa.tempo_exec_instancia, 1)
        self.assertEqual(tarefa.id_cpu_atual, 4)
        self.assertEqual(self.conteudo(sim)[0], passado)
        sim.avancar()
        self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_instancia, 2)

    def test_rejeita_alteracoes_invalidas_sem_apagar_futuro(self):
        casos = [
            ('ingresso', -1), ('duracao', 0), ('periodo', 0), ('prazo', 0),
            ('duracao', True), ('cor', 'GGGGGG'), ('cor', '#00ff00'),
            ('estado_tarefa', 'PRONTA'), ('id', 9), ('id_cpu_atual', 999),
            ('prazo_absoluto', 99), ('instancias_concluidas', 10),
            ('tempo_exec_instancia', 0), ('perdeu_prazo', False)
        ]
        for campo, valor in casos:
            with self.subTest(campo=campo):
                self.rejeita_sem_modificar(self.criar_simulacao(), 1, campo, **{campo: valor})
        self.rejeita_sem_modificar(self.criar_simulacao(), 99, 'não encontrada', cor='123456')

    def test_suspender_libera_cpu_e_retomar_preserva_progresso(self):
        sim = self.criar_simulacao()
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.SUSPENSA)
        atual = sim.historico[1]
        self.assertIsNone(atual.cpus[0].id_tarefa_alocada)
        self.assertIsNone(atual.tarefas[0].id_cpu_atual)
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.PRONTA)
        sim.avancar()
        self.assertEqual(sim.historico[2].tarefas[0].tempo_exec_instancia, 2)

    def test_executar_escolhe_cpu_sem_roubar_de_outra_tarefa(self):
        sim = self.criar_simulacao()
        self.rejeita_sem_modificar(sim, 2, 'CPU livre', estado_tarefa=EstadoTarefa.EXECUTANDO)
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.PRONTA)
        sim.modificar_tarefa_em_execucao(2, estado_tarefa=EstadoTarefa.EXECUTANDO)
        atual = sim.historico[1]
        self.assertEqual(atual.tarefas[1].id_cpu_atual, 4)
        self.assertEqual(atual.cpus[0].id_tarefa_alocada, 2)

    def test_prazo_absoluto_e_atualizado_pelo_motor(self):
        sim = self.criar_simulacao()
        sim.modificar_tarefa_em_execucao(1, prazo=12)
        self.assertEqual(sim.historico[1].tarefas[0].prazo_absoluto, 12)
        # Depois da primeira conclusão, a próxima ativação é no tick 10.
        sim.avancar(10)
        sim.modificar_tarefa_em_execucao(1, prazo=15)
        self.assertEqual(sim.historico[11].tarefas[0].prazo_absoluto, 25)

    def test_rejeita_mudancas_incompativeis_com_ocorrencia_atual(self):
        sim = self.criar_simulacao()
        self.rejeita_sem_modificar(sim, 1, 'duracao', duracao=1)
        self.rejeita_sem_modificar(sim, 1, 'ingresso', ingresso=5)
        self.rejeita_sem_modificar(sim, 1, 'dez', estado_tarefa=EstadoTarefa.FINALIZADA)

    def test_edita_tarefa_ainda_nao_ativada_sem_informar_dados_internos(self):
        tarefa = TCB('tarefa', 'FF0000', 5, 2, 10, 5)
        sim = Simulacao(EstadoSimulacao(0, [tarefa], [Cpu(0)], 0), 'EDF')
        self.rejeita_sem_modificar(sim, 'tarefa', 'ingresso', estado_tarefa=EstadoTarefa.PRONTA)
        sim.modificar_tarefa_em_execucao('tarefa', ingresso=0, prazo=12)
        self.assertEqual(sim.historico[0].tarefas[0].prazo_absoluto, 12)
        sim.executar_completa()
        self.assertEqual(sim.historico[-1].tarefas[0].instancias_concluidas, 10)
        self.rejeita_sem_modificar(sim, 'tarefa', 'dez', estado_tarefa=EstadoTarefa.PRONTA)

    def test_ativar_manualmente_nova_ocorrencia_reinicia_progresso(self):
        sim = self.criar_simulacao()
        sim.avancar(3)
        self.assertEqual(sim.historico[4].tarefas[0].instancias_concluidas, 1)
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.PRONTA)
        tarefa = sim.historico[4].tarefas[0]
        self.assertEqual(tarefa.tempo_exec_instancia, 0)
        self.assertEqual(tarefa.prazo_absoluto, 12)
        sim.avancar()
        self.assertEqual(sim.historico[5].tarefas[0].tempo_exec_instancia, 1)

    def test_sem_campos_nao_descarta_futuro(self):
        sim = self.criar_simulacao()
        antes = self.conteudo(sim)
        sim.modificar_tarefa_em_execucao(1)
        self.assertEqual(self.conteudo(sim), antes)


if __name__ == '__main__':
    unittest.main()
