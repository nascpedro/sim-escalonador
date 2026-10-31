"""Testes do Gantt Canvas/drawsvg e da interface CustomTkinter."""
import importlib.util
from pathlib import Path
import pickle
import tempfile
import time
import unittest

from models import EstadoTarefa

TEM_SVG = importlib.util.find_spec('drawsvg') is not None
TEM_CTK = TEM_SVG and importlib.util.find_spec('customtkinter') is not None


@unittest.skipUnless(TEM_CTK, 'CustomTkinter/drawsvg não instalados neste interpretador')
class TestInterface(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from gui import JanelaSimulador
        ctk.set_appearance_mode('light')
        self.pasta = tempfile.TemporaryDirectory()
        self.addCleanup(self.pasta.cleanup)
        self.caminho = Path(self.pasta.name) / 'tarefas.txt'
        self.caminho.write_text('RM;2;2\n1;123456;0;5;3;4;', encoding='utf-8')
        self.janela = JanelaSimulador()
        self.janela.withdraw()
        self.addCleanup(self.janela.fechar)
        self.assertTrue(self.janela.carregar_arquivo(self.caminho))

    def esperar(self):
        limite = time.monotonic() + 10
        while self.janela.timer is not None and time.monotonic() < limite:
            self.janela.update()
            time.sleep(.005)
        self.assertIsNone(self.janela.timer, 'Execução não terminou')

    def test_navegacao_zoom_exportacao_e_erro_preservam_estado(self):
        self.janela.avancar()
        self.janela.avancar()
        self.janela.retroceder()
        sim = self.janela.simulacao
        self.assertEqual(sim.instante_atual, 1)
        antes = pickle.dumps(sim.historico)
        self.janela.zoom(1.25)
        self.janela.ajustar()
        self.assertEqual(pickle.dumps(sim.historico), antes)
        self.assertTrue(self.janela.canvas.find_all())
        self.assertTrue(self.janela.exportar_arquivo(Path(self.pasta.name) / 'prefixo.svg'))
        self.assertEqual(pickle.dumps(sim.historico), antes)
        self.assertFalse(self.janela.carregar_arquivo(self.caminho.with_name('ausente.txt')))
        self.assertIs(self.janela.simulacao, sim)

    def test_edicao_rejeita_e_aceita_preservando_passado(self):
        from gui import DialogoTarefa
        self.janela.avancar()
        self.janela.avancar()
        self.janela.retroceder()
        sim = self.janela.simulacao
        futuro = sim.historico[-1]
        dialogo = DialogoTarefa(self.janela, self.janela.tarefa_selecionada())
        dialogo.campos['duracao'].delete(0, 'end')
        dialogo.campos['duracao'].insert(0, 'abc')
        self.assertFalse(dialogo.salvar())
        self.assertIs(sim.historico[-1], futuro)
        dialogo.campos['duracao'].delete(0, 'end')
        dialogo.campos['duracao'].insert(0, '6')
        self.assertTrue(dialogo.salvar())
        self.assertEqual(len(sim.historico), 2)
        self.assertEqual(sim.historico[0].tarefas[0].duracao, 5)
        self.assertEqual(sim.historico[1].tarefas[0].duracao, 6)

    def test_configuracao_sem_mudancas_rejeicao_e_algoritmo_no_passado(self):
        self.janela.avancar()
        self.janela.avancar()
        self.janela.retroceder()
        sim = self.janela.simulacao
        futuro = sim.historico[-1]
        self.assertTrue(self.janela.configurar())
        self.assertIs(sim.historico[-1], futuro)
        self.janela.cpus.delete(0, 'end')
        self.janela.cpus.insert(0, '0')
        self.assertFalse(self.janela.configurar())
        self.assertIs(sim.historico[-1], futuro)
        self.janela.cpus.delete(0, 'end')
        self.janela.cpus.insert(0, '1')
        self.janela.algoritmo.set('EDF')
        self.assertTrue(self.janela.configurar())
        self.janela.retroceder()
        self.assertEqual(sim.algoritmo, 'RM')
        self.assertEqual(self.janela.algoritmo.get(), 'RM')

    def test_execucao_completa_fila_e_svg_final_sem_sobrescrever(self):
        existente = self.caminho.with_name('tarefas-gantt.svg')
        existente.write_text('preservar', encoding='utf-8')
        self.janela.executar_completa()
        self.assertEqual(self.janela.botoes['abrir'].cget('state'), 'disabled')
        self.esperar()
        estado = self.janela.simulacao.historico[-1]
        self.assertEqual(estado.tick, 50)
        self.assertEqual(estado.tarefas[0].instancias_concluidas, 10)
        self.assertEqual(existente.read_text(encoding='utf-8'), 'preservar')
        self.assertTrue(self.caminho.with_name('tarefas-gantt-2.svg').exists())
        self.assertEqual(self.janela.botoes['avancar'].cget('state'), 'disabled')

    def test_suspensao_interrompe_e_falha_exportacao_preserva_resultado(self):
        sim = self.janela.simulacao
        sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.SUSPENSA)
        self.janela.executar_completa()
        self.esperar()
        self.assertIn('suspensa', self.janela.mensagem.cget('text'))
        self.assertEqual(sim.instante_atual, 0)
        self.assertFalse(self.janela.exportar_arquivo(Path(self.pasta.name) / 'ausente' / 'x.svg'))
        self.assertIs(self.janela.simulacao, sim)

    def test_fechar_cancela_execucao_pendente(self):
        self.janela.executar_completa()
        self.janela.fechar()
        self.assertIsNone(self.janela.timer)
        self.assertEqual(self.janela.simulacao.instante_atual, 0)

    def test_muitas_tarefas_tem_rolagem_e_controles_cabem_na_janela_minima(self):
        tarefas = [f'{i};{i*1000:06X};0;1;100;100;' for i in range(1, 26)]
        self.caminho.write_text('RM;0;2\n'+'\n'.join(tarefas), encoding='utf-8')
        self.janela.geometry('980x650')
        self.janela.deiconify()
        self.janela.carregar_arquivo(self.caminho)
        self.janela.update()
        x0, y0, x1, y1 = map(float, self.janela.canvas.cget('scrollregion').split())
        self.assertGreater(y1-y0, self.janela.canvas.winfo_height())
        self.janela.canvas.yview_moveto(1)
        self.assertEqual(self.janela.canvas.yview()[1], 1)
        for botao in self.janela.botoes.values():
            self.assertLessEqual(botao.winfo_x()+botao.winfo_width(), botao.master.winfo_width())
