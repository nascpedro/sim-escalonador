"""Interface QtWidgets do Projeto A baseada em ui/janela_principal.ui.

Execute: python gui.py [arquivo.txt].
A janela carrega o formulário do Qt Designer, embute o canvas Matplotlib em
graficoContainer e lê os snapshots. Edição individual e ticks usam Simulacao;
a configuração global também é validada e aplicada pelo motor.
API de teste preservada: carregar_arquivo(caminho), avancar(), retroceder(),
executar_completa(), exportar_arquivo(caminho), simulacao, tabela, figura,
canvas, barra_gantt e timer.
"""
import sys
from pathlib import Path

from PySide6.QtCore import QFile, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtUiTools import QUiLoader
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHBoxLayout, QHeaderView, QLabel, QLineEdit, QMainWindow,
    QPlainTextEdit, QPushButton, QScrollArea, QScrollBar,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure

from engine import Simulacao
from exporter import exportar_svg
from gantt import desenhar_gantt
from models import EstadoTarefa
from parser import carregar_configuracao


# Nomes do log; símbolos e posicionamento do gráfico pertencem a gantt.py.
NOMES_EVENTOS = {
    "chegada": "Chegada", "ativacao": "Ativação", "conclusao": "Conclusão",
    "perda_prazo": "Perda de prazo", "sorteio": "Sorteio", "fim_quantum": "Fim de quantum",
    "execucao": "Execução", "cpu_desligada": "CPU desligada",
}

CAMINHO_UI = Path(__file__).resolve().parent / "ui" / "janela_principal.ui"


class BarraGantt(NavigationToolbar2QT):
    # O botão próprio exporta o histórico inteiro, não só a área ampliada pelo zoom.
    toolitems = [item for item in NavigationToolbar2QT.toolitems if item[3] != "save_figure"]


def texto_evento(evento):
    tipo = evento["tipo"]
    nome = NOMES_EVENTOS.get(tipo, tipo)
    detalhes = ", ".join(f"{chave}={valor}" for chave, valor in evento.items() if chave not in ("tipo", "tick"))
    return f"t={evento['tick']} · {nome} · {detalhes}"


def tarefas_ordenadas(tarefas):
    # Numéricos decrescentes; IDs textuais em ordem estável, após os numéricos.
    return sorted(tarefas, key=lambda t: (0, -t.id) if isinstance(t.id, int) else (1, str(t.id)))


class DialogoEdicao(QDialog):
    """Valida os textos e entrega apenas os campos alterados à API do motor."""

    def __init__(self, janela, id_tarefa):
        super().__init__(janela)
        self.janela = janela
        self.id_tarefa = id_tarefa
        estado = janela.simulacao.historico[janela.simulacao.instante_atual]
        tarefa = next(t for t in estado.tarefas if t.id == id_tarefa)
        self.setWindowTitle(f"Editar tarefa {id_tarefa}")
        self.setMinimumWidth(440)
        self.setStyleSheet(janela.styleSheet())
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(
            f"Tarefa {id_tarefa} · tick {estado.tick}\n"
            "Uma edição aceita descarta somente o futuro deste instante."
        ))
        formulario = QFormLayout()
        self.campos = {}
        self.originais = {}
        for campo, rotulo in (
            ("ingresso", "Ingresso"),
            ("duracao", "Duração"),
            ("periodo", "Período"),
            ("prazo", "Prazo relativo"),
            ("cor", "Cor RGB (#RRGGBB)"),
        ):
            self.originais[campo] = getattr(tarefa, campo)
            entrada = QLineEdit(str(self.originais[campo]))
            self.campos[campo] = entrada
            formulario.addRow(rotulo, entrada)
        self.estado = QComboBox()
        for opcao in EstadoTarefa:
            self.estado.addItem(opcao.name, opcao)
        self.estado.setCurrentIndex(self.estado.findData(tarefa.estado_tarefa))
        self.originais["estado_tarefa"] = tarefa.estado_tarefa
        formulario.addRow("Estado", self.estado)
        layout.addLayout(formulario)
        layout.addWidget(QLabel(
            f"Somente leitura: CPU {tarefa.id_cpu_atual if tarefa.id_cpu_atual is not None else '—'}\n"
            f"Execução: {tarefa.tempo_exec_instancia} · fatia: {tarefa.tempo_exec_quantum}\n"
            f"Concluídas: {tarefa.instancias_concluidas}/10 · prazo absoluto: {tarefa.prazo_absoluto}"
        ))
        self.erro = QLabel("")
        self.erro.setTextFormat(Qt.TextFormat.PlainText)
        self.erro.setWordWrap(True)
        self.erro.setStyleSheet("color: #b91c1c; font-weight: 600;")
        layout.addWidget(self.erro)
        botoes = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        botoes.button(QDialogButtonBox.StandardButton.Save).setText("Salvar alterações")
        botoes.button(QDialogButtonBox.StandardButton.Cancel).setText("Cancelar")
        botoes.accepted.connect(self.accept)
        botoes.rejected.connect(self.reject)
        layout.addWidget(botoes)

    def accept(self):
        alteracoes = {}
        try:
            for campo, entrada in self.campos.items():
                texto = entrada.text().strip()
                if campo == "cor":
                    valor = "#" + texto.removeprefix("#").upper()
                else:
                    try:
                        valor = int(texto)
                    except ValueError:
                        raise ValueError(f"{campo} deve ser inteiro.") from None
                if valor != self.originais[campo]:
                    alteracoes[campo] = valor
            if self.estado.currentData() != self.originais["estado_tarefa"]:
                alteracoes["estado_tarefa"] = self.estado.currentData()
            self.janela.simulacao.modificar_tarefa_em_execucao(self.id_tarefa, **alteracoes)
        except ValueError as erro:
            self.erro.setText(str(erro))
            return
        self.janela.atualizar()
        if alteracoes:
            self.janela.mensagem.setText(
                f"Tarefa {self.id_tarefa} atualizada. O futuro foi descartado; "
                "os snapshots anteriores foram preservados."
            )
        super().accept()


class JanelaSimulador(QMainWindow):
    def __init__(self):
        super().__init__()
        self.simulacao = None
        self.caminho_configuracao = None
        self._estado_final_salvo = None
        self._ajustar_gantt = True
        self._limites_gantt = (0.0, 1.0)
        self._sincronizando_gantt = False
        self.timer = QTimer(self)
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.executar_lote)

        self._carregar_formulario_ui()
        self._configurar_grafico_matplotlib()
        self._conectar_sinais()
        self.atualizar()

    def _carregar_formulario_ui(self):
        """Carrega o desenho da janela, identifica controles e prepara a tabela."""
        self._abrir_formulario_ui()
        self._identificar_controles()
        self._configurar_tabela_tarefas()
        self.avisos.hide()
        self.resumo.setText("Nenhuma simulação carregada")
        self.mensagem.setText("Abra um arquivo de configuração para começar. Nenhum resultado foi simulado.")

    def _abrir_formulario_ui(self):
        arquivo = QFile(str(CAMINHO_UI))
        if not arquivo.open(QFile.OpenModeFlag.ReadOnly):
            raise RuntimeError(f"Não foi possível abrir o arquivo de interface: {CAMINHO_UI}")
        try:
            carregada = QUiLoader().load(arquivo)
        finally:
            arquivo.close()
        if carregada is None:
            raise RuntimeError(f"Falha ao carregar o formulário Qt Designer: {CAMINHO_UI}")

        self.setWindowTitle(carregada.windowTitle())
        self.resize(carregada.size())
        self.setMinimumSize(carregada.minimumSize())
        self.setStyleSheet(carregada.styleSheet())
        central = carregada.takeCentralWidget()
        central.setParent(self)
        self.setCentralWidget(central)
        carregada.deleteLater()

    def _identificar_controles(self):
        # Referências para os componentes definidos em ui/janela_principal.ui
        self.graficoContainer = self._obter_widget(QWidget, "graficoContainer")
        self.graficoPlaceholderLabel = self._obter_widget(QLabel, "graficoPlaceholderLabel")

        self.zoomMenosButton = self._obter_widget(QPushButton, "zoomMenosButton")
        self.zoomMaisButton = self._obter_widget(QPushButton, "zoomMaisButton")

        # Atributos públicos compatíveis com a API de testes e controle da janela
        self.botao_abrir = self._obter_widget(QPushButton, "abrirArquivoButton")
        self.botao_retroceder = self._obter_widget(QPushButton, "retrocederButton")
        self.botao_avancar = self._obter_widget(QPushButton, "avancarButton")
        self.botao_completa = self._obter_widget(QPushButton, "executarCompletaButton")
        self.botao_exportar = self._obter_widget(QPushButton, "exportarSvgButton")
        self.botao_editar = self._obter_widget(QPushButton, "editarTarefaButton")

        self.resumo = self._obter_widget(QLabel, "resumoMetaLabel")
        self.mensagem = self._obter_widget(QLabel, "mensagemStatusLabel")
        self.avisos = self._obter_widget(QLabel, "avisosLabel")
        self.eventos = self._obter_widget(QPlainTextEdit, "logEventosPlainTextEdit")
        self.tabela = self._obter_widget(QTableWidget, "tabelaConfiguracaoTarefas")

        # Painel de inspeção da tarefa selecionada (aba Simular)
        self.tarefaSelecionadaCombo = self._obter_widget(QComboBox, "tarefaSelecionadaCombo")
        self.tarefaSelecionadaCombo.setPlaceholderText("Selecione uma tarefa…")
        self.valorEstadoLabel = self._obter_widget(QLabel, "valorEstadoLabel")
        self.valorCpuLabel = self._obter_widget(QLabel, "valorCpuLabel")
        self.valorIngressoLabel = self._obter_widget(QLabel, "valorIngressoLabel")
        self.valorDuracaoLabel = self._obter_widget(QLabel, "valorDuracaoLabel")
        self.valorPeriodoLabel = self._obter_widget(QLabel, "valorPeriodoLabel")
        self.valorPrazoLabel = self._obter_widget(QLabel, "valorPrazoLabel")
        self.valorPrazoAbsolutoLabel = self._obter_widget(QLabel, "valorPrazoAbsolutoLabel")
        self.valorExecucaoLabel = self._obter_widget(QLabel, "valorExecucaoLabel")
        self.valorOcorrenciasLabel = self._obter_widget(QLabel, "valorOcorrenciasLabel")
        self.valorPerdeuPrazoLabel = self._obter_widget(QLabel, "valorPerdeuPrazoLabel")

        # Controles da aba Configurar
        self.algoritmoCombo = self._obter_widget(QComboBox, "algoritmoCombo")
        self.quantumEntrada = self._obter_widget(QLineEdit, "quantumEntrada")
        self.quantidadeCpusEntrada = self._obter_widget(QLineEdit, "quantidadeCpusEntrada")
        self.carregarArquivoConfigButton = self._obter_widget(QPushButton, "carregarArquivoConfigButton")
        self.aplicarConfiguracaoButton = self._obter_widget(QPushButton, "aplicarConfiguracaoButton")

    def _configurar_tabela_tarefas(self):
        self.tabela.setColumnCount(7)
        self.tabela.setHorizontalHeaderLabels([
            "Tarefa", "Estado", "Ingresso", "Duração", "Período", "Prazo", "Cor",
        ])
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.verticalHeader().hide()
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.tabela.setRowCount(0)

    def _obter_widget(self, tipo, nome):
        widget = self.findChild(tipo, nome)
        if widget is None:
            raise RuntimeError(f"Componente {nome!r} ({tipo.__name__}) não encontrado em {CAMINHO_UI}")
        return widget

    def _configurar_grafico_matplotlib(self):
        self.graficoPlaceholderLabel.hide()
        # O tamanho mínimo do placeholder no Designer não pode impedir que
        # a área de rolagem encolha junto com a janela.
        self.graficoContainer.setMinimumSize(0, 0)
        # A legenda é gerada por gantt.py; não manter outra com símbolos distintos.
        self._obter_widget(QLabel, "legendaGanttLabel").hide()
        self.graficoContainer.setStyleSheet("QWidget#graficoContainer { background-color: #ffffff; border: none; }")
        layout_grafico = self.graficoContainer.layout()
        if layout_grafico is None:
            layout_grafico = QVBoxLayout(self.graficoContainer)
        layout_grafico.setContentsMargins(0, 0, 0, 0)
        layout_grafico.setSpacing(4)

        self.figura = Figure(figsize=(8.8, 4.2), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figura)
        self.barra_gantt = BarraGantt(self.canvas, self)
        layout_grafico.addWidget(self.barra_gantt)
        navegacao = QHBoxLayout()
        self.botao_ajustar_gantt = QPushButton("Ajustar tudo")
        self.intervalo_gantt = QLabel("")
        navegacao.addWidget(self.botao_ajustar_gantt)
        navegacao.addStretch()
        navegacao.addWidget(self.intervalo_gantt)
        layout_grafico.addLayout(navegacao)
        self.canvas.setMinimumWidth(500)

        self.gantt = QScrollArea()
        self.gantt.setWidgetResizable(True)
        self.gantt.setWidget(self.canvas)
        layout_grafico.addWidget(self.gantt, 1)
        # Desloca o intervalo de tempo, não uma imagem com milhões de pixels.
        self.barra_tempo = QScrollBar(Qt.Orientation.Horizontal)
        self.barra_tempo.setRange(0, 0)
        self.barra_tempo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.barra_tempo.setStyleSheet("""
            QScrollBar:horizontal { background: #e2e8f0; height: 14px; }
            QScrollBar::handle:horizontal { background: #247d75; min-width: 24px; border-radius: 4px; }
            QScrollBar::handle:horizontal:disabled { background: #cbd5e1; }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0px; }
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: #e2e8f0; }
        """)
        self.barra_tempo.setToolTip("Deslocar a linha do tempo sem avançar a simulação")
        layout_grafico.addWidget(self.barra_tempo)
        self.barra_tempo.valueChanged.connect(self.deslocar_gantt)
        self.botao_ajustar_gantt.clicked.connect(self.ajustar_gantt)

    def _conectar_sinais(self):
        self.botao_abrir.clicked.connect(self.abrir_arquivo)
        self.carregarArquivoConfigButton.clicked.connect(self.abrir_arquivo)
        self.botao_retroceder.clicked.connect(self.retroceder)
        self.botao_avancar.clicked.connect(self.avancar)
        self.botao_completa.clicked.connect(self.executar_completa)
        self.botao_editar.clicked.connect(self.editar_selecionada)
        self.botao_exportar.clicked.connect(lambda: self.escolher_exportacao())

        self.zoomMenosButton.clicked.connect(lambda: self.zoom(1.25))
        self.zoomMaisButton.clicked.connect(lambda: self.zoom(0.8))
        self.aplicarConfiguracaoButton.clicked.connect(self.aplicar_configuracao_sistema)

        self.tabela.itemSelectionChanged.connect(self._ao_selecionar_na_tabela)
        self.tarefaSelecionadaCombo.currentIndexChanged.connect(self._ao_selecionar_no_combo)

    def _ao_selecionar_na_tabela(self):
        linha = self.tabela.currentRow()
        with QSignalBlocker(self.tarefaSelecionadaCombo):
            if 0 <= linha < self.tarefaSelecionadaCombo.count():
                self.tarefaSelecionadaCombo.setCurrentIndex(linha)
            else:
                self.tarefaSelecionadaCombo.setCurrentIndex(-1)
        self._atualizar_painel_inspecao()
        self.atualizar_controles()

    def _ao_selecionar_no_combo(self, indice):
        if 0 <= indice < self.tabela.rowCount():
            self.tabela.selectRow(indice)
        else:
            self.tabela.clearSelection()
            self.tabela.setCurrentCell(-1, -1)

    def _id_tarefa_selecionada(self):
        linha = self.tabela.currentRow()
        if linha >= 0:
            item = self.tabela.item(linha, 0)
            if item is not None:
                return item.data(Qt.ItemDataRole.UserRole)
        indice_combo = self.tarefaSelecionadaCombo.currentIndex()
        if indice_combo >= 0:
            return self.tarefaSelecionadaCombo.itemData(indice_combo)
        return None

    def _atualizar_painel_inspecao(self):
        id_tarefa = self._id_tarefa_selecionada()
        tarefa = None
        if self.simulacao is not None and id_tarefa is not None:
            estado = self.simulacao.historico[self.simulacao.instante_atual]
            tarefa = next((t for t in estado.tarefas if t.id == id_tarefa), None)

        if tarefa is None:
            for rotulo in (
                self.valorEstadoLabel, self.valorCpuLabel, self.valorIngressoLabel,
                self.valorDuracaoLabel, self.valorPeriodoLabel, self.valorPrazoLabel,
                self.valorPrazoAbsolutoLabel, self.valorExecucaoLabel,
                self.valorOcorrenciasLabel, self.valorPerdeuPrazoLabel,
            ):
                rotulo.setText("—")
            return

        self.valorEstadoLabel.setText(tarefa.estado_tarefa.name)
        self.valorCpuLabel.setText(str(tarefa.id_cpu_atual) if tarefa.id_cpu_atual is not None else "—")
        self.valorIngressoLabel.setText(str(tarefa.ingresso))
        self.valorDuracaoLabel.setText(str(tarefa.duracao))
        self.valorPeriodoLabel.setText(str(tarefa.periodo))
        self.valorPrazoLabel.setText(str(tarefa.prazo))
        self.valorPrazoAbsolutoLabel.setText(str(tarefa.prazo_absoluto))
        self.valorExecucaoLabel.setText(f"{tarefa.tempo_exec_instancia} / {tarefa.tempo_exec_quantum}")
        self.valorOcorrenciasLabel.setText(
            f"{tarefa.instancias_concluidas}/10 · {len(tarefa.ocorrencias_pendentes)} pendentes")
        self.valorPerdeuPrazoLabel.setText("SIM" if tarefa.perdeu_prazo else "Não")

    def zoom(self, fator):
        if self.simulacao is None or not self.figura.axes:
            return
        ax = self.figura.axes[0]
        inicio, fim = ax.get_xlim()
        largura = max(0.5, (fim - inicio) * fator)
        centro = (inicio + fim) / 2
        self._ajustar_gantt = False
        self.definir_intervalo_gantt(centro - largura / 2, centro + largura / 2)
        self.canvas.draw_idle()

    def definir_intervalo_gantt(self, inicio, fim):
        """Mantém a vista no prefixo selecionado e sincroniza a barra temporal."""
        if self.simulacao is None:
            return
        tick = self.simulacao.historico[self.simulacao.instante_atual].tick
        total = max(1, tick)
        largura = min(total, max(0.5, fim - inicio))
        inicio = min(max(0.0, inicio), total - largura)
        self._limites_gantt = (inicio, inicio + largura)
        self._sincronizando_gantt = True
        try:
            self.figura.axes[0].set_xlim(*self._limites_gantt)
            # A barra representa proporções, não pixels/ticks: sua faixa fica
            # pequena mesmo quando a simulação tem um relógio muito grande.
            pagina = min(10000, max(1, round(10000 * largura / total)))
            maximo = 0 if largura >= total else max(1, 10000 - pagina)
            with QSignalBlocker(self.barra_tempo):
                self.barra_tempo.setRange(0, maximo)
                self.barra_tempo.setPageStep(pagina)
                self.barra_tempo.setSingleStep(max(1, round(10000 / total)))
                self.barra_tempo.setValue(round(maximo * inicio / (total - largura)) if maximo else 0)
            self.barra_tempo.setEnabled(maximo > 0 and not self.timer.isActive())
            self.intervalo_gantt.setText(f"{inicio:g}–{inicio + largura:g} / {tick:g} ticks")
        finally:
            self._sincronizando_gantt = False

    def deslocar_gantt(self, posicao):
        if self.simulacao is None or not self.barra_tempo.maximum():
            return
        self._ajustar_gantt = False
        total = max(1, self.simulacao.historico[self.simulacao.instante_atual].tick)
        largura = self._limites_gantt[1] - self._limites_gantt[0]
        inicio = (total - largura) * posicao / self.barra_tempo.maximum()
        self.definir_intervalo_gantt(inicio, inicio + largura)
        self.canvas.draw_idle()

    def ajustar_gantt(self):
        if self.simulacao is None:
            return
        self._ajustar_gantt = True
        total = max(1, self.simulacao.historico[self.simulacao.instante_atual].tick)
        self.definir_intervalo_gantt(0, total)
        self.canvas.draw_idle()

    def guardar_navegacao_matplotlib(self, ax):
        """Pan/zoom da barra Matplotlib também atualiza nossa vista persistente."""
        if self._sincronizando_gantt:
            return
        self._ajustar_gantt = False
        self.definir_intervalo_gantt(*sorted(ax.get_xlim()))

    def aplicar_configuracao_sistema(self):
        if self.simulacao is None:
            self.mensagem.setText("Carregue um arquivo antes de aplicar alterações de configuração.")
            return
        try:
            try:
                quantum = int(self.quantumEntrada.text().strip())
                cpus = int(self.quantidadeCpusEntrada.text().strip())
            except ValueError:
                raise ValueError("Quantum e quantidade de CPUs devem ser inteiros.") from None
            algoritmo = "EDF" if self.algoritmoCombo.currentIndex() == 1 else "RM"
            mudou = self.simulacao.configurar_sistema(algoritmo, quantum, cpus)
        except ValueError as erro:
            self.mensagem.setText(str(erro))
            return
        self.atualizar()
        self.mensagem.setText(
            "Parâmetros atualizados. Somente o futuro deste instante foi descartado."
            if mudou else "Nenhuma alteração; histórico preservado.")

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(
            self, "Abrir configuração", "", "Texto (*.txt);;Todos os arquivos (*)"
        )
        if caminho:
            self.carregar_arquivo(caminho)

    def carregar_arquivo(self, caminho):
        try:
            estado, algoritmo, avisos = carregar_configuracao(caminho)
        except (ValueError, OSError) as erro:
            self.mensagem.setText(str(erro))
            return False
        self.simulacao = Simulacao(estado, algoritmo)
        self.caminho_configuracao = Path(caminho).resolve()
        self._estado_final_salvo = None
        self._ajustar_gantt = True
        self._limites_gantt = (0.0, 1.0)
        self.gantt.verticalScrollBar().setValue(0)
        self.avisos.setText("\n".join(avisos))
        self.avisos.setVisible(bool(avisos))
        self.tabela.clearSelection()
        self.tabela.setCurrentCell(-1, -1)
        with QSignalBlocker(self.tarefaSelecionadaCombo):
            self.tarefaSelecionadaCombo.setCurrentIndex(-1)
        self.barra_gantt.update()
        self.mensagem.setText("\n".join(avisos) or f"Arquivo carregado: {Path(caminho).name}")
        self.mensagem.setToolTip(
            f"Ao concluir, o SVG será salvo ao lado da configuração: {self.caminho_configuracao.parent}")
        self.atualizar()
        return True

    def escolher_exportacao(self):
        caminho, _ = QFileDialog.getSaveFileName(self, "Exportar Gantt", "gantt.svg", "SVG (*.svg)")
        if caminho:
            self.exportar_arquivo(caminho)

    def exportar_arquivo(self, caminho):
        """Exporta todo o histórico selecionado, independentemente do zoom da tela."""
        if self.simulacao is None:
            return False
        try:
            destino = exportar_svg(self.simulacao, caminho)
        except (OSError, ValueError) as erro:
            self.mensagem.setText(f"Erro ao exportar SVG: {erro}")
            return False
        self.mensagem.setText(f"SVG exportado: {destino}")
        return True

    def avancar(self):
        if self.simulacao is None:
            return
        self.simulacao.avancar()
        self.atualizar()
        self._salvar_resultado_final()

    def _salvar_resultado_final(self):
        """Salva uma vez ao concluir; preserva arquivos existentes e o resultado em memória."""
        estado = self.simulacao.historico[self.simulacao.instante_atual]
        if (not estado.tarefas or any(t.estado_tarefa != EstadoTarefa.FINALIZADA for t in estado.tarefas)
                or self.caminho_configuracao is None or self._estado_final_salvo is estado):
            return
        destino = self.caminho_configuracao.with_name(self.caminho_configuracao.stem + '-gantt.svg')
        numero = 2
        while destino.exists():
            destino = self.caminho_configuracao.with_name(
                f'{self.caminho_configuracao.stem}-gantt-{numero}.svg')
            numero += 1
        if self.exportar_arquivo(destino):
            self._estado_final_salvo = estado
            self.mensagem.setText(f"Execução concluída. SVG salvo: {destino}")
        else:
            self.mensagem.setText(self.mensagem.text() + ' O resultado permanece disponível para exportar novamente.')

    def retroceder(self):
        if self.simulacao is None:
            return
        self.simulacao.retroceder()
        self.atualizar()

    def editar_selecionada(self):
        id_tarefa = self._id_tarefa_selecionada()
        if self.simulacao is None or id_tarefa is None:
            self.mensagem.setText("Selecione uma tarefa para editar.")
            return
        dialogo = DialogoEdicao(self, id_tarefa)
        dialogo.exec()
        dialogo.deleteLater()

    def executar_completa(self):
        if self.simulacao is None or self.timer.isActive():
            return
        self.timer.start()
        self.mensagem.setText("Execução completa em andamento… O resultado será desenhado ao terminar.")
        self.atualizar_controles()

    def executar_lote(self):
        """Lotes são apenas uma pausa para Qt; não limitam a simulação.

        As condições de parada são as mesmas da execução completa do motor.
        Não redesenha todo o histórico a cada tick nem a cada lote.
        """
        from time import monotonic
        inicio = monotonic()
        try:
            for _ in range(32):
                estado = self.simulacao.historico[self.simulacao.instante_atual]
                pendentes = [t for t in estado.tarefas if t.estado_tarefa != EstadoTarefa.FINALIZADA]
                if not pendentes:
                    self.timer.stop()
                    self.mensagem.setText(
                        "Execução concluída. Todas as tarefas periódicas finalizaram suas dez ocorrências."
                        if estado.tarefas
                        else "Execução concluída: nenhuma tarefa periódica incluída. Consulte os avisos do arquivo."
                    )
                    self.atualizar()
                    self._salvar_resultado_final()
                    return
                if not estado.cpus:
                    raise RuntimeError("Execução completa interrompida: há tarefas pendentes, mas nenhuma CPU.")
                suspensa = next((t for t in pendentes if t.estado_tarefa == EstadoTarefa.SUSPENSA), None)
                if suspensa is not None:
                    raise RuntimeError(
                        f"Execução completa interrompida: tarefa {suspensa.id} suspensa. "
                        "Altere seu estado manualmente antes de continuar."
                    )
                self.simulacao.avancar()
                if monotonic() - inicio >= 0.012:
                    break
            self.mensagem.setText(
                f"Execução completa em andamento… tick {self.simulacao.historico[self.simulacao.instante_atual].tick}. "
                "A interface permanece disponível."
            )
        except (RuntimeError, ValueError) as erro:
            self.timer.stop()
            self.mensagem.setText(str(erro))
            self.atualizar()

    def closeEvent(self, evento):
        self.timer.stop()
        super().closeEvent(evento)

    def atualizar_controles(self):
        livre = not self.timer.isActive()
        carregada = self.simulacao is not None
        pendente = False
        if carregada:
            estado = self.simulacao.historico[self.simulacao.instante_atual]
            pendente = any(t.estado_tarefa != EstadoTarefa.FINALIZADA for t in estado.tarefas)
        tem_selecao = self._id_tarefa_selecionada() is not None

        self.botao_abrir.setEnabled(livre)
        self.carregarArquivoConfigButton.setEnabled(livre)
        self.botao_avancar.setEnabled(livre and carregada and pendente)
        self.botao_completa.setEnabled(livre and carregada and pendente)
        self.botao_retroceder.setEnabled(livre and carregada and self.simulacao.instante_atual > 0)
        self.botao_editar.setEnabled(livre and carregada and tem_selecao)
        self.tabela.setEnabled(livre)
        self.tarefaSelecionadaCombo.setEnabled(livre and carregada and self.tabela.rowCount() > 0)
        self.barra_gantt.setEnabled(livre and carregada)
        self.botao_exportar.setEnabled(livre and carregada)
        self.zoomMenosButton.setEnabled(livre and carregada)
        self.zoomMaisButton.setEnabled(livre and carregada)
        self.botao_ajustar_gantt.setEnabled(livre and carregada)
        self.barra_tempo.setEnabled(livre and carregada and self.barra_tempo.maximum() > 0)
        self.aplicarConfiguracaoButton.setEnabled(livre and carregada)
        self.algoritmoCombo.setEnabled(livre and carregada)
        self.quantumEntrada.setEnabled(livre and carregada)
        self.quantidadeCpusEntrada.setEnabled(livre and carregada)

    def atualizar(self):
        """Mostra o snapshot selecionado sem executar ou editar a simulação."""
        if self.simulacao is None:
            self._mostrar_janela_sem_simulacao()
            return

        estado = self.simulacao.historico[self.simulacao.instante_atual]
        self._atualizar_resumo_e_parametros(estado)
        self._atualizar_lista_tarefas(estado)
        self._atualizar_painel_inspecao()
        self.atualizar_controles()
        self.eventos.setPlainText(
            "\n".join(texto_evento(e) for e in estado.eventos) or "Nenhum evento neste snapshot."
        )
        self.desenhar_gantt()

    def _mostrar_janela_sem_simulacao(self):
        self.tabela.setRowCount(0)
        with QSignalBlocker(self.tarefaSelecionadaCombo):
            self.tarefaSelecionadaCombo.clear()
            self.tarefaSelecionadaCombo.setCurrentIndex(-1)
        self._atualizar_painel_inspecao()
        self.atualizar_controles()
        self.figura.clear()
        ax = self.figura.add_subplot()
        ax.text(
            0.5, 0.5, "Abra um arquivo para visualizar a linha do tempo.",
            ha="center", va="center", transform=ax.transAxes,
        )
        ax.set_axis_off()
        self.canvas.draw_idle()

    def _atualizar_resumo_e_parametros(self, estado):
        concluidas = sum(t.instancias_concluidas for t in estado.tarefas)
        desligadas = ", ".join(f"CPU {c.id_cpu}: {c.tempo_desligada}" for c in estado.cpus)
        self.resumo.setText(
            f"{self.simulacao.algoritmo} · {len(estado.cpus)} CPUs · tick {estado.tick} · "
            f"quantum {estado.quantum} · {concluidas} concluídas"
        )
        self.resumo.setToolTip(f"Ticks desligados — {desligadas}")

        with QSignalBlocker(self.algoritmoCombo):
            self.algoritmoCombo.setCurrentIndex(1 if self.simulacao.algoritmo.upper() == "EDF" else 0)
        with QSignalBlocker(self.quantumEntrada):
            self.quantumEntrada.setText(str(estado.quantum))
        with QSignalBlocker(self.quantidadeCpusEntrada):
            self.quantidadeCpusEntrada.setText(str(len(estado.cpus)))

    def _atualizar_lista_tarefas(self, estado):
        id_selecionado = self._id_tarefa_selecionada()
        tarefas = tarefas_ordenadas(estado.tarefas)

        with QSignalBlocker(self.tabela), QSignalBlocker(self.tarefaSelecionadaCombo):
            self.tabela.setRowCount(len(tarefas))
            self.tarefaSelecionadaCombo.clear()
            linha_selecionada = -1
            for linha, tarefa in enumerate(tarefas):
                self.tarefaSelecionadaCombo.addItem(f"Tarefa {tarefa.id} ({tarefa.cor})", tarefa.id)
                valores = (
                    tarefa.id,
                    tarefa.estado_tarefa.name,
                    tarefa.ingresso,
                    tarefa.duracao,
                    tarefa.periodo,
                    tarefa.prazo,
                    tarefa.cor,
                )
                for coluna, valor in enumerate(valores):
                    item = QTableWidgetItem(str(valor))
                    if coluna == 0:
                        item.setData(Qt.ItemDataRole.UserRole, tarefa.id)
                        item.setForeground(QColor(tarefa.cor))
                    self.tabela.setItem(linha, coluna, item)
                if tarefa.id == id_selecionado:
                    linha_selecionada = linha

            if linha_selecionada >= 0:
                self.tabela.selectRow(linha_selecionada)
                self.tarefaSelecionadaCombo.setCurrentIndex(linha_selecionada)
            else:
                self.tabela.clearSelection()
                self.tabela.setCurrentCell(-1, -1)
                self.tarefaSelecionadaCombo.setCurrentIndex(-1)

    def desenhar_gantt(self):
        """Redesenha dados, mas preserva a janela de tempo escolhida pelo usuário."""
        if self.simulacao is None:
            return
        ax = desenhar_gantt(self.simulacao, self.figura)
        tick = self.simulacao.historico[self.simulacao.instante_atual].tick
        if self._ajustar_gantt:
            self.definir_intervalo_gantt(0, max(1, tick))
        else:
            inicio, fim = self._limites_gantt
            self.definir_intervalo_gantt(inicio, fim)
        ax.callbacks.connect("xlim_changed", self.guardar_navegacao_matplotlib)
        # A altura segue as trilhas, não o viewport; QScrollArea agora tem
        # conteúdo vertical para percorrer em vez de comprimir todas as linhas.
        altura = max(420, round(abs(ax.get_ylim()[1] - ax.get_ylim()[0]) * 28 + 180))
        self.canvas.setMinimumHeight(altura)
        self.barra_gantt.update()
        self.canvas.draw_idle()


def main():
    # A mesma distribuição permite exportar sem abrir a janela.
    if len(sys.argv) > 1 and sys.argv[1] == '--exportar':
        from exporter import main as exportar_cli
        return exportar_cli(sys.argv[2:])
    app = QApplication(sys.argv)
    janela = JanelaSimulador()
    if len(sys.argv) > 1:
        janela.carregar_arquivo(sys.argv[1])
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
