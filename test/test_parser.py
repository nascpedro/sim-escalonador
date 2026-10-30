"""Testes com arquivos reais; temporários ficam no scratch do Hermes."""

from pathlib import Path
import tempfile
import unittest

from models import Cpu, EstadoSimulacao, EstadoTarefa, TCB


class TesteParser(unittest.TestCase):
    def setUp(self):
        scratch = Path("C:/Users/pedro/AppData/Local/hermes/cache/scratch")
        scratch.mkdir(parents=True, exist_ok=True)
        self.temporario = tempfile.TemporaryDirectory(prefix="parser-", dir=scratch)
        self.addCleanup(self.temporario.cleanup)
        self.pasta = Path(self.temporario.name)

    def carregar(self, texto, encoding="utf-8"):
        from parser import carregar_configuracao

        caminho = self.pasta / "configuracao com espaços.txt"
        caminho.write_text(texto, encoding=encoding)
        return carregar_configuracao(caminho)

    def test_carrega_estado_inicial_rm_de_arquivo_real(self):
        estado, algoritmo, avisos = self.carregar("RM;0;2\n1;FF0000;0;2;10;6;\n")
        self.assertIsInstance(estado, EstadoSimulacao)
        self.assertEqual((estado.tick, estado.quantum, algoritmo, avisos), (0, 0, "RM", []))
        self.assertEqual([cpu.id_cpu for cpu in estado.cpus], [0, 1])
        self.assertTrue(all(isinstance(cpu, Cpu) for cpu in estado.cpus))
        tarefa = estado.tarefas[0]
        self.assertIsInstance(tarefa, TCB)
        self.assertEqual((tarefa.id, tarefa.cor, tarefa.ingresso, tarefa.duracao,
                          tarefa.periodo, tarefa.prazo), (1, "#FF0000", 0, 2, 10, 6))
        self.assertEqual(tarefa.estado_tarefa, EstadoTarefa.AGUARDANDO)
        self.assertEqual(tarefa.instancias_concluidas, 0)
        self.assertTrue(all(cpu.id_tarefa_alocada is None for cpu in estado.cpus))

    def test_normaliza_edf_ids_cores_espacos_e_bom(self):
        texto = "\n \n eDf ; 7 ; 1 ; \n\n TaReFa ; #abCdEf ; 3 ; 8 ; 5 ; 12 ; evento B qualquer ; \n"
        estado, algoritmo, avisos = self.carregar(texto, encoding="utf-8-sig")
        self.assertEqual((algoritmo, estado.quantum, avisos), ("EDF", 7, []))
        tarefa = estado.tarefas[0]
        self.assertEqual((tarefa.id, tarefa.cor, tarefa.ingresso, tarefa.duracao,
                          tarefa.periodo, tarefa.prazo), ("tarefa", "#ABCDEF", 3, 8, 5, 12))

    def test_eventos_vazios_ou_preenchidos_com_terminador_opcional(self):
        for eventos in ("", ";", "qualquer coisa,SEM validar!?", "qualquer coisa,SEM validar!?;"):
            with self.subTest(eventos=eventos):
                estado, _, _ = self.carregar("rm;0;1;\n-2;abcdef;0;1;5;5;" + eventos)
                self.assertEqual((estado.tarefas[0].id, estado.tarefas[0].cor), (-2, "#ABCDEF"))

    def test_eventos_vazios_sem_ponto_e_virgula_final(self):
        estado, algoritmo, avisos = self.carregar("RM;0;1\n1;ABCDEF;0;2;5;5")
        self.assertEqual((algoritmo, avisos), ("RM", []))
        self.assertEqual(estado.tarefas[0].duracao, 2)

    def test_integracao_passo_a_passo_e_retrocesso(self):
        from engine import Simulacao

        estado, algoritmo, _ = self.carregar("RM;0;1\n1;ABCDEF;0;2;5;5;")
        sim = Simulacao(estado, algoritmo)
        sim.avancar()
        primeiro = sim.historico[sim.instante_atual]
        self.assertEqual(primeiro.tick, 1)
        self.assertEqual(primeiro.tarefas[0].tempo_exec_instancia, 1)
        sim.retroceder()
        self.assertIs(sim.historico[sim.instante_atual], estado)
        self.assertEqual(estado.tarefas[0].tempo_exec_instancia, 0)
        sim.avancar()
        self.assertIs(sim.historico[sim.instante_atual], primeiro)

    def test_ids_numericos_nao_exigem_positividade(self):
        estado, _, _ = self.carregar("RM;0;1\n0;000000;0;1;2;2;\n+002;FFFFFF;0;1;3;3;")
        self.assertEqual([tarefa.id for tarefa in estado.tarefas], [0, 2])

    def test_rejeita_formato_invalido_com_linha_fisica(self):
        casos = [
            ("", 1, "cabeçalho"),
            ("\n  \n", 1, "cabeçalho"),
            ("\nRM;0\n", 2, "3 campos"),
            ("RM;0;1;extra\n", 1, "3 campos"),
            ("RM;0;1;;\n", 1, "3 campos"),
            ("RM;0;1\n\n", 3, "tarefa"),
            ("RM;0;1\n\n1;FFFFFF;0;1;2", 3, "7 campos"),
            ("RM;0;1\n1;FFFFFF;0;1;2;2;evento;extra", 2, "7 campos"),
            ("RM;0;1\n1;FFFFFF;0;1;2;2;;;", 2, "7 campos"),
        ]
        for texto, linha, motivo in casos:
            with self.subTest(texto=texto):
                with self.assertRaisesRegex(ValueError, rf"[Ll]inha {linha}:.*{motivo}"):
                    self.carregar(texto)

    def test_rejeita_cabecalho_invalido(self):
        for cabecalho, motivo in [
            ("FIFO;0;1", "algoritmo"), (";0;1", "algoritmo"),
            ("RM;-1;1", "quantum"), ("RM;1.5;1", "quantum"),
            ("RM;;1", "quantum"), ("RM;0;0", "qtde_cpus"),
            ("RM;0;-2", "qtde_cpus"), ("RM;0;dois", "qtde_cpus"),
        ]:
            with self.subTest(cabecalho=cabecalho):
                with self.assertRaisesRegex(ValueError, rf"[Ll]inha 1:.*{motivo}"):
                    self.carregar(cabecalho + "\n1;FFFFFF;0;1;2;2;")

    def test_rejeita_dados_de_tarefa_invalidos_sem_preencher_defaults(self):
        for indice, nome, valores in [
            (0, "id", [""]),
            (1, "cor", ["", "FFF", "#12345G", "##ABCDEF", "1234567"]),
            (2, "ingresso", ["", "-1", "1.5", "texto"]),
            (3, "duracao", ["", "0", "-1", "1.5"]),
            (4, "periodo", ["", "-1", "texto"]),
            (5, "prazo", ["", "0", "-1", "texto"]),
        ]:
            for valor in valores:
                with self.subTest(campo=nome, valor=valor):
                    campos = ["1", "ABCDEF", "0", "1", "5", "5", ""]
                    campos[indice] = valor
                    with self.assertRaisesRegex(ValueError, rf"[Ll]inha 4:.*{nome}"):
                        self.carregar("\nRM;0;1\n\n" + ";".join(campos))

    def test_rejeita_ids_duplicados_apos_normalizacao_inclusive_ignorados(self):
        for primeiro, segundo in [("1", "01"), ("TaReFa", "tarefa")]:
            for periodo in (0, 5):
                with self.subTest(ids=(primeiro, segundo), periodo=periodo):
                    texto = (f"RM;0;1\n{primeiro};ABCDEF;0;1;{periodo};5;\n"
                             f"{segundo};000000;0;1;5;5;")
                    with self.assertRaisesRegex(ValueError, r"[Ll]inha 3:.*id.*duplicado"):
                        self.carregar(texto)

    def test_rejeita_cores_repetidas_em_tarefas_incluidas(self):
        with self.assertRaisesRegex(ValueError, r"[Ll]inha 3:.*cor.*repetida"):
            self.carregar("RM;0;1\n1;abcdef;0;1;5;5;\n2;#ABCDEF;0;1;5;5;")

    def test_ignora_aperiodicas_com_aviso_e_nao_reserva_cor(self):
        estado, algoritmo, avisos = self.carregar(
            "RM;0;1\n\nA;abcdef;0;1;0;5;nao validar\nB;ABCDEF;0;1;5;5;\nC;ABCDEF;0;1;0;5;"
        )
        self.assertEqual([tarefa.id for tarefa in estado.tarefas], ["b"])
        self.assertEqual(algoritmo, "RM")
        self.assertEqual(len(avisos), 2)
        for aviso, linha, identificador in zip(avisos, (3, 5), ("a", "c")):
            self.assertIsInstance(aviso, str)
            self.assertIn(f"Linha {linha}:", aviso)
            self.assertIn(repr(identificador), aviso)
            self.assertIn("aperiódica", aviso)
            self.assertIn("ignorada", aviso)
            self.assertIn("Projeto A", aviso)

    def test_apenas_aperiodicas_retorna_estado_vazio_com_aviso(self):
        estado, algoritmo, avisos = self.carregar("EDF;0;2\n1;FFFFFF;0;1;0;5;")
        self.assertEqual((estado.tick, estado.tarefas, algoritmo), (0, [], "EDF"))
        self.assertEqual(len(estado.cpus), 2)
        self.assertEqual(len(avisos), 1)

    def test_valida_dados_mesmo_em_tarefa_aperiodica(self):
        with self.assertRaisesRegex(ValueError, r"[Ll]inha 2:.*duracao"):
            self.carregar("RM;0;1\n1;FFFFFF;0;0;0;5;")

    def test_erro_de_io_informa_caminho_e_motivo(self):
        from parser import carregar_configuracao

        for caminho in (self.pasta / "nao existe.txt", self.pasta):
            with self.subTest(caminho=caminho):
                with self.assertRaises(OSError) as contexto:
                    carregar_configuracao(caminho)
                self.assertIn(str(caminho), str(contexto.exception))
                self.assertIn("Não foi possível ler", str(contexto.exception))
                self.assertIsNotNone(contexto.exception.errno)

    def test_erro_de_utf8_informa_caminho_e_motivo(self):
        from parser import carregar_configuracao

        caminho = self.pasta / "invalido.txt"
        caminho.write_bytes(b"RM;0;1\n1;FFFFFF;0;1;5;5;\xff")
        with self.assertRaisesRegex(ValueError, "UTF-8") as contexto:
            carregar_configuracao(caminho)
        self.assertIn(str(caminho), str(contexto.exception))
        self.assertIn("decodificar", str(contexto.exception))
        self.assertIsInstance(contexto.exception.__cause__, UnicodeDecodeError)

    def test_aceita_nome_sem_extensao_e_caminho_string(self):
        from parser import carregar_configuracao

        pasta = self.pasta / "outra pasta"
        pasta.mkdir()
        caminho = pasta / "qualquer nome sem extensão"
        caminho.write_text("RM;0;1\n1;ABCDEF;0;1;5;5;", encoding="utf-8")
        estado, algoritmo, _ = carregar_configuracao(str(caminho))
        self.assertEqual((algoritmo, len(estado.tarefas)), ("RM", 1))

    def test_nao_impoe_maximos_artificiais_a_tarefas_cpus_ou_tempos(self):
        registros = [f"{i};{i:06X};100000;2;1000000;2000000;" for i in range(300)]
        estado, _, _ = self.carregar("RM;100000;128\n" + "\n".join(registros))
        self.assertEqual((len(estado.tarefas), len(estado.cpus), estado.quantum), (300, 128, 100000))
        self.assertEqual(estado.tarefas[-1].prazo, 2000000)

    def test_integracao_executa_dez_ocorrencias_por_tarefa_em_rm_e_edf(self):
        from engine import Simulacao

        for algoritmo in ("RM", "EDF"):
            with self.subTest(algoritmo=algoritmo):
                estado, algoritmo_lido, avisos = self.carregar(
                    algoritmo + ";0;2\n1;FF0000;0;1;3;2;\nTarefa;00FF00;2;2;5;4;"
                )
                simulacao = Simulacao(estado, algoritmo_lido)
                final = simulacao.executar_completa()
                self.assertEqual(avisos, [])
                self.assertEqual(final.tick, 49)
                for tarefa in final.tarefas:
                    self.assertEqual(tarefa.instancias_concluidas, 10)
                    self.assertEqual(tarefa.estado_tarefa, EstadoTarefa.FINALIZADA)
                conclusoes = [evento for snapshot in simulacao.historico
                              for evento in snapshot.eventos if evento["tipo"] == "conclusao"]
                for identificador in (1, "tarefa"):
                    self.assertEqual(sum(evento["id_tarefa"] == identificador for evento in conclusoes), 10)
                self.assertEqual(estado.tick, 0)
                self.assertTrue(all(tarefa.instancias_concluidas == 0 for tarefa in estado.tarefas))


if __name__ == "__main__":
    unittest.main()
