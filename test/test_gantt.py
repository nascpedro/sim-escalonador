"""Testes do Gantt Canvas/drawsvg e da interface CustomTkinter."""
import importlib.util
from pathlib import Path
import pickle
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

from engine import Simulacao
from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB

TEM_SVG = importlib.util.find_spec('drawsvg') is not None


@unittest.skipUnless(TEM_SVG, 'drawsvg não instalado neste interpretador')
class TestGanttSVG(unittest.TestCase):
    def criar(self):
        return Simulacao(EstadoSimulacao(0, [TCB('ação <x>&', '123456', 0, 4, 8, 2)],
                                        [Cpu(0), Cpu(1)], 1), 'RM')

    def test_svg_vetorial_prefixo_real_sem_alterar_historico(self):
        from gantt import exportar_svg
        sim = self.criar()
        sim.avancar(6)
        sim.retroceder(2)
        antes = pickle.dumps(sim.historico)
        with tempfile.TemporaryDirectory() as pasta:
            saida = exportar_svg(sim, Path(pasta) / 'gantt.svg')
            raiz = ET.parse(saida).getroot()
            texto = ''.join(raiz.itertext())
            self.assertIn('0 a 4 ticks', texto)
            self.assertNotIn('0 a 6 ticks', texto)
            self.assertIn('ação <x>&', texto)
            self.assertEqual(raiz.tag, '{http://www.w3.org/2000/svg}svg')
            self.assertFalse(raiz.findall('.//{http://www.w3.org/2000/svg}image'))
        self.assertEqual(pickle.dumps(sim.historico), antes)

    def test_suspensao_tem_padrao_e_eventos_tem_legenda(self):
        from gantt import EVENTOS, exportar_svg
        sim = self.criar()
        sim.modificar_tarefa_em_execucao('ação <x>&', estado_tarefa=EstadoTarefa.SUSPENSA)
        sim.avancar(3)
        with tempfile.TemporaryDirectory() as pasta:
            raiz = ET.parse(exportar_svg(sim, Path(pasta) / 'suspensa.svg')).getroot()
        self.assertTrue(raiz.findall('.//{http://www.w3.org/2000/svg}pattern'))
        for nome, _, _ in EVENTOS.values():
            self.assertIn(nome, ''.join(raiz.itertext()))

    def test_sem_qt_matplotlib_ou_tk_na_exportacao(self):
        teste = subprocess.run([sys.executable, '-B', '-c',
            "import gantt,sys; assert not any(m in sys.modules for m in ['PySide6','matplotlib','tkinter'])"],
            capture_output=True, text=True)
        self.assertEqual(teste.returncode, 0, teste.stderr)

    def test_erro_de_escrita_e_historia_sem_tarefas(self):
        from gantt import exportar_svg
        sim = Simulacao(EstadoSimulacao(0, [], [], 0), 'EDF')
        with tempfile.TemporaryDirectory() as pasta:
            raiz = ET.parse(exportar_svg(sim, Path(pasta) / 'vazio.svg')).getroot()
            self.assertIn('0 a 0 ticks', ''.join(raiz.itertext()))
            with self.assertRaises(OSError):
                exportar_svg(sim, Path(pasta) / 'ausente' / 'falha.svg')

    def test_sorteio_na_trilha_das_selecionadas_e_ids_decrescentes(self):
        from unittest.mock import patch
        from gantt import DesenhoSVG, desenhar_gantt, preparar_gantt, tamanho_gantt
        sim = Simulacao(EstadoSimulacao(0, [TCB(i, f'{i*1000:06X}', 0, 3, 10, 10)
            for i in (1, 2, 3)], [Cpu(0), Cpu(1)], 0), 'RM')
        with patch('scheduler.random.shuffle', side_effect=lambda g: g.reverse()):
            sim.avancar()
        dados = preparar_gantt(sim)
        self.assertEqual(dados[1], [3, 2, 1])
        largura, altura, _ = tamanho_gantt(dados)
        desenho = DesenhoSVG(largura, altura)
        sorteios = []
        poligono = desenho.poligono
        def registrar(pontos, cor):
            if cor == '#6e3f97':
                sorteios.append(sum(y for _, y in pontos) / len(pontos))
            poligono(pontos, cor)
        desenho.poligono = registrar
        desenhar_gantt(dados, desenho, 'RM')
        # Tarefas 3 e 2 recebem CPUs; tarefa 1 não recebe o diamante.
        self.assertEqual(sorted(y for y in sorteios if y < 400), [156, 281])
