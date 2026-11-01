from pathlib import Path
import sys
raiz=Path.cwd()
sys.path.insert(0,str(raiz))
import customtkinter as ctk
from gui import JanelaSimulador
ctk.set_appearance_mode('light')
ctk.set_widget_scaling(1)
j=JanelaSimulador(); j.geometry('1440x760+0+0')
ultima=''
def preparar():
    global ultima
    f=raiz/'build/gantt-compacto/cena.txt'
    if f.exists():
        cena=f.read_text().strip()
        if cena!=ultima:
            ultima=cena
            if cena=='fechar':
                j.fechar(); return
            if cena!='inicial':
                j.carregar_arquivo(raiz/'exemplos/configuracao.txt')
                if cena=='final': j.simulacao.executar_completa()
                else: j.simulacao.avancar(12)
                j.atualizar(); j.update_idletasks(); j.ajustar()
                j.seletor.set('Tarefa 1'); j.inspecionar()
    j.after(200,preparar)
j.after(200,preparar); j.mainloop()
