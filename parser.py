"""Leitura do arquivo de configuração do Projeto A, sem interface gráfica."""

import re

from models import Cpu, EstadoSimulacao, TCB


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


def carregar_configuracao(caminho):
    """Retorna (EstadoSimulacao, algoritmo RM/EDF, lista de avisos).

    O arquivo deve ser UTF-8, com ou sem BOM. Campos obrigatórios não recebem
    defaults. A lista de eventos é lida como um campo opaco do Projeto B.
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
    registros = [(numero, texto.strip()) for numero, texto in enumerate(linhas, 1) if texto.strip()]
    if not registros:
        raise ValueError("Linha 1: cabeçalho ausente.")
    linha, texto = registros[0]
    algoritmo, quantum, quantidade_cpus = _campos(texto, 3, linha)
    algoritmo = algoritmo.upper()
    if algoritmo not in ("RM", "EDF"):
        raise ValueError(f"Linha {linha}: algoritmo deve ser RM ou EDF; recebido {algoritmo!r}.")
    quantum = _inteiro(quantum, "quantum", 0, linha)
    quantidade_cpus = _inteiro(quantidade_cpus, "qtde_cpus", 1, linha)
    if len(registros) == 1:
        raise ValueError(f"Linha {len(linhas) + 1}: esperado pelo menos um registro de tarefa.")

    tarefas = []
    avisos = []
    ids = set()
    cores = set()
    for linha, texto in registros[1:]:
        identificador, cor, ingresso, duracao, periodo, prazo, eventos = _campos(texto, 7, linha)
        if not identificador:
            raise ValueError(f"Linha {linha}: id da tarefa não pode ser vazio.")
        # Preserva a compatibilidade com IDs inteiros sem restringir IDs textuais.
        try:
            identificador = int(identificador)
        except ValueError:
            identificador = identificador.casefold()
        if identificador in ids:
            raise ValueError(f"Linha {linha}: id duplicado: {identificador!r}.")
        ids.add(identificador)
        if not re.fullmatch(r"#?[0-9a-fA-F]{6}", cor):
            raise ValueError(f"Linha {linha}: cor deve ser RGB hexadecimal com 6 dígitos (# opcional).")
        cor = "#" + cor.removeprefix("#").upper()
        ingresso = _inteiro(ingresso, "ingresso", 0, linha)
        duracao = _inteiro(duracao, "duracao", 1, linha)
        periodo = _inteiro(periodo, "periodo", 0, linha)
        prazo = _inteiro(prazo, "prazo", 1, linha)
        # Valida o registro antes de ignorá-lo; um período zero não encobre erros.
        if periodo == 0:
            avisos.append(f"Linha {linha}: tarefa {identificador!r} aperiódica ignorada no Projeto A.")
            continue
        if cor in cores:
            raise ValueError(f"Linha {linha}: cor repetida {cor}; cada tarefa incluída deve ter cor diferente.")
        cores.add(cor)
        tarefas.append(TCB(identificador, cor, ingresso, duracao, periodo, prazo))
    estado = EstadoSimulacao(0, tarefas, [Cpu(i) for i in range(quantidade_cpus)], quantum)
    return estado, algoritmo, avisos
