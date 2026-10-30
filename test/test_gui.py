"""Testes reais de Qt, sem janela/modal; execute com unittest.

Os arquivos temporários ficam no scratch do Hermes, não no temp do sistema.
"""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
TEM_QT = importlib.util.find_spec("PySide6") is not None
if TEM_QT:
    from PySide6.QtWidgets import QApplication


@unittest.skipUnless(TEM_QT, "PySide6 não instalado neste interpretador")
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

    def test_carregar_arquivo_real_e_controles(self):
        self.assertIsNone(self.janela.simulacao)
        self.assertFalse(self.janela.botao_avancar.isEnabled())
        self.assertTrue(all(not b.isEnabled() for b in self.janela.botoes_zoom))
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
        blocos = [i for i in self.janela.cena.items() if i.data(0) == "execucao"]
        self.assertEqual(len(blocos), 1)
        self.assertIn("CPU 0", blocos[0].toolTip())
        self.assertTrue(any(i.data(0) == "chegada" for i in self.janela.cena.items()))
        self.janela.retroceder()
        self.assertEqual(self.janela.tabela.item(1, 1).text(), "AGUARDANDO")
        self.assertFalse(any(i.data(0) == "execucao" for i in self.janela.cena.items()))
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
        tipos = {i.data(0) for i in self.janela.cena.items()}
        self.assertTrue({"chegada", "ativacao", "sorteio", "fim_quantum", "perda_prazo"} <= tipos)
        for item in self.janela.cena.items():
            if item.data(0) in ("chegada", "ativacao", "sorteio"):
                self.assertIn("t=0", item.toolTip())
            if item.data(0) in ("fim_quantum", "perda_prazo"):
                self.assertIn("t=1", item.toolTip())
        self.assertEqual([self.janela.tabela.item(i, 0).text() for i in range(3)], ["10", "2", "a"])
        sim = self.janela.simulacao
        sim.modificar_tarefa_em_execucao(2, estado_tarefa=EstadoTarefa.SUSPENSA)
        self.janela.avancar()
        self.assertTrue(any(i.data(0) == "suspensa" for i in self.janela.cena.items()))

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
        bloco = next(i for i in self.janela.cena.items() if i.data(0) == "execucao")
        self.assertEqual(bloco.brush().color().name(), "#aabbcc")
        dialogo.deleteLater()

    def test_redesenho_preserva_posicao_do_gantt(self):
        self.caminho.write_text(
            "RM;3;2\n1;2DD4BF;2;2;8;4;\n2;60A5FA;0;4;12;8;\n3;C084FC;0;5;20;12;\n",
            encoding="utf-8",
        )
        self.janela.show()
        self.app.processEvents()
        self.janela.carregar_arquivo(str(self.caminho))
        self.janela.gantt.verticalScrollBar().setValue(0)
        for _ in range(12):
            self.janela.avancar()
        self.janela.retroceder()
        self.janela.avancar()
        from gui import DialogoEdicao
        self.janela.tabela.selectRow(2)
        dialogo = DialogoEdicao(self.janela, 1)
        dialogo.campos['prazo'].setText('8')
        dialogo.accept()
        self.app.processEvents()
        self.assertEqual(self.janela.gantt.verticalScrollBar().value(), 0)
        dialogo.deleteLater()


if __name__ == "__main__":
    unittest.main()
