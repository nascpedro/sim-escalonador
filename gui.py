"""Interface do Projeto A: CustomTkinter + Canvas + drawsvg.

Execute: python gui.py [configuracao.txt]. O desenho e a exportação estão em gantt.py.
"""
import sys
import tkinter as tk
from pathlib import Path
from time import monotonic
from tkinter import filedialog

import customtkinter as ctk

from engine import Simulacao
from gantt import DesenhoCanvas, desenhar_gantt, exportar_svg, preparar_gantt, tamanho_gantt
from models import EstadoTarefa
from parser import carregar_configuracao


class DialogoTarefa(tk.Toplevel):
    """Coleta somente alterações; o motor decide se elas são válidas."""
    def __init__(self, janela, tarefa):
        super().__init__(janela)
        self.janela, self.tarefa = janela, tarefa
        self.title(f'Editar tarefa {tarefa.id}')
        self.resizable(False, False)
        self.transient(janela)
        self.campos = {}
        for linha, (campo, nome) in enumerate((('ingresso', 'Ingresso'), ('duracao', 'Duração'),
                ('periodo', 'Período'), ('prazo', 'Prazo relativo'), ('cor', 'Cor RGB'))):
            ctk.CTkLabel(self, text=nome).grid(row=linha, column=0, padx=16, pady=6, sticky='w')
            entrada = ctk.CTkEntry(self, width=220)
            entrada.insert(0, str(getattr(tarefa, campo)))
            entrada.grid(row=linha, column=1, padx=16, pady=6)
            self.campos[campo] = entrada
        self.estado = ctk.CTkOptionMenu(self, values=[e.name for e in EstadoTarefa])
        self.estado.set(tarefa.estado_tarefa.name)
        ctk.CTkLabel(self, text='Estado').grid(row=5, column=0, padx=16, sticky='w')
        self.estado.grid(row=5, column=1, padx=16, pady=6)
        self.erro = ctk.CTkLabel(self, text='Uma edição aceita descarta o futuro.\nAGUARDANDO abandona a ocorrência e sua fila.',
                                 wraplength=370, justify='left')
        self.erro.grid(row=6, column=0, columnspan=2, padx=16, pady=12)
        ctk.CTkButton(self, text='Salvar', command=self.salvar).grid(row=7, column=0, padx=16, pady=16)
        ctk.CTkButton(self, text='Cancelar', command=self.destroy).grid(row=7, column=1, padx=16, pady=16)
        self.grab_set()

    def salvar(self):
        alteracoes = {}
        try:
            for campo, entrada in self.campos.items():
                texto = entrada.get().strip()
                if campo == 'cor':
                    valor = '#' + texto.lstrip('#').upper()
                else:
                    try:
                        valor = int(texto)
                    except ValueError:
                        raise ValueError(f'{campo} deve ser inteiro.') from None
                if valor != getattr(self.tarefa, campo):
                    alteracoes[campo] = valor
            estado = EstadoTarefa[self.estado.get()]
            if estado != self.tarefa.estado_tarefa:
                alteracoes['estado_tarefa'] = estado
            self.janela.simulacao.modificar_tarefa_em_execucao(self.tarefa.id, **alteracoes)
        except ValueError as erro:
            self.erro.configure(text=str(erro), text_color='#a62626')
            return False
        self.janela.atualizar()
        self.janela.mensagem.configure(text='Tarefa atualizada; snapshots anteriores preservados.'
                                      if alteracoes else 'Sem alterações; histórico preservado.')
        self.destroy()
        return True


class JanelaSimulador(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title('Simulador de escalonamento · Projeto A')
        self.geometry('1200x800')
        self.minsize(980, 650)
        self.simulacao = None
        self.caminho = None
        self.escala = 24.0
        self.dados_gantt = None
        self.ids_tarefas = []
        self.timer = None
        self.fechada = False
        self.estado_exportado = None
        self.protocol('WM_DELETE_WINDOW', self.fechar)
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, minsize=260)
        self.grid_rowconfigure(2, weight=1)
        self._montar_controles()
        self._montar_grafico()
        self._montar_inspecao()
        self.mensagem = ctk.CTkLabel(self, text='Abra uma configuração para começar.', anchor='w',
                                    wraplength=1100, justify='left')
        self.mensagem.grid(row=3, column=0, columnspan=2, padx=15, pady=10, sticky='ew')
        self.atualizar()

    def _montar_controles(self):
        self.resumo = ctk.CTkLabel(self, text='Projeto A', font=ctk.CTkFont(size=20, weight='bold'), anchor='w')
        self.resumo.grid(row=0, column=0, columnspan=2, padx=18, pady=12, sticky='ew')
        barra = ctk.CTkFrame(self)
        barra.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 10), sticky='ew')
        self.botoes = {}
        for i, (nome, texto, acao) in enumerate((
                ('abrir', 'Abrir arquivo', self.abrir), ('voltar', '← Voltar', self.retroceder),
                ('avancar', 'Avançar tick →', self.avancar), ('executar', 'Executar até o fim', self.executar_completa),
                ('exportar', 'Exportar SVG', self.escolher_exportacao))):
            botao = ctk.CTkButton(barra, text=texto, command=acao, width=145)
            botao.grid(row=0, column=i, padx=6, pady=10)
            self.botoes[nome] = botao

    def _montar_grafico(self):
        painel = ctk.CTkFrame(self)
        painel.grid(row=2, column=0, padx=(12, 6), sticky='nsew')
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(1, weight=1)
        zoom = ctk.CTkFrame(painel, fg_color='transparent')
        zoom.grid(row=0, column=0, sticky='w', padx=8, pady=8)
        self.botoes_zoom = []
        for i, (texto, acao) in enumerate((('− Zoom', lambda: self.zoom(.8)),
                ('+ Zoom', lambda: self.zoom(1.25)), ('Ajustar tudo', self.ajustar))):
            botao = ctk.CTkButton(zoom, text=texto, command=acao, width=100)
            botao.grid(row=0, column=i, padx=4)
            self.botoes_zoom.append(botao)
        self.canvas = tk.Canvas(painel, bg='white', highlightthickness=0)
        self.canvas.grid(row=1, column=0, sticky='nsew')
        horizontal = ctk.CTkScrollbar(painel, orientation='horizontal', command=self.canvas.xview)
        horizontal.grid(row=2, column=0, sticky='ew')
        vertical = ctk.CTkScrollbar(painel, orientation='vertical', command=self.canvas.yview)
        vertical.grid(row=1, column=1, sticky='ns')
        self.canvas.configure(xscrollcommand=horizontal.set, yscrollcommand=vertical.set)

    def _montar_inspecao(self):
        painel = ctk.CTkFrame(self, width=260)
        painel.grid(row=2, column=1, padx=(6, 12), sticky='nsew')
        painel.grid_columnconfigure(0, weight=1)
        painel.grid_rowconfigure(1, weight=1)
        self.seletor = ctk.CTkOptionMenu(painel, values=['Sem tarefas'], command=lambda _: self.inspecionar())
        self.seletor.grid(row=0, column=0, padx=12, pady=12, sticky='ew')
        self.detalhes = ctk.CTkTextbox(painel, width=250, wrap='word')
        self.detalhes.grid(row=1, column=0, padx=12, pady=(0, 10), sticky='nsew')
        self.botao_editar = ctk.CTkButton(painel, text='Editar tarefa', command=self.editar)
        self.botao_editar.grid(row=2, column=0, padx=12, pady=8, sticky='ew')
        self.algoritmo = ctk.CTkOptionMenu(painel, values=['RM', 'EDF'])
        self.algoritmo.grid(row=3, column=0, padx=12, pady=6, sticky='ew')
        self.quantum = self._campo_sistema(painel, 4, 'Quantum', '0')
        self.cpus = self._campo_sistema(painel, 6, 'Quantidade de CPUs', '1')
        self.botao_configurar = ctk.CTkButton(painel, text='Aplicar configuração', command=self.configurar)
        self.botao_configurar.grid(row=8, column=0, padx=12, pady=12, sticky='ew')

    def _campo_sistema(self, painel, linha, rotulo, valor):
        ctk.CTkLabel(painel, text=rotulo, anchor='w').grid(row=linha, column=0, padx=12, sticky='ew')
        entrada = ctk.CTkEntry(painel)
        entrada.insert(0, valor)
        entrada.grid(row=linha+1, column=0, padx=12, pady=(0, 6), sticky='ew')
        return entrada

    def abrir(self):
        caminho = filedialog.askopenfilename(parent=self, filetypes=[('Texto', '*.txt'), ('Todos', '*')])
        if caminho:
            self.carregar_arquivo(caminho)

    def carregar_arquivo(self, caminho):
        try:
            estado, algoritmo, avisos = carregar_configuracao(caminho)
        except (ValueError, OSError) as erro:
            self.mensagem.configure(text=str(erro))
            return False
        self.simulacao = Simulacao(estado, algoritmo)
        self.caminho = Path(caminho).resolve()
        self.estado_exportado = None
        self.escala = 24.0
        self.seletor.set('Sem tarefas')
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)
        self.atualizar()
        self.mensagem.configure(text=('\n'.join(avisos) + '\n' if avisos else '') +
            f'Arquivo: {self.caminho.name}. SVG final será salvo ao lado dele, sem sobrescrever arquivos.')
        return True

    def avancar(self):
        if self.simulacao is not None:
            self.simulacao.avancar()
            self.atualizar()
            self.salvar_final()

    def retroceder(self):
        if self.simulacao is not None:
            self.simulacao.retroceder()
            self.atualizar()

    def executar_completa(self):
        if self.simulacao is not None and self.timer is None:
            self.timer = self.after(1, self.executar_lote)
            self.atualizar_controles()

    def executar_lote(self):
        inicio = monotonic()
        try:
            for _ in range(32):
                estado = self.simulacao.historico[self.simulacao.instante_atual]
                pendentes = [t for t in estado.tarefas if t.estado_tarefa != EstadoTarefa.FINALIZADA]
                if not pendentes:
                    self.timer = None
                    self.atualizar()
                    self.mensagem.configure(text='Execução concluída.')
                    self.salvar_final()
                    return
                if not estado.cpus:
                    raise RuntimeError('Há tarefas pendentes, mas nenhuma CPU.')
                suspensa = next((t for t in pendentes if t.estado_tarefa == EstadoTarefa.SUSPENSA), None)
                if suspensa is not None:
                    raise RuntimeError(f'Tarefa {suspensa.id} suspensa: retome manualmente antes de continuar.')
                self.simulacao.avancar()
                if monotonic() - inicio >= .012:
                    break
        except (ValueError, RuntimeError) as erro:
            self.timer = None
            self.atualizar()
            self.mensagem.configure(text=str(erro))
            return
        self.mensagem.configure(text=f'Executando… tick {self.simulacao.instante_atual}')
        self.timer = self.after(1, self.executar_lote)

    def configurar(self):
        try:
            try:
                quantum, cpus = int(self.quantum.get()), int(self.cpus.get())
            except ValueError:
                raise ValueError('Quantum e CPUs devem ser inteiros.') from None
            mudou = self.simulacao.configurar_sistema(self.algoritmo.get(), quantum, cpus)
        except ValueError as erro:
            self.mensagem.configure(text=str(erro))
            return False
        self.atualizar()
        self.mensagem.configure(text='Configuração alterada; somente o futuro foi descartado.'
                                if mudou else 'Sem alterações; histórico preservado.')
        return True

    def tarefa_selecionada(self):
        if not self.ids_tarefas:
            return None
        nomes = [f'Tarefa {id_}' for id_ in self.ids_tarefas]
        id_ = self.ids_tarefas[nomes.index(self.seletor.get())]
        estado = self.simulacao.historico[self.simulacao.instante_atual]
        return next(t for t in estado.tarefas if t.id == id_)

    def editar(self):
        tarefa = self.tarefa_selecionada()
        if tarefa is not None:
            DialogoTarefa(self, tarefa)

    def inspecionar(self):
        tarefa = self.tarefa_selecionada()
        texto = 'Abra um arquivo para inspecionar as tarefas.'
        if tarefa is not None:
            cpu = '—' if tarefa.id_cpu_atual is None else tarefa.id_cpu_atual
            perdeu = 'SIM' if tarefa.perdeu_prazo else 'Não'
            texto = (f'Tarefa {tarefa.id}\nEstado: {tarefa.estado_tarefa.name}\nCPU: {cpu}\n'
                f'Ingresso: {tarefa.ingresso}\nDuração: {tarefa.duracao}\nPeríodo: {tarefa.periodo}\n'
                f'Prazo relativo: {tarefa.prazo}\nPrazo absoluto: {tarefa.prazo_absoluto}\n'
                f'Execução / fatia: {tarefa.tempo_exec_instancia} / {tarefa.tempo_exec_quantum}\n'
                f'Concluídas: {tarefa.instancias_concluidas}/10\n'
                f'Pendentes: {len(tarefa.ocorrencias_pendentes)}\nPerdeu prazo: {perdeu}\n')
        if self.simulacao is not None:
            estado = self.simulacao.historico[self.simulacao.instante_atual]
            texto += '\nTicks ociosos:\n' + '\n'.join(f'CPU {c.id_cpu}: {c.tempo_desligada}' for c in estado.cpus)
            texto += '\n\nEventos do snapshot:\n' + '\n'.join(str(e) for e in estado.eventos)
        self.detalhes.configure(state='normal')
        self.detalhes.delete('1.0', 'end')
        self.detalhes.insert('1.0', texto)
        self.detalhes.configure(state='disabled')

    def atualizar(self):
        if self.simulacao is not None:
            estado = self.simulacao.historico[self.simulacao.instante_atual]
            self.resumo.configure(text=f'Projeto A · {self.simulacao.algoritmo} · {len(estado.cpus)} CPUs · tick {estado.tick}')
            self.algoritmo.set(self.simulacao.algoritmo)
            for entrada, valor in ((self.quantum, estado.quantum), (self.cpus, len(estado.cpus))):
                entrada.delete(0, 'end')
                entrada.insert(0, str(valor))
            self.ids_tarefas = sorted([t.id for t in estado.tarefas],
                key=lambda id_: (isinstance(id_, str), id_), reverse=True)
            nomes = [f'Tarefa {id_}' for id_ in self.ids_tarefas] or ['Sem tarefas']
            self.seletor.configure(values=nomes)
            if self.seletor.get() not in nomes:
                self.seletor.set(nomes[0])
            self.dados_gantt = preparar_gantt(self.simulacao)
            self.redesenhar()
        self.inspecionar()
        self.atualizar_controles()

    def atualizar_controles(self):
        carregada = self.simulacao is not None
        livre = self.timer is None
        pendentes = carregada and any(t.estado_tarefa != EstadoTarefa.FINALIZADA
            for t in self.simulacao.historico[self.simulacao.instante_atual].tarefas)
        for nome, botao in self.botoes.items():
            habilitado = livre and (nome == 'abrir' or carregada)
            if nome in ('avancar', 'executar'):
                habilitado = habilitado and pendentes
            if nome == 'voltar':
                habilitado = habilitado and self.simulacao.instante_atual > 0
            botao.configure(state='normal' if habilitado else 'disabled')
        for controle in (self.algoritmo, self.quantum, self.cpus, self.botao_configurar, *self.botoes_zoom):
            controle.configure(state='normal' if livre and carregada else 'disabled')
        self.seletor.configure(state='normal' if livre and self.ids_tarefas else 'disabled')
        self.botao_editar.configure(state='normal' if livre and self.ids_tarefas else 'disabled')

    def redesenhar(self):
        if self.dados_gantt is None:
            return
        esquerda, topo = max(0, self.canvas.canvasx(0)), max(0, self.canvas.canvasy(0))
        self.canvas.delete('all')
        largura, altura = desenhar_gantt(self.dados_gantt, DesenhoCanvas(self.canvas), self.simulacao.algoritmo, self.escala)
        self.canvas.configure(scrollregion=(0, 0, largura, altura))
        self.canvas.xview_moveto(esquerda / largura)
        self.canvas.yview_moveto(topo / altura)

    def zoom(self, fator):
        if self.dados_gantt is None:
            return
        _, _, margem = tamanho_gantt(self.dados_gantt)
        largura_tela = self.canvas.winfo_width()
        centro_tick = (self.canvas.canvasx(largura_tela/2)-margem) / self.escala
        self.escala = max(.01, min(200, self.escala * fator))
        self.redesenhar()
        largura, _, _ = tamanho_gantt(self.dados_gantt, self.escala)
        self.canvas.xview_moveto(max(0, margem+centro_tick*self.escala-largura_tela/2) / largura)

    def ajustar(self):
        if self.dados_gantt is not None:
            fim = max(1, self.dados_gantt[0])
            _, _, margem = tamanho_gantt(self.dados_gantt)
            self.escala = max(1e-9, (self.canvas.winfo_width()-margem-30) / fim)
            self.canvas.xview_moveto(0)
            self.redesenhar()

    def escolher_exportacao(self):
        caminho = filedialog.asksaveasfilename(parent=self, defaultextension='.svg',
            filetypes=[('SVG', '*.svg')], initialfile='gantt.svg')
        if caminho:
            self.exportar_arquivo(caminho)

    def exportar_arquivo(self, caminho):
        try:
            exportar_svg(self.simulacao, caminho)
        except (OSError, ValueError) as erro:
            self.mensagem.configure(text=f'Erro ao exportar: {erro}. O resultado continua disponível.')
            return False
        self.mensagem.configure(text=f'SVG salvo: {caminho}')
        return True

    def salvar_final(self):
        estado = self.simulacao.historico[self.simulacao.instante_atual]
        if (not estado.tarefas or self.estado_exportado is estado
                or any(t.estado_tarefa != EstadoTarefa.FINALIZADA for t in estado.tarefas)):
            return
        destino = self.caminho.with_name(self.caminho.stem + '-gantt.svg')
        numero = 2
        while destino.exists():
            destino = self.caminho.with_name(f'{self.caminho.stem}-gantt-{numero}.svg')
            numero += 1
        if self.exportar_arquivo(destino):
            self.estado_exportado = estado

    def fechar(self):
        if self.fechada:
            return
        self.fechada = True
        if self.timer is not None:
            self.after_cancel(self.timer)
            self.timer = None
        # CustomTkinter também agenda callbacks de aparência/DPI. Cancela os
        # callbacks deste interpretador antes de destruir seus widgets.
        for callback in self.tk.call('after', 'info'):
            self.tk.call('after', 'cancel', callback)
        self.destroy()


def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--exportar':
        from exporter import main as exportar_cli
        return exportar_cli(sys.argv[2:])
    if len(sys.argv) > 1 and sys.argv[1] == '--verificar-interface':
        from scripts.verificar_interface import verificar
        verificar(JanelaSimulador, sys.argv[2], sys.argv[3])
        return 0
    ctk.set_appearance_mode('light')
    janela = JanelaSimulador()
    if len(sys.argv) > 1:
        janela.carregar_arquivo(sys.argv[1])
    janela.mainloop()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
