import random
from models import TCB, EstadoTarefa


def chave_prioridade(tarefa: TCB, algoritmo: str) -> tuple:
    """Tupla de prioridade principal (RM ou EDF) seguida dos 4 desempates determinísticos."""
    if algoritmo.upper() == "RM":
        prioridade = tarefa.periodo
    elif algoritmo.upper() == "EDF":
        prioridade = tarefa.prazo_absoluto
    else:
        prioridade = 0

    # Desempate 1: quem já estava EXECUTANDO no tick anterior ganha (0 vem antes de 1)
    ja_executava = 0 if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO else 1

    return (
        prioridade,
        ja_executava,      # Desempate 1: manter tarefa já em execução
        tarefa.prazo,      # Desempate 2: menor prazo relativo
        tarefa.ingresso,   # Desempate 3: menor instante de ingresso
        tarefa.duracao,    # Desempate 4: menor duração
    )


def _desempatar_por_sorteio(tarefas_ordenadas: list, algoritmo: str, sorteios) -> None:
    """5º critério de desempate: sorteia apenas subgrupos com todas as chaves anteriores iguais."""
    inicio = 0
    while inicio < len(tarefas_ordenadas):
        fim = inicio + 1
        chave = chave_prioridade(tarefas_ordenadas[inicio], algoritmo)
        while fim < len(tarefas_ordenadas) and chave_prioridade(tarefas_ordenadas[fim], algoritmo) == chave:
            fim += 1

        if fim - inicio > 1:
            grupo = tarefas_ordenadas[inicio:fim]
            random.shuffle(grupo)
            tarefas_ordenadas[inicio:fim] = grupo
            if sorteios is not None:
                sorteios.append([tarefa.id for tarefa in grupo])
        inicio = fim


def escalonar(fila_tarefas: list, algoritmo: str, sorteios=None) -> list:
    """Ordena candidatas prontas/executando segundo o algoritmo e critérios de desempate."""
    tarefas_ordenadas = sorted(
        fila_tarefas, key=lambda tarefa: chave_prioridade(tarefa, algoritmo)
    )
    _desempatar_por_sorteio(tarefas_ordenadas, algoritmo, sorteios)
    return tarefas_ordenadas
