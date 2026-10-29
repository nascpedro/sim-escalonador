import unittest
from unittest.mock import patch

from engine import Simulacao
from models import TCB, Cpu, EstadoSimulacao, EstadoTarefa
from scheduler import escalonar


class TesteSorteio(unittest.TestCase):
    def test_registra_ordem_sorteada_apenas_no_grupo_totalmente_empatado(self):
        for algoritmo in ['RM', 'EDF']:
            with self.subTest(algoritmo=algoritmo):
                t1 = TCB(1, 'FF0000', 0, 2, 10, 10)
                t2 = TCB(2, '00FF00', 0, 2, 10, 10)
                t3 = TCB(3, '0000FF', 0, 1, 5, 5)
                sorteios = []
                # Torna o sorteio previsível neste teste, invertendo o grupo empatado.
                with patch('scheduler.random.shuffle', side_effect=lambda grupo: grupo.reverse()) as sorteio:
                    ordenadas = escalonar([t1, t2, t3], algoritmo, sorteios)
                self.assertEqual([t.id for t in ordenadas], [3, 2, 1])
                self.assertEqual(sorteios, [[2, 1]])
                sorteio.assert_called_once()
                self.assertEqual(t1.estado_tarefa, EstadoTarefa.AGUARDANDO)

    def test_criterios_anteriores_e_listas_pequenas_nao_geram_sorteio(self):
        for criterio in ['periodo', 'estado_tarefa', 'prazo', 'ingresso', 'duracao']:
            with self.subTest(criterio=criterio):
                t1 = TCB(1, 'FF0000', 0, 2, 10, 10)
                t2 = TCB(2, '00FF00', 0, 2, 10, 10)
                if criterio == 'estado_tarefa':
                    t1.estado_tarefa = EstadoTarefa.EXECUTANDO
                else:
                    setattr(t1, criterio, getattr(t1, criterio) - 1)
                sorteios = []
                with patch('scheduler.random.shuffle') as sorteio:
                    escalonar([t1, t2], 'RM', sorteios)
                    escalonar([], 'RM', sorteios)
                    escalonar([t1], 'RM', sorteios)
                self.assertEqual(sorteios, [])
                sorteio.assert_not_called()

    def test_motor_guarda_evento_com_tick_e_selecionada_e_preserva_historico(self):
        t1 = TCB(1, 'FF0000', 0, 2, 10, 10)
        t2 = TCB(2, '00FF00', 0, 2, 10, 10)
        sim = Simulacao(EstadoSimulacao(0, [t1, t2], [Cpu(0)], 0), 'RM')
        with patch('scheduler.random.shuffle', side_effect=lambda grupo: grupo.reverse()) as sorteio:
            sim.avancar()
            primeiro = sim.historico[sim.instante_atual]
            self.assertEqual([e for e in primeiro.eventos if e['tipo'] == 'sorteio'], [
                {'tipo': 'sorteio', 'tick': 0, 'ordem': [2, 1], 'selecionadas': [2]}
            ])
            self.assertEqual(primeiro.cpus[0].id_tarefa_alocada, 2)
            self.assertEqual(sim.historico[0].eventos, [])
            sim.retroceder()
            sim.avancar()
            self.assertIs(sim.historico[sim.instante_atual], primeiro)
            sorteio.assert_called_once()
            # No próximo tick, quem já executava vence sem sorteio.
            sim.avancar()
            self.assertEqual([e for e in sim.historico[sim.instante_atual].eventos if e['tipo'] == 'sorteio'], [])
            self.assertEqual(primeiro.eventos[0]['ordem'], [2, 1])
            sorteio.assert_called_once()


if __name__ == '__main__':
    unittest.main()
