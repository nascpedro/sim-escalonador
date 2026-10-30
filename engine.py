from models import *
from scheduler import escalonar
import copy
import re

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

    def modificar_tarefa_em_execucao(self, id_tarefa: int | str, **alteracoes) -> None:
        """Edita ingresso, duracao, periodo, prazo, cor ou estado_tarefa.

        Exemplo: modificar_tarefa_em_execucao(1, duracao=4).
        CPU, progresso, contadores e prazo absoluto são administrados pelo motor.
        PRONTA e SUSPENSA preservam uma ocorrência ativa; AGUARDANDO a abandona.
        Rejeições preservam o histórico; aceitação descarta somente o futuro.
        """
        estado = self.historico[self.instante_atual]
        indice = None
        for i, tarefa in enumerate(estado.tarefas):
            if tarefa.id == id_tarefa:
                indice = i
                break
        if indice is None:
            raise ValueError(f"Tarefa {id_tarefa!r} não encontrada.")
        if not alteracoes:
            return

        # Valida apenas a entrada da edição, não a estrutura inteira do TCB.
        limites = {'ingresso': 0, 'duracao': 1, 'periodo': 1, 'prazo': 1}
        for campo, valor in alteracoes.items():
            if campo in limites:
                if type(valor) is not int or valor < limites[campo]:
                    raise ValueError(f"{campo} deve ser inteiro maior ou igual a {limites[campo]}.")
            elif campo == 'cor':
                if not isinstance(valor, str) or not re.fullmatch(r'#?[0-9a-fA-F]{6}', valor):
                    raise ValueError("cor deve ser RGB hexadecimal de seis dígitos.")
                for outra in estado.tarefas:
                    if outra.id != id_tarefa and outra.cor.lstrip('#').upper() == valor.lstrip('#').upper():
                        raise ValueError("cor já utilizada por outra tarefa.")
            elif campo == 'estado_tarefa':
                if not isinstance(valor, EstadoTarefa):
                    raise ValueError("estado_tarefa deve ser um valor de EstadoTarefa.")
            else:
                raise ValueError(f"{campo} não é um campo editável.")

        nova = copy.deepcopy(estado.tarefas[indice])
        for campo, valor in alteracoes.items():
            setattr(nova, campo, valor)

        anterior = estado.tarefas[indice]
        ativos = (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO, EstadoTarefa.SUSPENSA)
        if nova.estado_tarefa == EstadoTarefa.FINALIZADA and nova.instancias_concluidas < 10:
            raise ValueError("FINALIZADA exige dez ocorrências concluídas.")
        if nova.instancias_concluidas == 10 and nova.estado_tarefa != EstadoTarefa.FINALIZADA:
            raise ValueError("Após dez ocorrências, a tarefa não pode ser reativada.")
        if nova.estado_tarefa in ativos:
            ativacao = anterior.prazo_absoluto - anterior.prazo
            if anterior.estado_tarefa not in ativos:
                # Entrar manualmente em PRONTA/EXECUTANDO/SUSPENSA inicia uma ocorrência agora.
                ativacao = estado.tick
                nova.tempo_exec_instancia = 0
                nova.perdeu_prazo = False
            if nova.ingresso > ativacao:
                raise ValueError("ingresso não pode ser posterior à ativação da ocorrência atual.")
            if nova.tempo_exec_instancia >= nova.duracao:
                raise ValueError("duracao deve superar o tempo já executado da ocorrência ativa.")
            nova.prazo_absoluto = ativacao + nova.prazo
        elif anterior.instancias_concluidas == 0:
            nova.prazo_absoluto = nova.ingresso + nova.prazo
        if nova.estado_tarefa == EstadoTarefa.AGUARDANDO and anterior.estado_tarefa in ativos:
            # A mudança manual abandona a ocorrência atual e espera a próxima ativação.
            nova.tempo_exec_instancia = 0
            nova.perdeu_prazo = False
        if nova.prazo_absoluto != anterior.prazo_absoluto:
            # Se o novo prazo já venceu, o próximo tick registra a perda no histórico.
            nova.perdeu_prazo = False

        # EXECUTANDO mantém a CPU atual ou usa uma livre, sem migração manual.
        escolhida = None
        if nova.estado_tarefa == EstadoTarefa.EXECUTANDO:
            for cpu in estado.cpus:
                if cpu.id_tarefa_alocada == id_tarefa:
                    escolhida = cpu
                    break
                if cpu.id_tarefa_alocada is None and escolhida is None:
                    escolhida = cpu
            if escolhida is None:
                raise ValueError("Não há CPU livre para colocar a tarefa em EXECUTANDO.")
        nova.id_cpu_atual = escolhida.id_cpu if escolhida is not None else None
        if anterior.estado_tarefa != EstadoTarefa.EXECUTANDO or nova.estado_tarefa != EstadoTarefa.EXECUTANDO:
            nova.tempo_exec_quantum = 0

        # Todas as verificações terminaram. Só agora altera o estado e descarta o futuro.
        for cpu in estado.cpus:
            if cpu.id_tarefa_alocada == id_tarefa:
                cpu.id_tarefa_alocada = None
        if escolhida is not None:
            escolhida.id_tarefa_alocada = id_tarefa
        estado.tarefas[indice] = nova
        del self.historico[self.instante_atual + 1:]

    def _executar_um_tick(self, estado_ant: EstadoSimulacao) -> EstadoSimulacao:
        # 1. Clona estado_ant para não sobrescrever a foto do tick t
        novo_estado = copy.deepcopy(estado_ant)
        t = estado_ant.tick
        novo_estado.eventos = []

        # 2. Registra a chegada inicial separadamente das ativações periódicas.
        for tarefa in novo_estado.tarefas:
            if t == tarefa.ingresso:
                novo_estado.eventos.append({
                    'tipo': 'chegada', 'tick': t, 'id_tarefa': tarefa.id
                })
            if tarefa.instancias_concluidas >= 10:
                tarefa.estado_tarefa = EstadoTarefa.FINALIZADA
                continue

            # Verifica se há uma ativação prevista no ingresso ou a cada período.
            if t >= tarefa.ingresso and (t - tarefa.ingresso) % tarefa.periodo == 0:
                if tarefa.estado_tarefa == EstadoTarefa.AGUARDANDO:
                    tarefa.estado_tarefa = EstadoTarefa.PRONTA
                    tarefa.tempo_exec_instancia = 0
                    tarefa.prazo_absoluto = t + tarefa.prazo
                    tarefa.perdeu_prazo = False
                    # Só registra quando a ocorrência realmente é ativada, no instante t.
                    novo_estado.eventos.append({
                        'tipo': 'ativacao', 'tick': t, 'id_tarefa': tarefa.id
                    })

        # 3. Reavalia a cada tick, depois dos eventos, sem esperar o quantum acabar.
        # Prontas e executando disputam CPU; preserva quem executava para o desempate.
        candidatas = []
        for tarefa in novo_estado.tarefas:
            if tarefa.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO):
                candidatas.append(tarefa)

        # A política retorna a ordem de preferência sem reordenar a lista de todas as tarefas.
        sorteios = []
        tarefas_ordenadas = escalonar(candidatas, self.algoritmo, sorteios)
        # Guarda o instante real da decisão, não o tick t+1 do estado retornado.
        ids_selecionadas = [tarefa.id for tarefa in tarefas_ordenadas[:len(novo_estado.cpus)]]
        # Preserva os sorteios no início da lista, como nos snapshots anteriores.
        for indice_sorteio, ordem in enumerate(sorteios):
            novo_estado.eventos.insert(indice_sorteio, {
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
            # A fatia pertence à tarefa enquanto executa sem interrupção,
            # mesmo se o despacho a migrar para outra CPU.
            if tarefa.estado_tarefa != EstadoTarefa.EXECUTANDO:
                tarefa.tempo_exec_quantum = 0
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO:
                tarefa.tempo_exec_instancia += 1
                if novo_estado.quantum > 0:
                    tarefa.tempo_exec_quantum += 1
                # Preserva quem executou neste intervalo, mesmo após liberar a CPU.
                novo_estado.eventos.append({
                    'tipo': 'execucao', 'tick': t,
                    'id_tarefa': tarefa.id, 'id_cpu': tarefa.id_cpu_atual
                })
                if tarefa.tempo_exec_instancia >= tarefa.duracao:
                    tarefa.tempo_exec_quantum = 0
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
                elif novo_estado.quantum > 0 and tarefa.tempo_exec_quantum >= novo_estado.quantum:
                    novo_estado.eventos.append({
                        'tipo': 'fim_quantum', 'tick': t + 1,
                        'id_tarefa': tarefa.id, 'id_cpu': tarefa.id_cpu_atual
                    })
                    tarefa.tempo_exec_quantum = 0
                    # Não bloqueia nem apaga quem executava: no próximo tick,
                    # no mesmo instante t+1, RM/EDF reavaliam todas as candidatas.

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