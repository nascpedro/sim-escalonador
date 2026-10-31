"""Exportação SVG e CLI: o desenho pertence exclusivamente a gantt.py."""
from pathlib import Path

from matplotlib import rc_context
from matplotlib.figure import Figure

from gantt import desenhar_gantt


def exportar_svg(simulacao, caminho):
    """Salva o prefixo visível sem executar ticks ou modificar snapshots.

    Usa o mesmo desenho da tela; bbox_inches inclui legenda e rótulos longos.
    Não cria diretórios. Falhas de escrita propagam OSError com o destino.
    """
    estado = simulacao.historico[simulacao.instante_atual]
    figura = Figure(figsize=(max(12, min(24, estado.tick * .12)),
                             max(4, 2 + len(estado.tarefas) * .9 + len(estado.cpus) * .3)))
    desenhar_gantt(simulacao, figura)
    destino = Path(caminho)
    try:
        # Texto continua texto no SVG, sem alterar rcParams do aplicativo.
        with rc_context({'svg.fonttype': 'none'}):
            figura.savefig(destino, format='svg', bbox_inches='tight', facecolor='white')
    except OSError as erro:
        raise OSError(erro.errno, f'Não foi possível exportar SVG para {destino}: {erro.strerror}',
                      str(destino)) from erro
    return destino


def main(argv=None):
    """CLI: python exporter.py arquivo.txt saida.svg; erros esperados sem traceback."""
    import argparse
    import sys
    from engine import Simulacao
    from parser import carregar_configuracao

    argumentos = argparse.ArgumentParser(description='Exporta o Gantt SVG completo do Projeto A.')
    argumentos.add_argument('configuracao', help='Arquivo de configuração UTF-8')
    argumentos.add_argument('saida', help='Caminho do arquivo SVG de destino')
    args = argumentos.parse_args(argv)
    try:
        estado, algoritmo, avisos = carregar_configuracao(args.configuracao)
        for aviso in avisos:
            print(f'Aviso: {aviso}', file=sys.stderr)
        simulacao = Simulacao(estado, algoritmo)
        simulacao.executar_completa()
        destino = exportar_svg(simulacao, args.saida)
    except (OSError, ValueError, RuntimeError) as erro:
        print(f'Erro: {erro}', file=sys.stderr)
        return 1
    print(f'SVG exportado: {destino}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
