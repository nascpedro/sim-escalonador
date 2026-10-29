from models import *
from scheduler import escalonar
import copy

class Simulacao:
    def __init__(self, estado_inicial: EstadoSimulacao, algoritmo: str):
        self.algoritmo = algoritmo
        # O histórico guarda cada estado da simulação
        self.historico = [estado_inicial]
        self.instante_atual = 0 # aponta para o instante de tempo atual da simulação



    def avancar(self, passos: int = 1) -> None:
        for _ in range(passos):
            # Se o futuro já consta no histórico, basta avançar o instante
            if self.instante_atual < len(self.historico) - 1:
                self.instante_atual += 1
            else:
                # Calcula o próximo tick [t, t+1)
                novo_estado = self._executar_um_tick(self.historico[self.instante_atual])
                self.historico.append(novo_estado)
                self.instante_atual += 1

    def executar_completa(self) -> EstadoSimulacao:
        # Executa até todas as tarefas estarem FINALIZADA, sem limite de passos.
        while True:
            estado = self.historico[self.instante_atual]
            pendentes = []
            for tarefa in estado.tarefas:
                if tarefa.estado_tarefa != EstadoTarefa.FINALIZADA:
                    pendentes.append(tarefa)

            # Retorna assim que não houver tarefas pendentes, sem criar ticks extras.
            if not pendentes:
                return estado

            if not estado.cpus:
                raise RuntimeError("Execução completa interrompida: há tarefas pendentes, mas nenhuma CPU.")
            for tarefa in pendentes:
                # O motor atual não possui evento automático para retirar a suspensão.
                if tarefa.estado_tarefa == EstadoTarefa.SUSPENSA:
                    raise RuntimeError(
                        f"Execução completa interrompida: tarefa {tarefa.id} suspensa. "
                        "Altere seu estado manualmente antes de continuar."
                    )


            # Reutiliza o histórico quando existe; calcula um novo tick apenas no fim.
            self.avancar()

    def retroceder(self, passos: int = 1) -> None:
        # Retrocede simulação com base no histórico
        self.instante_atual = max(0, self.instante_atual - passos)

    def modificar_tarefa_em_execucao(self, id_tarefa: int, nova_tarefa_modificada: TCB) -> None:
        # Removemos o histórico futuro da lista caso estejamos no passado
        del self.historico[self.instante_atual + 1:]
        
        # Atualiza a tarefa no estado atual
        estado_ativo = self.historico[self.instante_atual]
        for i, tarefa in enumerate(estado_ativo.tarefas):
            if tarefa.id == id_tarefa:
                estado_ativo.tarefas[i] = copy.deepcopy(nova_tarefa_modificada)
                break

    def _executar_um_tick(self, estado_ant: EstadoSimulacao) -> EstadoSimulacao:
        # 1. Clona estado_ant para não sobrescrever a foto do tick t
        novo_estado = copy.deepcopy(estado_ant)
        t = estado_ant.tick
        novo_estado.eventos = []

        # 2. Ativa novas instâncias periódicas que chegam no tick
        for tarefa in novo_estado.tarefas:
            if tarefa.instancias_concluidas >= 10:
                tarefa.estado_tarefa = EstadoTarefa.FINALIZADA
                continue

            # Verifica se é o instante de chegada (ingresso ou múltiplo do período)
            if t >= tarefa.ingresso and (t - tarefa.ingresso) % tarefa.periodo == 0:
                if tarefa.estado_tarefa == EstadoTarefa.AGUARDANDO:
                    tarefa.estado_tarefa = EstadoTarefa.PRONTA
                    tarefa.tempo_exec_instancia = 0
                    tarefa.prazo_absoluto = t + tarefa.prazo
                    tarefa.perdeu_prazo = False

        # 3. Prontas e executando disputam CPU; preservamos os estados para o desempate.
        candidatas = []
        for tarefa in novo_estado.tarefas:
            if tarefa.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO):
                candidatas.append(tarefa)

        # A política retorna a ordem de preferência sem reordenar a lista de todas as tarefas.
        sorteios = []
        tarefas_ordenadas = escalonar(candidatas, self.algoritmo, sorteios)
        # Guarda o instante real da decisão, não o tick t+1 do estado retornado.
        ids_selecionadas = [tarefa.id for tarefa in tarefas_ordenadas[:len(novo_estado.cpus)]]
        for ordem in sorteios:
            novo_estado.eventos.append({
                'tipo': 'sorteio',
                'tick': t,
                'ordem': ordem,
                'selecionadas': [id_tarefa for id_tarefa in ordem if id_tarefa in ids_selecionadas]
            })
        # 4. Refaz as alocações após a decisão; o escalonador já usou quem executava.
        for tarefa in novo_estado.tarefas:
            tarefa.id_cpu_atual = None
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO:
                tarefa.estado_tarefa = EstadoTarefa.PRONTA

        for indice, cpu in enumerate(novo_estado.cpus):
            cpu.id_tarefa_alocada = None
            if indice < len(tarefas_ordenadas):
                tarefa = tarefas_ordenadas[indice]
                cpu.id_tarefa_alocada = tarefa.id
                tarefa.id_cpu_atual = cpu.id_cpu
                tarefa.estado_tarefa = EstadoTarefa.EXECUTANDO
        # CPUs sem tarefa ficam livres; o tempo desligado será contado na etapa 5.

        # 5. Executa [t, t+1). Uma CPU que trabalhou não conta como desligada,
        # mesmo que sua tarefa termine e libere a CPU no fim do intervalo.
        for cpu in novo_estado.cpus:
            if cpu.id_tarefa_alocada is None:
                cpu.tempo_desligada += 1
                novo_estado.eventos.append({
                    'tipo': 'cpu_desligada', 'tick': t, 'id_cpu': cpu.id_cpu
                })

        for tarefa in novo_estado.tarefas:
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO:
                tarefa.tempo_exec_instancia += 1
                # Preserva quem executou neste intervalo, mesmo após liberar a CPU.
                novo_estado.eventos.append({
                    'tipo': 'execucao', 'tick': t,
                    'id_tarefa': tarefa.id, 'id_cpu': tarefa.id_cpu_atual
                })
                if tarefa.tempo_exec_instancia >= tarefa.duracao:
                    tarefa.instancias_concluidas += 1
                    if tarefa.instancias_concluidas >= 10:
                        tarefa.estado_tarefa = EstadoTarefa.FINALIZADA
                    else:
                        tarefa.estado_tarefa = EstadoTarefa.AGUARDANDO
                    for cpu in novo_estado.cpus:
                        if cpu.id_tarefa_alocada == tarefa.id:
                            cpu.id_tarefa_alocada = None
                    tarefa.id_cpu_atual = None
                    novo_estado.eventos.append({
                        'tipo': 'conclusao', 'tick': t + 1,
                        'id_tarefa': tarefa.id, 'instancia': tarefa.instancias_concluidas
                    })

        # Verifica o prazo após as conclusões: terminar exatamente no limite é válido.
        # Prontas e suspensas também podem perder prazo, mesmo sem receber CPU.
        for tarefa in novo_estado.tarefas:
            if tarefa.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO, EstadoTarefa.SUSPENSA):
                if t + 1 >= tarefa.prazo_absoluto and not tarefa.perdeu_prazo:
                    tarefa.perdeu_prazo = True
                    novo_estado.eventos.append({
                        'tipo': 'perda_prazo', 'tick': t + 1, 'id_tarefa': tarefa.id
                    })

        # 6. Retorna o novo estado referente a t+1
        novo_estado.tick = t + 1
        return novo_estado