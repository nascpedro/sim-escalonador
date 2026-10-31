"""Padrões compartilhados, alterações do conjunto e preservação do histórico."""
import pickle
from pathlib import Path
import tempfile
import unittest

import padroes
from engine import Simulacao
from models import Cpu, EstadoSimulacao
from parser import carregar_configuracao


class TestPadroesConjunto(unittest.TestCase):
    def nova(self):
        return Simulacao(EstadoSimulacao(0, [], [Cpu(0)], 0), 'RM')

    def test_arquivo_vazio_nos_campos_usa_padroes_com_avisos(self):
        with tempfile.TemporaryDirectory() as pasta:
            arquivo = Path(pasta) / 'entrada.txt'
            arquivo.write_text(';;\n;;;;;;\n1;2DD4BF;3;2;6;4;', encoding='utf-8')
            estado, algoritmo, avisos = carregar_configuracao(arquivo)
        self.assertEqual((algoritmo, estado.quantum, len(estado.cpus)), ('RM', 0, 2))
        a, b = estado.tarefas
        self.assertEqual((a.id, a.cor, a.ingresso, a.duracao, a.periodo, a.prazo),
                         (2, '#60A5FA', 0, 1, 10, 10))
        self.assertEqual((b.id, b.ingresso, b.duracao, b.periodo, b.prazo), (1, 3, 2, 6, 4))
        self.assertEqual(len(avisos), 9)

    def test_sugestoes_nao_limitam_quantidade_a_paleta(self):
        cores = set(padroes.CORES)
        sugestao = padroes.sugerir_tarefa(range(1, 15), cores, 7)
        self.assertEqual((sugestao['id_tarefa'], sugestao['ingresso']), (15, 7))
        self.assertNotIn(sugestao['cor'], cores)

    def test_inclusao_no_presente_completa_dez_ocorrencias(self):
        sim = self.nova()
        sim.avancar(3)
        antes = pickle.dumps(sim.historico[:3])
        sim.adicionar_tarefa(**sim.sugerir_tarefa())
        self.assertEqual(pickle.dumps(sim.historico[:3]), antes)
        final = sim.executar_completa()
        self.assertEqual((final.tick, final.tarefas[0].instancias_concluidas), (94, 10))
        chegadas = [e['tick'] for s in sim.historico for e in s.eventos if e['tipo'] == 'chegada']
        self.assertEqual(chegadas, [3])

    def test_remocao_libera_cpu_descarta_futuro_e_nao_reusa_id(self):
        sim = self.nova()
        valores = sim.sugerir_tarefa()
        valores['duracao'] = 5
        sim.adicionar_tarefa(**valores)
        sim.avancar(3)
        sim.retroceder()
        passado = pickle.dumps(sim.historico[:2])
        sim.remover_tarefa(1)
        self.assertEqual(len(sim.historico), 3)
        self.assertEqual(pickle.dumps(sim.historico[:2]), passado)
        self.assertEqual(sim.historico[-1].tarefas, [])
        self.assertIsNone(sim.historico[-1].cpus[0].id_tarefa_alocada)
        from gantt import preparar_gantt
        dados = preparar_gantt(sim)
        self.assertEqual(sum(b-a for chave, trechos in dados[4].items()
                             if chave[0] == 'execucao' for a, b in trechos), 2)
        self.assertEqual(sim.sugerir_tarefa()['id_tarefa'], 2)
        with self.assertRaises(ValueError):
            sim.adicionar_tarefa(**valores)
        sim.retroceder()
        self.assertEqual(sim.historico[sim.instante_atual].tarefas[0].id, 1)

    def test_erros_nao_alteram_estado_nem_futuro(self):
        sim = self.nova()
        sim.adicionar_tarefa(**sim.sugerir_tarefa())
        sim.avancar(2)
        sim.retroceder()
        antes = pickle.dumps(sim.historico)
        valores = sim.sugerir_tarefa()
        for campo, valor in [('id_tarefa', '01'), ('ingresso', 0), ('duracao', 0),
                ('periodo', 0), ('prazo', -1), ('cor', 'xyz'), ('cor', '#2DD4BF')]:
            with self.subTest(campo=campo, valor=valor):
                with self.assertRaises(ValueError):
                    sim.adicionar_tarefa(**(valores | {campo: valor}))
                self.assertEqual(pickle.dumps(sim.historico), antes)
        with self.assertRaises(ValueError):
            sim.remover_tarefa('ausente')
        self.assertEqual(pickle.dumps(sim.historico), antes)

    def test_remocao_no_tick_zero_permanece_no_svg(self):
        from gantt import exportar_svg, preparar_gantt
        sim = self.nova()
        sim.adicionar_tarefa(**sim.sugerir_tarefa())
        sim.remover_tarefa(1)
        dados = preparar_gantt(sim)
        self.assertEqual(dados[1], [1])
        self.assertEqual([e['tipo'] for e in dados[3]], ['inclusao', 'remocao'])
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'gantt.svg'
            exportar_svg(sim, caminho)
            self.assertIn('Tarefa 1', caminho.read_text(encoding='utf-8'))
