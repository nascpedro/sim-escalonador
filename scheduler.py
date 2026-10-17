import random
from models import TCB, EstadoTarefa

def escalonar(fila_prontos: list, algoritmo: str) -> list:
    # Faz uma cópia da lista para ordenar sem bagunçar a original
    tarefas_ordenadas = list(fila_prontos)
    
    # Critério 5 de desempate: embaralha antes para que empates totais sejam decididos no sorteio
    random.shuffle(tarefas_ordenadas)

    def chave_prioridade(tarefa: TCB):
        # Define o critério principal de acordo com o algoritmo
        if algoritmo.upper() == "RM":
            prioridade = tarefa.periodo
        elif algoritmo.upper() == "EDF":
            prioridade = tarefa.prazo_absoluto
        else:
            prioridade = 0

        # Desempate 1: quem já estava EXECUTANDO no tick anterior ganha (0 vem antes de 1)
        ja_executava = 0 if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO else 1

        # Retorna a tupla com o critério principal + os 4 desempates em ordem
        return (
            prioridade,
            ja_executava,
            tarefa.prazo,      # Desempate 2: menor prazo
            tarefa.ingresso,   # Desempate 3: menor ingresso
            tarefa.duracao     # Desempate 4: menor duração
        )

    tarefas_ordenadas.sort(key=chave_prioridade)
    return tarefas_ordenadas