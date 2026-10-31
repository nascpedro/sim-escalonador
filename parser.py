"""Leitura do arquivo de configuração do Projeto A, sem interface gráfica."""

import re

from models import Cpu, EstadoSimulacao, TCB, normalizar_id
import padroes


def _campos(texto, quantidade, linha):
    """Separa campos, removendo apenas um terminador opcional extra."""
    campos = [campo.strip() for campo in texto.split(";")]
    # No Projeto A, a lista de eventos vazia também pode vir sem o ';' final.
    if quantidade == 7 and len(campos) == 6:
        campos.append("")
    # Não remover o sétimo campo vazio: ele representa a lista de eventos.
    if len(campos) == quantidade + 1 and campos[-1] == "":
        campos.pop()
    if len(campos) != quantidade:
        raise ValueError(f"Linha {linha}: esperados {quantidade} campos; encontrados {len(campos)}.")
    return campos


def _inteiro(texto, nome, minimo, linha):
    """Converte um campo numérico e explica qual limite foi desrespeitado."""
    try:
        valor = int(texto)
    except ValueError as erro:
        raise ValueError(f"Linha {linha}: {nome} deve ser inteiro; recebido {texto!r}.") from erro
    if valor < minimo:
        raise ValueError(f"Linha {linha}: {nome} deve ser maior ou igual a {minimo}; recebido {valor}.")
    return valor


def _preencher_padroes(campos, nomes, valores, linha, avisos):
    """Campo vazio é opção pelo padrão; valor informado nunca é substituído."""
    for i, (nome, valor) in enumerate(zip(nomes, valores)):
        if campos[i] == '':
            campos[i] = str(valor)
            avisos.append(f'Linha {linha}: {nome} vazio; usado padrão {valor!r}.')
    return campos


def _ler_cabecalho(texto, linha, avisos):
    """Lê algoritmo, quantum e quantidade de CPUs da primeira linha útil."""
    campos = _campos(texto, 3, linha)
    algoritmo, quantum, quantidade_cpus = _preencher_padroes(campos,
        ('algoritmo', 'quantum', 'qtde_cpus'),
        (padroes.ALGORITMO, padroes.QUANTUM, padroes.QUANTIDADE_CPUS), linha, avisos)
    algoritmo = algoritmo.upper()
    if algoritmo not in ("RM", "EDF"):
        raise ValueError(f"Linha {linha}: algoritmo deve ser RM ou EDF; recebido {algoritmo!r}.")
    quantum = _inteiro(quantum, "quantum", 0, linha)
    quantidade_cpus = _inteiro(quantidade_cpus, "qtde_cpus", 1, linha)
    return algoritmo, quantum, quantidade_cpus


def _ler_tarefa(campos, linha, ids_existentes):
    """Converte um registro em TCB, sem modificar o conjunto de IDs recebido.

    O ID é verificado primeiro para preservar a ordem das mensagens de erro.
    Uma tarefa aperiódica também é validada; o carregador decide ignorá-la.
    """
    identificador, cor, ingresso, duracao, periodo, prazo, eventos = campos
    identificador = normalizar_id(identificador)
    if identificador in ids_existentes:
        raise ValueError(f"Linha {linha}: id duplicado: {identificador!r}.")
    if not re.fullmatch(r"#?[0-9a-fA-F]{6}", cor):
        raise ValueError(f"Linha {linha}: cor deve ser RGB hexadecimal com 6 dígitos (# opcional).")
    cor = "#" + cor.removeprefix("#").upper()
    ingresso = _inteiro(ingresso, "ingresso", 0, linha)
    duracao = _inteiro(duracao, "duracao", 1, linha)
    periodo = _inteiro(periodo, "periodo", 0, linha)
    prazo = _inteiro(prazo, "prazo", 1, linha)
    return TCB(identificador, cor, ingresso, duracao, periodo, prazo)


def carregar_configuracao(caminho):
    """Retorna (EstadoSimulacao, algoritmo RM/EDF, lista de avisos).

    O arquivo deve ser UTF-8, com ou sem BOM. Campos de configuração vazios
    recebem padrões com aviso; formato errado e valores inválidos são erros.
    A lista de eventos é lida como um campo opaco do Projeto B.
    IDs numéricos viram int; os demais usam casefold. Cores viram #RRGGBB,
    e CPUs são numeradas a partir de zero. IDs são únicos em todo o arquivo;
    cores só precisam ser únicas entre as tarefas periódicas incluídas.
    Registros aperiódicos válidos geram avisos, mesmo se nenhum for incluído.
    Conteúdo inválido gera ValueError com linha física (ausência usa a linha
    esperada). Falhas de leitura/UTF-8 informam caminho e motivo; I/O usa OSError.
    Quantum é apenas armazenado, sem atribuir política de execução aqui.
    """
    try:
        with open(caminho, encoding="utf-8-sig") as arquivo:
            linhas = arquivo.readlines()
    except OSError as erro:
        raise OSError(erro.errno, f"Não foi possível ler {caminho}: {erro.strerror}", erro.filename) from erro
    except UnicodeDecodeError as erro:
        raise ValueError(f"Não foi possível decodificar {caminho} como UTF-8: {erro}") from erro
    registros = []
    for numero, texto in enumerate(linhas, 1):
        texto = texto.strip()
        if texto:
            registros.append((numero, texto))
    if not registros:
        raise ValueError("Linha 1: cabeçalho ausente.")
    linha, texto = registros[0]
    avisos = []
    algoritmo, quantum, quantidade_cpus = _ler_cabecalho(texto, linha, avisos)
    if len(registros) == 1:
        raise ValueError(f"Linha {len(linhas) + 1}: esperado pelo menos um registro de tarefa.")

    tarefas = []
    ids = set()
    cores = set()
    linhas_tarefas = [(linha, _campos(texto, 7, linha)) for linha, texto in registros[1:]]
    # Reserva os valores explícitos de todo o arquivo: uma sugestão na primeira
    # linha não pode ocupar o ID ou a cor que o usuário informou numa linha posterior.
    reservados = {normalizar_id(c[0]) for _, c in linhas_tarefas if c[0]}
    cores_reservadas = {c[1].lstrip('#').upper() for _, c in linhas_tarefas if c[1]}
    for linha, campos in linhas_tarefas:
        sugestao = padroes.sugerir_tarefa(reservados, cores_reservadas)
        _preencher_padroes(campos, ('id', 'cor', 'ingresso', 'duracao', 'periodo', 'prazo'),
                          (sugestao['id_tarefa'], sugestao['cor'], sugestao['ingresso'],
                           sugestao['duracao'], sugestao['periodo'], sugestao['prazo']), linha, avisos)
        tarefa = _ler_tarefa(campos, linha, ids)
        reservados.add(tarefa.id)
        cores_reservadas.add(tarefa.cor.lstrip('#'))
        ids.add(tarefa.id)
        # Valida o registro antes de ignorá-lo; um período zero não encobre erros.
        if tarefa.periodo == 0:
            avisos.append(f"Linha {linha}: tarefa {tarefa.id!r} aperiódica ignorada no Projeto A.")
            continue
        if tarefa.cor in cores:
            raise ValueError(f"Linha {linha}: cor repetida {tarefa.cor}; cada tarefa incluída deve ter cor diferente.")
        cores.add(tarefa.cor)
        tarefas.append(tarefa)
    estado = EstadoSimulacao(0, tarefas, [Cpu(i) for i in range(quantidade_cpus)], quantum)
    return estado, algoritmo, avisos
