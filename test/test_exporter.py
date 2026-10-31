"""API e CLI do SVG vetorial gerado pelo desenho compartilhado."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

import pickle

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB


def retrato(sim):
    return pickle.dumps(sim.historico)

NS = {'s': 'http://www.w3.org/2000/svg'}


class TesteExportador(unittest.TestCase):
    def exportar(self, sim, caminho):
        from exporter import exportar_svg
        self.assertEqual(exportar_svg(sim, caminho), Path(caminho))
        return ET.parse(caminho).getroot()

    def test_svg_historico_real_sem_mutacao_ou_futuro(self):
        sim = Simulacao(EstadoSimulacao(0, [
            TCB(2, 'FF0000', 0, 1, 5, 1),
            TCB(10, '00FF00', 0, 1, 10, 1)], [Cpu(4), Cpu(7)], 0), 'RM')
        sim.executar_completa()
        antes = retrato(sim)
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'gráfico completo ü.svg'
            for fim in (91, 2):
                raiz = self.exportar(sim, caminho)
                self.assertEqual(raiz.tag, '{%s}svg' % NS['s'])
                self.assertTrue(raiz.findall('.//s:rect', NS))
                self.assertIn(f'0 a {fim} ticks', ''.join(raiz.itertext()))
                cores = {r.get('fill') for r in raiz.findall('.//s:rect', NS)}
                self.assertTrue({'#FF0000', '#00FF00', '#d9dde2'} <= cores)
                self.assertFalse(raiz.findall('.//s:image', NS))
                self.assertTrue(raiz.findall('.//s:path', NS))
                if fim == 91:
                    self.assertEqual(retrato(sim), antes)
                    sim.retroceder(89)
            self.assertEqual(len(sim.historico), 92)
            self.assertEqual(sim.instante_atual, 2)
            self.assertEqual(retrato(sim), antes)

    def test_texto_escapado_estado_inicial_vazio_e_rotulos_longos(self):
        id_ = 'ação <x>& identificador muito longo'
        sim = Simulacao(EstadoSimulacao(0, [TCB(id_, '112233', 0, 1, 3, 2)], [Cpu(0)], 0), 'RM')
        with tempfile.TemporaryDirectory() as pasta:
            caminho = Path(pasta) / 'inicial.svg'
            raiz = self.exportar(sim, caminho)
            self.assertIn(id_, ''.join(raiz.itertext()))
            self.assertFalse(raiz.findall('.//s:image', NS))
            self.assertFalse(any(e.tag.rsplit('}', 1)[-1] in ('script', 'foreignObject')
                                 for e in raiz.iter()))
            sim.historico[0].tarefas[0].estado_tarefa = EstadoTarefa.SUSPENSA
            sim.avancar()
            raiz = self.exportar(sim, caminho)
            self.assertTrue(raiz.findall('.//s:pattern', NS))
            self.assertGreaterEqual(len([r for r in raiz.findall('.//s:rect', NS)
                                         if r.get('fill', '').startswith('url(')]), 2)
            vazio = Simulacao(EstadoSimulacao(0, [], [], 0), 'RM')
            raiz = self.exportar(vazio, caminho)
            self.assertIn('0 a 0 ticks', ''.join(raiz.itertext()))

    def test_cli_real_e_erros_legiveis(self):
        with tempfile.TemporaryDirectory() as pasta:
            destino = Path(pasta) / 'saída real.svg'
            comando = [sys.executable, '-B', 'exporter.py']
            sucesso = subprocess.run(comando + ['exemplos/configuracao.txt', str(destino)],
                                     capture_output=True, text=True)
            self.assertEqual(sucesso.returncode, 0, sucesso.stderr)
            self.assertIn('0 a 185 ticks', ''.join(ET.parse(destino).getroot().itertext()))
            invalido = Path(pasta) / 'inválido.txt'
            invalido.write_text('RM;0;0\n1;123456;0;1;2;1;', encoding='utf-8')
            for origem, saida in [('não existe.txt', destino), (invalido, destino),
                                  ('exemplos/configuracao.txt', Path(pasta) / 'ausente' / 'x.svg')]:
                erro = subprocess.run(comando + [str(origem), str(saida)], capture_output=True, text=True)
                self.assertNotEqual(erro.returncode, 0)
                self.assertIn('Erro', erro.stderr)
                self.assertNotIn('Traceback', erro.stderr)
            with self.assertRaisesRegex(OSError, 'Não foi possível exportar SVG'):
                from exporter import exportar_svg
                sim = Simulacao(EstadoSimulacao(0, [], [Cpu(0)], 0), 'RM')
                exportar_svg(sim, Path(pasta) / 'ausente' / 'x.svg')


if __name__ == '__main__':
    unittest.main()
