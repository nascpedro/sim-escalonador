import random
from models import TCB, EstadoTarefa

def escalonar(fila_tarefas: list, algoritmo: str, sorteios=None) -> list:
    # fila_tarefas se trata de uma fila de tarefas prontas ou em execução a serem ordenadas segundo o algorítmo ou desempate
    # Faz uma cópia da lista para ordenar sem bagunçar a original
    tarefas_ordenadas = list(fila_tarefas)
    

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
            ja_executava,      # Desempate 1
            tarefa.prazo,      # Desempate 2: menor prazo
            tarefa.ingresso,   # Desempate 3: menor ingresso
            tarefa.duracao     # Desempate 4: menor duração
        )
    #ordena de acordo com o algoritmo e desempates:
    tarefas_ordenadas.sort(key=chave_prioridade)
    # Chaves iguais ficam juntas. Sorteamos apenas dentro desses grupos,
    # sem interferir nas prioridades e nos desempates anteriores.
    inicio = 0
    while inicio < len(tarefas_ordenadas):
        fim = inicio + 1
        chave = chave_prioridade(tarefas_ordenadas[inicio])
        while fim < len(tarefas_ordenadas) and chave_prioridade(tarefas_ordenadas[fim]) == chave:
            fim += 1

        if fim - inicio > 1:
            grupo = tarefas_ordenadas[inicio:fim]
            random.shuffle(grupo)
            tarefas_ordenadas[inicio:fim] = grupo
            # O argumento opcional recebe os IDs na ordem definida pelo sorteio.
            if sorteios is not None:
                sorteios.append([tarefa.id for tarefa in grupo])
        inicio = fim

    return tarefas_ordenadas