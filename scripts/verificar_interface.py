"""Verificação de recursos Tcl/Tk, temas, desenho e fechamento no executável.

É acionada por --verificar-interface, sem interferir na janela do usuário.
Não substitui o ensaio visual nem a homologação em máquina limpa.
"""
import json
from pathlib import Path
import tempfile
from time import monotonic, sleep


def verificar(classe_janela, configuracao, relatorio):
    janela = classe_janela()
    janela.withdraw()
    try:
        with tempfile.TemporaryDirectory(prefix='simulador-gui-') as pasta:
            # A imagem automática é escrita somente nesta pasta temporária.
            arquivo = Path(pasta) / 'configuracao.txt'
            arquivo.write_bytes(Path(configuracao).read_bytes())
            assert janela.carregar_arquivo(arquivo)
            janela.avancar()
            janela.retroceder()
            assert janela.simulacao.instante_atual == 0
            janela.executar_completa()
            limite = monotonic() + 30
            while janela.timer is not None and monotonic() < limite:
                janela.update()
                sleep(.005)
            assert janela.timer is None, 'Execução completa não terminou.'
            estado = janela.simulacao.historico[janela.simulacao.instante_atual]
            assert janela.canvas.find_all(), 'Canvas sem elementos.'
            assert (Path(pasta) / 'configuracao-gantt.svg').is_file()
            Path(relatorio).write_text(json.dumps(dict(
                interface=True, tick_final=estado.tick,
                concluidas=sum(t.instancias_concluidas for t in estado.tarefas),
                elementos_canvas=len(janela.canvas.find_all()))), encoding='utf-8')
    finally:
        janela.fechar()
