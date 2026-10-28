from models import *
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

        # 3. escalona(fila_prontos, algoritmo)
        # 4. despacha(cpus, tarefas_eleitas)
        # 5. Executa computação de [t, t+1) e atualiza prazos/conclusões

        # 6. Retorna o novo estado referente a t+1
        novo_estado.tick = t + 1
        return novo_estado