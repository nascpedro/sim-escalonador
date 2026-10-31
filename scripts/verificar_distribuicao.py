"""Teste local do executável fora do repositório, sem Python/Qt no PATH.

Uso: python scripts/verificar_distribuicao.py dist/SimuladorSO
Não substitui a homologação em um Windows limpo.
"""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


def main():
    pacote = Path(sys.argv[1]).resolve()
    executavel = pacote / 'SimuladorSO.exe'
    assert (pacote / '_internal/ui/janela_principal.ui').is_file()
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('PYTHON', 'QT_', 'PYSIDE', 'MPL'))}
    env['PATH'] = os.pathsep.join([os.environ['SystemRoot'],
                                 str(Path(os.environ['SystemRoot']) / 'System32')])
    resultados = []
    with tempfile.TemporaryDirectory(prefix='simulador-distribuicao-') as pasta:
        pasta = Path(pasta)
        for i in range(3):
            destino = pasta / f'gantt-{i}.svg'
            r = subprocess.run([str(executavel), '--exportar',
                str(pacote / 'exemplos/configuracao.txt'), str(destino)],
                cwd=pasta, env=env, timeout=60)
            assert r.returncode == 0, r.returncode
            raiz = ET.parse(destino).getroot()
            assert 'histórico: 0 a 185 ticks' in ''.join(raiz.itertext())
            assert raiz.find('.//{http://www.w3.org/2000/svg}image') is None
            resultados.append(dict(execucao=i + 1, codigo=r.returncode,
                                   svg_bytes=destino.stat().st_size))
        invalido = pasta / 'invalido.txt'
        invalido.write_text('RM;0;0\n1;112233;0;1;2;2;', encoding='utf-8')
        r = subprocess.run([str(executavel), '--exportar', str(invalido), str(pasta / 'erro.svg')],
                           cwd=pasta, env=env, timeout=60)
        assert r.returncode == 1, r.returncode
        assert not (pasta / 'erro.svg').exists()
        resultados.append(dict(entrada_invalida=True, codigo=r.returncode))
    print(json.dumps(resultados, indent=2))


if __name__ == '__main__':
    main()
