"""Regras básicas compartilhadas pelo parser e pelas intervenções no motor.

A conversão de texto e o contexto da mensagem (linha ou formulário) ficam com
quem recebe a entrada. Aqui validamos os valores já convertidos.
"""
import re


def validar_inteiro(valor, nome, minimo):
    """Rejeita também bool: True não é uma duração ou quantidade de CPUs."""
    if type(valor) is not int or valor < minimo:
        raise ValueError(f'{nome} deve ser inteiro maior ou igual a {minimo}.')
    return valor


def normalizar_cor(valor):
    """Valida RGB de seis dígitos e devolve a representação #RRGGBB."""
    if not isinstance(valor, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', valor):
        raise ValueError('cor deve ser RGB hexadecimal de seis dígitos.')
    return '#' + valor.lstrip('#').upper()


def validar_algoritmo(valor):
    if not isinstance(valor, str) or valor.upper() not in ('RM', 'EDF'):
        raise ValueError('algoritmo deve ser RM ou EDF.')
    return valor.upper()
