"""Testes reais de Qt, sem janela/modal; execute com unittest.

Os arquivos temporários ficam no scratch do Hermes, não no temp do sistema.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEM_QT = (importlib.util.find_spec("PySide6") is not None
          and importlib.util.find_spec("matplotlib") is not None)
if TEM_QT:
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(TEM_QT, "PySide6/Matplotlib não instalados neste interpretador")
class TestInterface(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from gui import JanelaSimulador
        # No Windows deste ambiente, TMPDIR pode apontar ao Temp do sistema.
        # O scratch explícito mantém fixtures e evidências fora dele.
        base = Path.home() / "AppData/Local/hermes/cache/scratch"
        base.mkdir(parents=True, exist_ok=True)
        self.pasta = tempfile.TemporaryDirectory(dir=base, prefix="teste-gui-")
        self.caminho = Path(self.pasta.name) / "tarefas com espaços.txt"
        self.caminho.write_text("RM;1;2\n2;36BFA6;0;2;4;4;\n10;579BFF;1;1;5;5;\n", encoding="utf-8")
        self.janela = JanelaSimulador()

    def tearDown(self):
        self.janela.close()
        self.janela.deleteLater()
        self.app.processEvents()
        self.pasta.cleanup()

    def test_canvas_matplotlib_reutilizado_na_navegacao(self):
        from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg
        self.assertIsInstance(self.janela.canvas, FigureCanvasQTAgg)
        self.assertIs(self.janela.canvas.figure, self.janela.figura)
        self.janela.carregar_arquivo(str(self.caminho))
        figura = self.janela.figura
        self.janela.avancar()
        self.janela.retroceder()
        self.assertIs(self.janela.figura, figura)
        self.assertEqual(len(figura.axes), 1)

    def test_exportacao_svg_independe_do_zoom_e_preserva_janela(self):
        import xml.etree.ElementTree as ET
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.avancar()
        self.janela.avancar()
        self.janela.retroceder()
        ax = self.janela.figura.axes[0]
        ax.set_xlim(0.25, 0.75)
        antes = ax.get_xlim()
        saida = Path(self.pasta.name) / 'gantt.svg'
        self.assertTrue(self.janela.exportar_arquivo(saida))
        self.assertEqual(ET.parse(saida).getroot().tag, '{http://www.w3.org/2000/svg}svg')
        self.assertEqual(ax.get_xlim(), antes)
        self.assertEqual(self.janela.simulacao.instante_atual, 1)
        self.assertFalse(self.janela.exportar_arquivo(Path(self.pasta.name) / 'inexistente' / 'x.svg'))
        self.assertIn('SVG', self.janela.mensagem.text())

    def test_carregar_arquivo_real_e_controles(self):
        self.assertIsNone(self.janela.simulacao)
        self.assertFalse(self.janela.botao_avancar.isEnabled())
        self.assertFalse(self.janela.barra_gantt.isEnabled())
        self.assertFalse(self.janela.botao_exportar.isEnabled())
        self.assertTrue(self.janela.carregar_arquivo(str(self.caminho)))
        self.assertEqual(self.janela.tabela.rowCount(), 2)
        self.assertEqual(self.janela.tabela.item(0, 0).text(), "10")
        self.assertEqual(self.janela.simulacao.historico[0].tick, 0)
        self.assertTrue(self.janela.botao_avancar.isEnabled())

    def test_erro_preserva_simulacao(self):
        self.janela.carregar_arquivo(str(self.caminho))
        anterior = self.janela.simulacao
        self.caminho.write_text("RM;x;2\n", encoding="utf-8")
        self.assertFalse(self.janela.carregar_arquivo(str(self.caminho)))
        self.assertIs(self.janela.simulacao, anterior)
        self.assertIn("Linha 1", self.janela.mensagem.text())

    def test_passo_retrocesso_tabela_e_gantt_sem_futuro(self):
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.avancar()
        self.assertEqual(self.janela.simulacao.instante_atual, 1)
        self.assertIn("tick 1", self.janela.resumo.text())
        self.assertEqual(self.janela.tabela.item(1, 1).text(), "EXECUTANDO")
        ax = self.janela.figura.axes[0]
        self.assertTrue(ax.has_data())
        self.assertEqual(ax.get_xlim()[1], 1)
        self.janela.retroceder()
        self.assertEqual(self.janela.tabela.item(1, 1).text(), "AGUARDANDO")
        self.assertEqual(self.janela.figura.axes[0].get_xlim()[1], 1)
        self.assertEqual(len(self.janela.simulacao.historico), 2)
        self.janela.avancar()
        self.assertEqual(len(self.janela.simulacao.historico), 2)


    def test_edicao_rejeita_sem_apagar_futuro_e_aceita_sem_mutar_passado(self):
        from gui import DialogoEdicao
        from PySide6.QtWidgets import QDialog
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.avancar()
        self.janela.avancar()
        self.janela.retroceder()
        sim = self.janela.simulacao
        passado = sim.historico[0].tarefas[0].duracao
        futuro = sim.historico[2]
        dialogo = DialogoEdicao(self.janela, 2)
        dialogo.campos["duracao"].setText("abc")
        dialogo.accept()
        self.assertIn("inteiro", dialogo.erro.text())
        self.assertIs(sim.historico[2], futuro)
        dialogo.campos["duracao"].setText("1")
        dialogo.accept()
        self.assertIn("tempo já executado", dialogo.erro.text())
        self.assertIs(sim.historico[2], futuro)
        dialogo.campos["duracao"].setText("3")
        dialogo.accept()
        self.assertEqual(dialogo.result(), QDialog.DialogCode.Accepted)
        self.assertEqual(len(sim.historico), 2)
        self.assertEqual(sim.historico[1].tarefas[0].duracao, 3)
        self.assertEqual(sim.historico[0].tarefas[0].duracao, passado)
        dialogo.deleteLater()

    def test_edicao_sem_alteracao_preserva_futuro(self):
        from gui import DialogoEdicao
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.avancar()
        self.janela.retroceder()
        sim = self.janela.simulacao
        dialogo = DialogoEdicao(self.janela, 2)
        dialogo.accept()
        self.assertEqual(len(sim.historico), 2)
        dialogo.deleteLater()


    def esperar_lote(self):
        import time
        from PySide6.QtTest import QTest
        limite = time.monotonic() + 10
        while self.janela.timer.isActive() and time.monotonic() < limite:
            QTest.qWait(5)
        self.assertFalse(self.janela.timer.isActive(), "Execução Qt não terminou")

    def test_execucao_completa_timer_termina_e_desabilita_controles(self):
        from models import EstadoTarefa
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.executar_completa()
        self.assertTrue(self.janela.timer.isActive())
        self.assertFalse(self.janela.botao_avancar.isEnabled())
        self.assertFalse(self.janela.botao_abrir.isEnabled())
        self.assertFalse(self.janela.botao_completa.isEnabled())
        self.esperar_lote()
        sim = self.janela.simulacao
        final = sim.historico[sim.instante_atual]
        self.assertTrue(all(t.estado_tarefa == EstadoTarefa.FINALIZADA for t in final.tarefas))
        self.assertEqual(sum(t.instancias_concluidas for t in final.tarefas), 20)
        self.assertIn("concluída", self.janela.mensagem.text())
        self.assertTrue(self.janela.botao_abrir.isEnabled())
        self.assertFalse(self.janela.botao_avancar.isEnabled())
        self.assertTrue(self.janela.botao_retroceder.isEnabled())

    def test_execucao_interrompe_suspensa_e_sem_cpu(self):
        from models import EstadoTarefa
        self.janela.carregar_arquivo(str(self.caminho))
        sim = self.janela.simulacao
        sim.modificar_tarefa_em_execucao(2, estado_tarefa=EstadoTarefa.SUSPENSA)
        self.janela.executar_completa()
        self.esperar_lote()
        self.assertIn("suspensa", self.janela.mensagem.text())
        self.assertEqual(sim.instante_atual, 0)
        # Estado sem CPU só é produzido aqui como fixture, não pela UI/parser.
        sim.modificar_tarefa_em_execucao(2, estado_tarefa=EstadoTarefa.PRONTA)
        sim.historico[0].cpus = []
        self.janela.executar_completa()
        self.esperar_lote()
        self.assertIn("nenhuma CPU", self.janela.mensagem.text())

    def test_apenas_aperiodicas_vazio_sem_crash(self):
        self.caminho.write_text("EDF;0;1\na;FFAA22;0;1;0;3;\n", encoding="utf-8")
        self.assertTrue(self.janela.carregar_arquivo(str(self.caminho)))
        self.assertIn("aperiódica ignorada", self.janela.mensagem.text())
        self.assertEqual(self.janela.tabela.rowCount(), 0)
        self.janela.executar_completa()
        self.esperar_lote()
        self.assertIn("aperiódica ignorada", self.janela.avisos.text())
        self.assertEqual(self.janela.simulacao.instante_atual, 0)

    def test_fechar_interrompe_timer(self):
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.executar_completa()
        self.janela.close()
        self.assertFalse(self.janela.timer.isActive())


    def test_gantt_marcadores_timestamps_suspensao_e_ids_textuais(self):
        from models import EstadoTarefa
        self.caminho.write_text("RM;1;1\n2;36BFA6;0;3;4;1;\n10;579BFF;0;3;4;1;\na;FFAA22;20;1;30;3;\n", encoding="utf-8")
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.avancar()
        from matplotlib.text import Text
        textos = [t.get_text().casefold() for t in self.janela.figura.findobj(Text)]
        for nome in ("Chegada", "Ativação", "Sorteio", "Fim de quantum", "Perda de prazo"):
            self.assertTrue(any(nome.casefold() in texto for texto in textos), nome)
        self.assertEqual([self.janela.tabela.item(i, 0).text() for i in range(3)], ["10", "2", "a"])
        sim = self.janela.simulacao
        sim.modificar_tarefa_em_execucao(2, estado_tarefa=EstadoTarefa.SUSPENSA)
        self.janela.avancar()
        self.assertEqual(self.janela.figura.axes[0].get_xlim()[1], 2)
        self.assertIn("SUSPENSA", [self.janela.tabela.item(i, 1).text() for i in range(3)])

    def test_lotes_devolvem_controle_ao_qt_e_so_desenham_no_final(self):
        from PySide6.QtCore import QTimer
        self.caminho.write_text("EDF;0;1\n1;36BFA6;0;1;25;25;\n", encoding="utf-8")
        self.janela.carregar_arquivo(str(self.caminho))
        desenhos = []
        desenhar = self.janela.desenhar_gantt
        def observar_desenho():
            desenhos.append(self.janela.simulacao.instante_atual)
            desenhar()
        self.janela.desenhar_gantt = observar_desenho
        pulsos = []
        pulso = QTimer(self.janela)
        pulso.timeout.connect(lambda: pulsos.append(True))
        pulso.start(1)
        self.janela.executar_completa()
        self.esperar_lote()
        pulso.stop()
        self.assertGreater(len(pulsos), 1)
        self.assertEqual(desenhos, [226])

    def test_cor_editada_sem_hash_e_canonica_e_selecao_habilita_edicao(self):
        from gui import DialogoEdicao
        self.janela.carregar_arquivo(str(self.caminho))
        self.assertFalse(self.janela.botao_editar.isEnabled())
        self.janela.tabela.selectRow(1)
        self.assertTrue(self.janela.botao_editar.isEnabled())
        dialogo = DialogoEdicao(self.janela, 2)
        dialogo.campos["cor"].setText("aabbcc")
        dialogo.accept()
        self.assertEqual(self.janela.simulacao.historico[0].tarefas[0].cor, "#AABBCC")
        self.janela.avancar()
        from matplotlib.colors import to_rgba
        cores = [tuple(cor) for colecao in self.janela.figura.axes[0].collections
                 for cor in colecao.get_facecolors()]
        self.assertIn(to_rgba("#aabbcc"), cores)
        dialogo.deleteLater()

    def carregar_historia_para_navegar(self):
        self.caminho.write_text("RM;0;2\n1;36BFA6;0;1;25;25;\n2;579BFF;0;3;30;30;\n", encoding="utf-8")
        self.janela.carregar_arquivo(str(self.caminho))
        sim = self.janela.simulacao
        assert sim is not None
        for _ in range(60):
            sim.avancar()
        self.janela.atualizar()
        return sim

    def test_barra_temporal_percorre_historico_sem_alterar_simulacao(self):
        import pickle
        sim = self.carregar_historia_para_navegar()
        antes = pickle.dumps(sim.historico)
        self.janela.zoomMaisButton.click()
        barra = self.janela.barra_tempo
        self.assertGreater(barra.maximum(), 0)
        largura = self.janela.figura.axes[0].get_xlim()[1] - self.janela.figura.axes[0].get_xlim()[0]
        barra.setValue(barra.maximum())
        self.assertAlmostEqual(self.janela.figura.axes[0].get_xlim()[1], 60)
        barra.setValue(0)
        self.assertAlmostEqual(self.janela.figura.axes[0].get_xlim()[0], 0)
        self.assertAlmostEqual(self.janela.figura.axes[0].get_xlim()[1], largura)
        self.assertEqual(pickle.dumps(sim.historico), antes)
        self.assertEqual(sim.instante_atual, 60)

    def test_zoom_preservado_ao_avancar_retroceder_e_redimensionar(self):
        self.carregar_historia_para_navegar()
        self.janela.zoom(.25)
        self.janela.barra_tempo.setValue(0)
        limites = self.janela.figura.axes[0].get_xlim()
        self.janela.avancar()
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), limites)
        self.janela.retroceder()
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), limites)
        self.janela.resize(1350, 850)
        self.app.processEvents()
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), limites)

    def test_retrocesso_limita_vista_e_ajustar_tudo_mostra_so_prefixo(self):
        sim = self.carregar_historia_para_navegar()
        self.janela.zoom(.2)
        self.janela.barra_tempo.setValue(self.janela.barra_tempo.maximum())
        self.janela.retroceder()
        self.assertAlmostEqual(self.janela.figura.axes[0].get_xlim()[1], 59)
        self.assertAlmostEqual(self.janela.figura.axes[0].get_xlim()[1] - self.janela.figura.axes[0].get_xlim()[0], 12)
        self.janela.botao_ajustar_gantt.click()
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), (0, 59))
        self.assertEqual(self.janela.barra_tempo.maximum(), 0)
        self.assertEqual(len(sim.historico), 61)
        self.janela.retroceder()
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), (0, 58))

    def test_muitas_tarefas_tem_rolagem_vertical_real(self):
        linhas = [f"{i};{1000 + i * 700:06X};0;1;100;100;" for i in range(1, 26)]
        self.caminho.write_text("RM;0;2\n" + "\n".join(linhas), encoding="utf-8")
        self.janela.resize(self.janela.minimumSize())
        self.janela.show()
        self.janela.carregar_arquivo(str(self.caminho))
        self.app.processEvents()
        container = self.janela.graficoContainer
        self.assertTrue(container.parentWidget().rect().contains(container.geometry()))
        barra = self.janela.gantt.verticalScrollBar()
        self.assertGreater(barra.maximum(), 0)
        self.assertGreater(self.janela.canvas.height(), self.janela.gantt.viewport().height())
        barra.setValue(barra.maximum())
        self.assertEqual(barra.value(), barra.maximum())

    def test_exportacao_integral_apos_navegar_nao_altera_vista(self):
        import pickle
        import xml.etree.ElementTree as ET
        sim = self.carregar_historia_para_navegar()
        self.janela.retroceder()
        self.janela.zoom(.2)
        self.janela.barra_tempo.setValue(0)
        limites = self.janela.figura.axes[0].get_xlim()
        antes = pickle.dumps(sim.historico)
        saida = Path(self.pasta.name) / 'navegado.svg'
        self.assertTrue(self.janela.exportar_arquivo(saida))
        texto = ' '.join(ET.parse(saida).getroot().itertext())
        self.assertIn('histórico: 0 a 59 ticks', texto)
        self.assertNotIn('histórico: 0 a 60 ticks', texto)
        self.assertEqual(self.janela.figura.axes[0].get_xlim(), limites)
        self.assertEqual(pickle.dumps(sim.historico), antes)

    def test_redesenho_nao_acumula_eixos_ou_troca_canvas(self):
        self.janela.carregar_arquivo(str(self.caminho))
        canvas = self.janela.canvas
        for _ in range(4):
            self.janela.avancar()
            self.app.processEvents()
        self.janela.retroceder()
        self.janela.avancar()
        self.assertIs(self.janela.canvas, canvas)
        self.assertEqual(len(self.janela.figura.axes), 1)
        self.assertEqual(self.janela.figura.axes[0].get_xlim()[1], 4)

    def test_configuracao_sem_mudancas_invalida_e_quantum_grande(self):
        self.caminho.write_text('RM;1000000000000;2\n1;123456;0;4;10;10;', encoding='utf-8')
        self.janela.carregar_arquivo(self.caminho)
        sim = self.janela.simulacao
        self.assertEqual(self.janela.quantumEntrada.text(), '1000000000000')
        sim.avancar(3)
        sim.retroceder()
        self.janela.atualizar()
        futuro = sim.historico[-1]
        self.janela.aplicar_configuracao_sistema()
        self.assertIs(sim.historico[-1], futuro)
        self.janela.quantumEntrada.setText('abc')
        self.janela.aplicar_configuracao_sistema()
        self.assertIn('inteiros', self.janela.mensagem.text())
        self.assertIs(sim.historico[-1], futuro)
        self.janela.quantumEntrada.setText('2')
        self.janela.quantidadeCpusEntrada.setText('1')
        self.janela.algoritmoCombo.setCurrentIndex(1)
        self.janela.aplicar_configuracao_sistema()
        self.assertEqual(sim.algoritmo, 'EDF')
        self.assertEqual(len(sim.historico), 3)
        self.janela.retroceder()
        self.assertEqual(self.janela.algoritmoCombo.currentIndex(), 0)

    def test_imagem_final_automatica_por_passo_e_por_execucao_sem_sobrescrever(self):
        self.caminho.write_text('RM;0;1\n1;123456;0;1;1;1;', encoding='utf-8')
        destino = self.caminho.with_name(self.caminho.stem + '-gantt.svg')
        destino.write_text('preservar', encoding='utf-8')
        self.janela.carregar_arquivo(self.caminho)
        for _ in range(10):
            self.janela.avancar()
        saida = self.caminho.with_name(self.caminho.stem + '-gantt-2.svg')
        self.assertTrue(saida.is_file())
        self.assertEqual(destino.read_text(encoding='utf-8'), 'preservar')
        self.assertIn('SVG salvo', self.janela.mensagem.text())
        self.janela.carregar_arquivo(self.caminho)
        self.janela.executar_completa()
        self.esperar_lote()
        self.assertTrue(self.caminho.with_name(self.caminho.stem + '-gantt-3.svg').is_file())

    def test_falha_imagem_final_preserva_resultado_para_nova_exportacao(self):
        from unittest.mock import patch
        self.janela.carregar_arquivo(self.caminho)
        sim = self.janela.simulacao
        sim.executar_completa()
        sim.retroceder()
        with patch('gui.exportar_svg', side_effect=PermissionError('destino sem permissao')):
            self.janela.avancar()
        self.assertIn('permanece disponível', self.janela.mensagem.text())
        self.assertEqual(sum(t.instancias_concluidas for t in sim.historico[-1].tarefas), 20)
        self.assertTrue(self.janela.exportar_arquivo(Path(self.pasta.name) / 'outro.svg'))


if __name__ == "__main__":
    unittest.main()
