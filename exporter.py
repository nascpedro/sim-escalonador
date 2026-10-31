"""CLI e API de exportação SVG por drawsvg, sem abrir a interface."""
from gantt import exportar_svg


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
