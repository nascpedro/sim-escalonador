"""Sugestões de entrada compartilhadas pelo arquivo e pelos formulários."""
ALGORITMO = 'RM'
QUANTUM = 0  # sem limite de fatia, mantendo preempção
QUANTIDADE_CPUS = 2
INGRESSO = 0
DURACAO = 1
PERIODO = 10
PRAZO = 10
ESCALA_GANTT = 24.0
NOME_SVG = 'gantt.svg'

CORES = ('#2DD4BF', '#60A5FA', '#C084FC', '#FBBF24',
         '#FB7185', '#A3E635', '#F97316', '#22D3EE')


def sugerir_tarefa(ids=(), cores=(), tick=INGRESSO):
    """ID e cor disponíveis; a chegada de uma inclusão manual começa no tick atual."""
    identificador = 1
    while identificador in ids:
        identificador += 1
    usadas = {'#' + cor.lstrip('#').upper() for cor in cores}
    cor = next((c for c in CORES if c not in usadas), None)
    # O passo ímpar percorre o espaço RGB sem ficar limitado às oito cores iniciais.
    indice = 0
    while cor is None:
        candidata = f'#{(0x4F86C6 + indice * 0x9E3779) % 0x1000000:06X}'
        if candidata not in usadas:
            cor = candidata
        indice += 1
    return dict(id_tarefa=identificador, cor=cor, ingresso=tick,
                duracao=DURACAO, periodo=PERIODO, prazo=PRAZO)
