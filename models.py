from enum import Enum, auto
import copy

#Definições das classes representando dados a serem usados na simulação (TCB, CPU, Estado/Snapshot)

#Task Control Block (TCB) - Estrutura de dados que representa uma tarefa
class TCB:
    def __init__(self, id_tarefa: int, cor: str, ingresso: int, duracao:int, periodo:int, prazo:int):
    #atributos estaticos (serão lidos do arquivo de inicialização):
        self.id = id_tarefa
        self.cor = cor 
        self.ingresso = ingresso
        self.duracao = duracao
        self.periodo = periodo
        self.prazo = prazo

    #atributos dinâmicos (alteram a cada tick durante a simulação):
        self.estado_tarefa = None #AGUARDANDO, PRONTA, EXECUTANDO, SUSPENSA, FINALIZADA
        self.cpu_atual_id = 0
        self.tempo_exec_instancia = 0 #Quanto tempo a tarefa executou no ciclo atual
        self.deadline_absoluto = ingresso + prazo
        self.instancias_concluidas = 0 
        self.perdeu_prazo = 0


class EstadoTarefa(Enum):
    AGUARDANDO = auto() # Ainda não ingressou ou espera o próximo período
    PRONTA = auto()     # Na fila de prontos aguardando CPU
    EXECUTANDO = auto() # Alocada em um núcleo
    SUSPENSA = auto()   # Bloqueada (necessária para Gantt / Requisito 2.1)
    FINALIZADA = auto() # Já completou 10 instâncias

class Cpu:
    def __init__(self, id_cpu: int, tarefa_alocada: int):
        self.id_cpu = id_cpu
        self.tarefa_alocada = tarefa_alocada #recebe o id da tarefa alocada 
        self.tempo_desligada = 0

class EstadoSimulacao:
    def __init__(self, tick:int, tarefas:list, cpus: list, quantum: int):
        self.tick = tick
        self.tarefas = tarefas
        self.cpus = cpus
        self.quantum = quantum

        


        
