"""Testes do experimento; use o Python de .venv-ctk."""
import importlib.util
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import time
import unittest
import xml.etree.ElementTree as ET

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB

TEM_SVG = importlib.util.find_spec('drawsvg') is not None
TEM_CTK = TEM_SVG and importlib.util.find_spec('customtkinter') is not None


@unittest.skipUnless(TEM_SVG, 'drawsvg não instalado neste interpretador')
class TestGanttSVG(unittest.TestCase):
    def criar(self):
        return Simulacao(EstadoSimulacao(0, [TCB('ação <x>&', '123456', 0, 4, 8, 2)],
                                        [Cpu(0), Cpu(1)], 1), 'RM')

    def test_svg_vetorial_prefixo_real_sem_alterar_historico(self):
        from gantt_svg import exportar_svg
        sim = self.criar()
        sim.avancar(6)
        sim.retroceder(2)
        antes = pickle.dumps(sim.historico)
        with tempfile.TemporaryDirectory() as pasta:
            saida = exportar_svg(sim, Path(pasta) / 'gantt.svg')
            raiz = ET.parse(saida).getroot()
            texto = ''.join(raiz.itertext())
            self.assertIn('0 a 4 ticks', texto)
            self.assertNotIn('0 a 6 ticks', texto)
            self.assertIn('ação <x>&', texto)
            self.assertEqual(raiz.tag, '{http://www.w3.org/2000/svg}svg')
            self.assertFalse(raiz.findall('.//{http://www.w3.org/2000/svg}image'))
        self.assertEqual(pickle.dumps(sim.historico), antes)

    def test_suspensao_tem_padrao_e_eventos_tem_legenda(self):
        from gantt_svg import EVENTOS, exportar_svg
        sim = self.criar()
        sim.modificar_tarefa_em_execucao('ação <x>&', estado_tarefa=EstadoTarefa.SUSPENSA)
        sim.avancar(3)
        with tempfile.TemporaryDirectory() as pasta:
            raiz = ET.parse(exportar_svg(sim, Path(pasta) / 'suspensa.svg')).getroot()
        self.assertTrue(raiz.findall('.//{http://www.w3.org/2000/svg}pattern'))
        for nome, _, _ in EVENTOS.values():
            self.assertIn(nome, ''.join(raiz.itertext()))

    def test_sem_qt_matplotlib_ou_tk_na_exportacao(self):
        teste = subprocess.run([sys.executable, '-B', '-c',
            "import gantt_svg,sys; assert not any(m in sys.modules for m in ['PySide6','matplotlib','tkinter'])"],
            capture_output=True, text=True)
        self.assertEqual(teste.returncode, 0, teste.stderr)

    def test_erro_de_escrita_e_historia_sem_tarefas(self):
        from gantt_svg import exportar_svg
        sim = Simulacao(EstadoSimulacao(0, [], [], 0), 'EDF')
        with tempfile.TemporaryDirectory() as pasta:
            raiz = ET.parse(exportar_svg(sim, Path(pasta) / 'vazio.svg')).getroot()
            self.assertIn('0 a 0 ticks', ''.join(raiz.itertext()))
            with self.assertRaises(OSError):
                exportar_svg(sim, Path(pasta) / 'ausente' / 'falha.svg')

    def test_sorteio_na_trilha_das_selecionadas_e_ids_decrescentes(self):
        from unittest.mock import patch
        from gantt_svg import DesenhoSVG, desenhar_gantt, preparar_gantt, tamanho_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(i, f'{i*1000:06X}', 0, 3, 10, 10)
            for i in (1, 2, 3)], [Cpu(0), Cpu(1)], 0), 'RM')
        with patch('scheduler.random.shuffle', side_effect=lambda g: g.reverse()):
            sim.avancar()
        dados = preparar_gantt(sim)
        self.assertEqual(dados[1], [3, 2, 1])
        largura, altura, _ = tamanho_gantt(dados)
        desenho = DesenhoSVG(largura, altura)
        sorteios = []
        poligono = desenho.poligono
        def registrar(pontos, cor):
            if cor == '#6e3f97':
                sorteios.append(sum(y for _, y in pontos) / len(pontos))
            poligono(pontos, cor)
        desenho.poligono = registrar
        desenhar_gantt(dados, desenho, 'RM')
        # Tarefas 3 e 2 recebem CPUs; tarefa 1 não recebe o diamante.
        self.assertEqual(sorted(y for y in sorteios if y < 400), [156, 261])


@unittest.skipUnless(TEM_CTK, 'CustomTkinter/drawsvg não instalados neste interpretador')
class TestInterfaceCTK(unittest.TestCase):
    def setUp(self):
        import customtkinter as ctk
        from gui_ctk import JanelaSimulador
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
        from gui_ctk import DialogoTarefa
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


if __name__ == '__main__':
    unittest.main()
