import unittest
from models import TCB, EstadoTarefa
from scheduler import escalonar

class TesteEscalonadorPasso3(unittest.TestCase):

    def test_prioridade_rm(self):
        # T1 tem período 10, T2 tem período 5 (T2 deve ganhar no RM)
        t1 = TCB(1, "FF0000", ingresso=0, duracao=2, periodo=10, prazo=10)
        t2 = TCB(2, "00FF00", ingresso=0, duracao=2, periodo=5, prazo=5)
        
        eleitas = escalonar([t1, t2], "RM")
        self.assertEqual(eleitas[0].id, 2)

    def test_prioridade_edf(self):
        # T1 tem prazo_absoluto 8, T2 tem prazo_absoluto 12 (T1 deve ganhar no EDF)
        t1 = TCB(1, "FF0000", ingresso=0, duracao=2, periodo=10, prazo=8)
        t2 = TCB(2, "00FF00", ingresso=0, duracao=2, periodo=5, prazo=12)
        
        eleitas = escalonar([t1, t2], "EDF")
        self.assertEqual(eleitas[0].id, 1)

    def test_desempates_em_cascata(self):
        # Mesmo período (10), mas T2 já estava EXECUTANDO -> T2 ganha (Desempate 1)
        t1 = TCB(1, "FF0000", ingresso=0, duracao=2, periodo=10, prazo=5)
        t2 = TCB(2, "00FF00", ingresso=0, duracao=2, periodo=10, prazo=5)
        t1.estado_tarefa = EstadoTarefa.PRONTA
        t2.estado_tarefa = EstadoTarefa.EXECUTANDO
        
        eleitas = escalonar([t1, t2], "RM")
        self.assertEqual(eleitas[0].id, 2)

if __name__ == "__main__":
    unittest.main()