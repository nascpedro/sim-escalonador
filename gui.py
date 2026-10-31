"""Interface QtWidgets do Projeto A. Execute: python gui.py [arquivo.txt].

A janela lê snapshots; somente Simulacao pode editar tarefas ou executar ticks.
API de teste: carregar_arquivo(caminho), avancar(), retroceder(),
executar_completa(), simulacao, tabela, figura, canvas e timer.
O mesmo desenho Matplotlib é usado na janela e na exportação SVG.
"""
import sys
from pathlib import Path

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QFileDialog,
    QFormLayout, QHeaderView, QHBoxLayout,
    QLabel, QLineEdit, QMainWindow, QPlainTextEdit, QPushButton, QSplitter,
    QScrollArea, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

from engine import Simulacao
from models import EstadoTarefa
from parser import carregar_configuracao
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT
from matplotlib.figure import Figure
from gantt import desenhar_gantt
from exporter import exportar_svg


# Nomes do log; símbolos e posicionamento do gráfico pertencem a gantt.py.
NOMES_EVENTOS = {
    "chegada": "Chegada", "ativacao": "Ativação", "conclusao": "Conclusão",
    "perda_prazo": "Perda de prazo", "sorteio": "Sorteio", "fim_quantum": "Fim de quantum",
    "execucao": "Execução", "cpu_desligada": "CPU desligada",
}


class BarraGantt(NavigationToolbar2QT):
    # O botão próprio exporta o histórico inteiro, não só a área ampliada pelo zoom.
    toolitems = [item for item in NavigationToolbar2QT.toolitems if item[3] != 'save_figure']


ESTILO = """
QWidget { background: #101720; color: #E7EDF6; font: 10pt 'Segoe UI'; }
QLabel#titulo { font-size: 19pt; font-weight: 700; color: #F0F6FF; }
QLabel#resumo { color: #71DCC9; font-size: 11pt; padding: 5px 0; }
QLabel#mensagem { background: #1A2635; border: 1px solid #33465B; padding: 10px; border-radius: 6px; }
QPushButton { background: #223249; border: 1px solid #405974; border-radius: 6px; padding: 8px 13px; }
QPushButton:hover { background: #304964; border-color: #60D4C2; }
QPushButton:disabled { color: #6B7C90; background: #18212D; border-color: #273444; }
QPushButton#primario { background: #176E68; border-color: #3DBDAA; }
QTableWidget, QPlainTextEdit, QScrollArea { background: #131D2A; border: 1px solid #304255; border-radius: 5px; }
QTableWidget { gridline-color: #28384A; alternate-background-color: #192638; selection-background-color: #254F64; }
QTableWidget::item:selected { background: #254F64; color: #F0F6FF; }
QTableWidget::item:focus { outline: none; }
QHeaderView::section { background: #223248; padding: 7px; border: none; border-right: 1px solid #33465B; }
QSplitter::handle { background: #243449; height: 5px; }
QLineEdit, QComboBox { padding: 6px; border: 1px solid #405974; border-radius: 4px; background: #182436; }
"""


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
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Tarefa {id_tarefa} · tick {estado.tick}\nUma edição aceita descarta somente o futuro deste instante."))
        formulario = QFormLayout()
        self.campos = {}
        self.originais = {}
        for campo, rotulo in (("ingresso", "Ingresso"), ("duracao", "Duração"), ("periodo", "Período"), ("prazo", "Prazo relativo"), ("cor", "Cor RGB (#RRGGBB)")):
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
        layout.addWidget(QLabel(f"Somente leitura: CPU {tarefa.id_cpu_atual if tarefa.id_cpu_atual is not None else '—'}\nExecução: {tarefa.tempo_exec_instancia} · fatia: {tarefa.tempo_exec_quantum}\nConcluídas: {tarefa.instancias_concluidas}/10 · prazo absoluto: {tarefa.prazo_absoluto}"))
        self.erro = QLabel("")
        self.erro.setTextFormat(Qt.TextFormat.PlainText)
        self.erro.setWordWrap(True)
        self.erro.setStyleSheet("color: #FF9CAA;")
        layout.addWidget(self.erro)
        botoes = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
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
            self.janela.mensagem.setText(f"Tarefa {self.id_tarefa} atualizada. O futuro foi descartado; os snapshots anteriores foram preservados.")
        super().accept()


class JanelaSimulador(QMainWindow):
    def __init__(self):
        super().__init__()
        self.simulacao = None
        self.timer = QTimer(self)
        self.timer.setInterval(1)
        self.timer.timeout.connect(self.executar_lote)
        self.setWindowTitle("Simulador de escalonamento • Projeto A")
        self.resize(1280, 880)
        self.setStyleSheet(ESTILO)
        central = QWidget()
        self.setCentralWidget(central)
        self.layout = QVBoxLayout(central)
        self.layout.setContentsMargins(22, 18, 22, 18)
        self.layout.setSpacing(12)
        titulo = QLabel("Simulador de escalonamento")
        titulo.setObjectName("titulo")
        self.layout.addWidget(titulo)
        self.layout.addWidget(QLabel("PROJETO A   /   RM e EDF preemptivos   /   Histórico por tick"))
        controles = QHBoxLayout()
        self.botao_abrir = QPushButton("Abrir arquivo…")
        self.botao_abrir.setObjectName("primario")
        self.botao_abrir.clicked.connect(self.abrir_arquivo)
        self.botao_retroceder = QPushButton("← Retroceder")
        self.botao_retroceder.clicked.connect(self.retroceder)
        self.botao_avancar = QPushButton("Avançar →")
        self.botao_avancar.clicked.connect(self.avancar)
        self.botao_editar = QPushButton("Editar tarefa selecionada")
        self.botao_editar.clicked.connect(self.editar_selecionada)
        self.botao_completa = QPushButton("Execução completa")
        self.botao_completa.clicked.connect(self.executar_completa)
        self.botao_exportar = QPushButton("Exportar SVG…")
        self.botao_exportar.clicked.connect(lambda: self.escolher_exportacao())
        for botao in (self.botao_abrir, self.botao_retroceder, self.botao_avancar, self.botao_completa, self.botao_editar, self.botao_exportar):
            controles.addWidget(botao)
        controles.addStretch()
        self.layout.addLayout(controles)
        self.resumo = QLabel("Nenhuma simulação carregada")
        self.resumo.setObjectName("resumo")
        self.layout.addWidget(self.resumo)
        self.divisor = QSplitter(Qt.Orientation.Vertical)
        self.layout.addWidget(self.divisor, 1)
        self.tabela = QTableWidget(0, 13)
        self.tabela.setHorizontalHeaderLabels([
            "Tarefa", "Estado", "CPU", "Ingresso", "Duração", "Período", "Prazo",
            "Prazo abs.", "Exec. atual", "Fatia", "Concluídas", "Perdeu prazo", "Cor",
        ])
        self.tabela.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.tabela.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.tabela.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.tabela.setAlternatingRowColors(True)
        self.tabela.itemSelectionChanged.connect(self.atualizar_controles)
        self.tabela.verticalHeader().hide()
        self.tabela.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.divisor.addWidget(self.tabela)
        painel_gantt = QWidget()
        gantt_layout = QVBoxLayout(painel_gantt)
        gantt_layout.setContentsMargins(0, 0, 0, 0)
        gantt_layout.addWidget(QLabel("LINHA DO TEMPO · Matplotlib · número no bloco = CPU"))
        self.figura = Figure(figsize=(11, 5), dpi=100)
        self.canvas = FigureCanvasQTAgg(self.figura)
        self.barra_gantt = BarraGantt(self.canvas, self)
        gantt_layout.addWidget(self.barra_gantt)
        self.gantt = QScrollArea()
        self.gantt.setWidgetResizable(True)
        self.gantt.setWidget(self.canvas)
        gantt_layout.addWidget(self.gantt, 1)
        self.divisor.addWidget(painel_gantt)
        self.eventos = QPlainTextEdit()
        self.eventos.setReadOnly(True)
        self.eventos.setPlaceholderText("Os eventos do intervalo selecionado aparecerão aqui.")
        self.divisor.addWidget(self.eventos)
        self.divisor.setSizes([210, 390, 110])
        self.mensagem = QLabel("Abra um arquivo de configuração para começar. Nenhum resultado foi simulado.")
        self.mensagem.setObjectName("mensagem")
        self.mensagem.setWordWrap(True)
        self.mensagem.setTextFormat(Qt.TextFormat.PlainText)
        self.layout.addWidget(self.mensagem)
        self.avisos = QLabel("")
        self.avisos.setTextFormat(Qt.TextFormat.PlainText)
        self.avisos.setWordWrap(True)
        self.avisos.setStyleSheet("color: #FFD37A;")
        self.avisos.hide()
        self.layout.addWidget(self.avisos)
        self.atualizar()

    def abrir_arquivo(self):
        caminho, _ = QFileDialog.getOpenFileName(self, "Abrir configuração", "", "Texto (*.txt);;Todos os arquivos (*)")
        if caminho:
            self.carregar_arquivo(caminho)

    def carregar_arquivo(self, caminho):
        try:
            estado, algoritmo, avisos = carregar_configuracao(caminho)
        except (ValueError, OSError) as erro:
            self.mensagem.setText(str(erro))
            return False
        self.simulacao = Simulacao(estado, algoritmo)
        self.avisos.setText("\n".join(avisos))
        self.avisos.setVisible(bool(avisos))
        self.tabela.clearSelection()
        self.tabela.setCurrentCell(-1, -1)
        self.barra_gantt.update()
        self.mensagem.setText("\n".join(avisos) or f"Arquivo carregado: {Path(caminho).name}")
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

    def retroceder(self):
        if self.simulacao is None:
            return
        self.simulacao.retroceder()
        self.atualizar()

    def editar_selecionada(self):
        item = self.tabela.item(self.tabela.currentRow(), 0)
        if self.simulacao is None or item is None:
            self.mensagem.setText("Selecione uma tarefa na tabela para editar.")
            return
        dialogo = DialogoEdicao(self, item.data(Qt.ItemDataRole.UserRole))
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
                    self.mensagem.setText("Execução concluída. Todas as tarefas periódicas finalizaram suas dez ocorrências." if estado.tarefas else "Execução concluída: nenhuma tarefa periódica incluída. Consulte os avisos do arquivo.")
                    self.atualizar()
                    return
                if not estado.cpus:
                    raise RuntimeError("Execução completa interrompida: há tarefas pendentes, mas nenhuma CPU.")
                suspensa = next((t for t in pendentes if t.estado_tarefa == EstadoTarefa.SUSPENSA), None)
                if suspensa is not None:
                    raise RuntimeError(f"Execução completa interrompida: tarefa {suspensa.id} suspensa. Altere seu estado manualmente antes de continuar.")
                self.simulacao.avancar()
                if monotonic() - inicio >= 0.012:
                    break
            self.mensagem.setText(f"Execução completa em andamento… tick {self.simulacao.historico[self.simulacao.instante_atual].tick}. A interface permanece disponível.")
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
        self.botao_abrir.setEnabled(livre)
        self.botao_avancar.setEnabled(livre and carregada and pendente)
        self.botao_completa.setEnabled(livre and carregada and pendente)
        self.botao_retroceder.setEnabled(livre and carregada and self.simulacao.instante_atual > 0)
        self.botao_editar.setEnabled(livre and carregada and self.tabela.currentRow() >= 0)
        self.tabela.setEnabled(livre)
        self.barra_gantt.setEnabled(livre and carregada)
        self.botao_exportar.setEnabled(livre and carregada)

    def atualizar(self):
        self.atualizar_controles()
        if self.simulacao is None:
            self.figura.clear()
            ax = self.figura.add_subplot()
            ax.text(0.5, 0.5, "Abra um arquivo para visualizar a linha do tempo.",
                    ha="center", va="center", transform=ax.transAxes)
            ax.set_axis_off()
            self.canvas.draw_idle()
            return
        estado = self.simulacao.historico[self.simulacao.instante_atual]
        concluidas = sum(t.instancias_concluidas for t in estado.tarefas)
        desligadas = ", ".join(f"CPU {c.id_cpu}: {c.tempo_desligada}" for c in estado.cpus)
        self.resumo.setText(f"{self.simulacao.algoritmo}  ·  tick {estado.tick}  ·  {len(estado.tarefas)} tarefas  ·  {len(estado.cpus)} CPUs  ·  quantum {estado.quantum}  ·  {concluidas} ocorrências concluídas\nTicks desligados — {desligadas}")
        selecionada = self.tabela.item(self.tabela.currentRow(), 0)
        id_selecionado = selecionada.data(Qt.ItemDataRole.UserRole) if selecionada else None
        tarefas = tarefas_ordenadas(estado.tarefas)
        self.tabela.setRowCount(len(tarefas))
        for linha, tarefa in enumerate(tarefas):
            valores = (tarefa.id, tarefa.estado_tarefa.name, tarefa.id_cpu_atual if tarefa.id_cpu_atual is not None else "—",
                       tarefa.ingresso, tarefa.duracao, tarefa.periodo, tarefa.prazo, tarefa.prazo_absoluto,
                       tarefa.tempo_exec_instancia, tarefa.tempo_exec_quantum, f"{tarefa.instancias_concluidas}/10",
                       "SIM" if tarefa.perdeu_prazo else "Não", tarefa.cor)
            for coluna, valor in enumerate(valores):
                item = QTableWidgetItem(str(valor))
                if coluna == 0:
                    item.setData(Qt.ItemDataRole.UserRole, tarefa.id)
                    item.setForeground(QColor(tarefa.cor))
                self.tabela.setItem(linha, coluna, item)
            if tarefa.id == id_selecionado:
                self.tabela.selectRow(linha)
        self.eventos.setPlainText("\n".join(texto_evento(e) for e in estado.eventos) or "Nenhum evento neste snapshot.")
        self.desenhar_gantt()

    def desenhar_gantt(self):
        """A janela só fornece o estado; gantt.py desenha a mesma Figure usada na exportação."""
        desenhar_gantt(self.simulacao, self.figura)
        self.barra_gantt.update()
        self.canvas.draw_idle()



def main():
    app = QApplication(sys.argv)
    janela = JanelaSimulador()
    if len(sys.argv) > 1:
        janela.carregar_arquivo(sys.argv[1])
    janela.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
