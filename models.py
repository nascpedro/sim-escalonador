from enum import Enum, auto

#Definições das classes representando dados a serem usados na simulação (TCB, CPU, Estado/Snapshot)

#Task Control Block (TCB) - Estrutura de dados que representa uma tarefa
class TCB:
    def __init__(self, id_tarefa: int | str, cor: str, ingresso: int, duracao:int, periodo:int, prazo:int):
    #atributos estaticos (serão lidos do arquivo de inicialização):
        self.id = id_tarefa
        self.cor = cor 
        self.ingresso = ingresso
        self.duracao = duracao
        self.periodo = periodo
        self.prazo = prazo

    #atributos dinâmicos (alteram a cada tick durante a simulação):
        self.estado_tarefa = EstadoTarefa.AGUARDANDO #AGUARDANDO, PRONTA, EXECUTANDO, SUSPENSA, FINALIZADA
        self.id_cpu_atual = None
        self.tempo_exec_instancia = 0 #Quanto tempo a tarefa executou no ciclo atual
        self.prazo_absoluto = ingresso + prazo
        self.instancias_concluidas = 0 
        self.perdeu_prazo = False


class EstadoTarefa(Enum):
    AGUARDANDO = auto() # Ainda não ingressou ou espera o próximo período
    PRONTA = auto()     # Na fila de prontos aguardando CPU
    EXECUTANDO = auto() # Alocada em um núcleo
    SUSPENSA = auto()   # Bloqueada (necessária para Gantt / Requisito 2.1)
    FINALIZADA = auto() # Já completou 10 instâncias

class Cpu:
    def __init__(self, id_cpu: int):
        self.id_cpu = id_cpu
        self.id_tarefa_alocada = None #recebe o id da tarefa alocada 
        self.tempo_desligada = 0

class EstadoSimulacao:
    def __init__(self, tick:int, tarefas:list, cpus: list, quantum: int):
        self.tick = tick
        self.tarefas = tarefas
        self.cpus = cpus
        self.quantum = quantum
        # Eventos do intervalo que produziu este estado; os anteriores ficam no histórico.
        self.eventos = []

        


        
