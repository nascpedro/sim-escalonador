from models import Cpu, EstadoSimulacao, EstadoTarefa, Ocorrencia
from scheduler import escalonar
import copy
import re

class Simulacao:
    def __init__(self, estado_inicial: EstadoSimulacao, algoritmo: str):
        estado_inicial.algoritmo = algoritmo.upper()
        # O histórico guarda cada estado da simulação
        self.historico = [estado_inicial]
        self.instante_atual = 0 # aponta para o instante de tempo atual da simulação

    @property
    def algoritmo(self):
        return self.historico[self.instante_atual].algoritmo or self.historico[0].algoritmo



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

    def configurar_sistema(self, algoritmo, quantum, quantidade_cpus):
        """Valida tudo antes de substituir o snapshot; retorna se houve mudança."""
        if not isinstance(algoritmo, str) or algoritmo.upper() not in ('RM', 'EDF'):
            raise ValueError('algoritmo deve ser RM ou EDF.')
        if type(quantum) is not int or quantum < 0:
            raise ValueError('quantum deve ser inteiro maior ou igual a zero.')
        if type(quantidade_cpus) is not int or quantidade_cpus < 1:
            raise ValueError('quantidade de CPUs deve ser inteiro maior ou igual a um.')
        algoritmo = algoritmo.upper()
        anterior = self.historico[self.instante_atual]
        if (algoritmo, quantum, quantidade_cpus) == (self.algoritmo, anterior.quantum, len(anterior.cpus)):
            return False
        novo = copy.deepcopy(anterior)
        novo.algoritmo = algoritmo
        novo.quantum = quantum
        # CPUs preservadas mantêm alocação e ociosidade; novas começam livres.
        novo.cpus = novo.cpus[:quantidade_cpus]
        proximo_id = max((c.id_cpu for c in novo.cpus), default=-1) + 1
        while len(novo.cpus) < quantidade_cpus:
            novo.cpus.append(Cpu(proximo_id))
            proximo_id += 1
        ids = {c.id_cpu for c in novo.cpus}
        for tarefa in novo.tarefas:
            if novo.quantum != anterior.quantum:
                tarefa.tempo_exec_quantum = 0
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO and tarefa.id_cpu_atual not in ids:
                tarefa.estado_tarefa = EstadoTarefa.PRONTA
                tarefa.id_cpu_atual = None
                tarefa.tempo_exec_quantum = 0
        self.historico[self.instante_atual] = novo
        del self.historico[self.instante_atual + 1:]
        return True

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
            # Abandona a ocorrência e sua fila, sem fabricar conclusões.
            nova.tempo_exec_instancia = 0
            nova.perdeu_prazo = False
            nova.ocorrencias_pendentes.clear()
        if nova.prazo != anterior.prazo:
            for ocorrencia in nova.ocorrencias_pendentes:
                ocorrencia.prazo_absoluto = ocorrencia.ativacao + nova.prazo
                ocorrencia.perdeu_prazo = False
        if any(nova.ingresso > o.ativacao for o in nova.ocorrencias_pendentes):
            raise ValueError("ingresso não pode ser posterior à ativação de uma ocorrência pendente.")
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
        """Um tick: copiar → ativar → escalonar/despachar → executar → verificar."""
        estado = copy.deepcopy(estado_ant)
        estado.eventos = []
        self._ativar_tarefas(estado)
        self._despachar(estado)
        self._executar_tarefas(estado)
        self._verificar_prazos(estado)
        estado.tick += 1
        return estado

    def _iniciar_ocorrencia(self, tarefa, ocorrencia):
        # O prazo conta da ativação original, mesmo após esperar na fila.
        tarefa.estado_tarefa = EstadoTarefa.PRONTA
        tarefa.tempo_exec_instancia = 0
        tarefa.tempo_exec_quantum = 0
        tarefa.prazo_absoluto = ocorrencia.prazo_absoluto
        tarefa.perdeu_prazo = ocorrencia.perdeu_prazo
        tarefa.id_cpu_atual = None

    def _ativar_tarefas(self, estado):
        t = estado.tick
        for tarefa in estado.tarefas:
            if t == tarefa.ingresso:
                estado.eventos.append(dict(tipo='chegada', tick=t, id_tarefa=tarefa.id))
            if tarefa.estado_tarefa == EstadoTarefa.FINALIZADA:
                continue
            if t < tarefa.ingresso or (t - tarefa.ingresso) % tarefa.periodo != 0:
                continue

            ativa = tarefa.estado_tarefa != EstadoTarefa.AGUARDANDO
            # A parada em dez execuções também limita o trabalho já admitido.
            total = tarefa.instancias_concluidas + len(tarefa.ocorrencias_pendentes) + int(ativa)
            if total >= 10:
                continue
            ocorrencia = Ocorrencia(t, t + tarefa.prazo)
            estado.eventos.append(dict(tipo='ativacao', tick=t, id_tarefa=tarefa.id))
            if not ativa:
                self._iniciar_ocorrencia(tarefa, ocorrencia)
            elif tarefa.prazo_absoluto - tarefa.prazo != t:
                # Uma ativação manual no próprio instante já representa esta ocorrência.
                tarefa.ocorrencias_pendentes.append(ocorrencia)

    def _despachar(self, estado):
        candidatas = [t for t in estado.tarefas
                      if t.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO)]
        sorteios = []
        # Consultar a política antes de apagar quem estava executando (desempate).
        ordenadas = escalonar(candidatas, estado.algoritmo, sorteios)
        ids = [t.id for t in ordenadas[:len(estado.cpus)]]
        for indice, ordem in enumerate(sorteios):
            estado.eventos.insert(indice, dict(
                tipo='sorteio', tick=estado.tick, ordem=ordem,
                selecionadas=[id_ for id_ in ordem if id_ in ids]))
        for tarefa in estado.tarefas:
            tarefa.id_cpu_atual = None
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO:
                tarefa.estado_tarefa = EstadoTarefa.PRONTA
        for indice, cpu in enumerate(estado.cpus):
            cpu.id_tarefa_alocada = None
            if indice < len(ordenadas):
                tarefa = ordenadas[indice]
                cpu.id_tarefa_alocada = tarefa.id
                tarefa.id_cpu_atual = cpu.id_cpu
                tarefa.estado_tarefa = EstadoTarefa.EXECUTANDO

    def _executar_tarefas(self, estado):
        t = estado.tick
        for cpu in estado.cpus:
            if cpu.id_tarefa_alocada is None:
                cpu.tempo_desligada += 1
                estado.eventos.append(dict(tipo='cpu_desligada', tick=t, id_cpu=cpu.id_cpu))
        for tarefa in estado.tarefas:
            if tarefa.estado_tarefa != EstadoTarefa.EXECUTANDO:
                tarefa.tempo_exec_quantum = 0
                continue
            tarefa.tempo_exec_instancia += 1
            if estado.quantum > 0:
                tarefa.tempo_exec_quantum += 1
            estado.eventos.append(dict(tipo='execucao', tick=t,
                                      id_tarefa=tarefa.id, id_cpu=tarefa.id_cpu_atual))
            if tarefa.tempo_exec_instancia >= tarefa.duracao:
                tarefa.instancias_concluidas += 1
                tarefa.tempo_exec_quantum = 0
                estado.eventos.append(dict(tipo='conclusao', tick=t + 1,
                    id_tarefa=tarefa.id, instancia=tarefa.instancias_concluidas))
                for cpu in estado.cpus:
                    if cpu.id_tarefa_alocada == tarefa.id:
                        cpu.id_tarefa_alocada = None
                tarefa.id_cpu_atual = None
                if tarefa.instancias_concluidas == 10:
                    tarefa.estado_tarefa = EstadoTarefa.FINALIZADA
                elif tarefa.ocorrencias_pendentes:
                    self._iniciar_ocorrencia(tarefa, tarefa.ocorrencias_pendentes.pop(0))
                else:
                    tarefa.estado_tarefa = EstadoTarefa.AGUARDANDO
            elif estado.quantum > 0 and tarefa.tempo_exec_quantum >= estado.quantum:
                estado.eventos.append(dict(tipo='fim_quantum', tick=t + 1,
                    id_tarefa=tarefa.id, id_cpu=tarefa.id_cpu_atual))
                # Reavaliar no próximo tick; expirar a fatia não exige rodízio.
                tarefa.tempo_exec_quantum = 0

    def _verificar_prazos(self, estado):
        # Conclusões já foram processadas: terminar exatamente no prazo é válido.
        for tarefa in estado.tarefas:
            if tarefa.estado_tarefa in (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO, EstadoTarefa.SUSPENSA):
                if estado.tick + 1 >= tarefa.prazo_absoluto and not tarefa.perdeu_prazo:
                    tarefa.perdeu_prazo = True
                    estado.eventos.append(dict(tipo='perda_prazo', tick=estado.tick + 1,
                                              id_tarefa=tarefa.id))
            # A espera pela ocorrência anterior também consome o prazo.
            for ocorrencia in tarefa.ocorrencias_pendentes:
                if estado.tick + 1 >= ocorrencia.prazo_absoluto and not ocorrencia.perdeu_prazo:
                    ocorrencia.perdeu_prazo = True
                    estado.eventos.append(dict(tipo='perda_prazo', tick=estado.tick + 1,
                        id_tarefa=tarefa.id, ativacao=ocorrencia.ativacao))
