"""Motor da simulação: histórico, intervenções manuais e evolução por ticks.

O snapshot t antecede [t, t+1). Um tick copia o estado, ativa ocorrências,
despacha, executa uma unidade e verifica prazos. A ordem é parte do modelo:
concluir exatamente no prazo é válido. O motor não conhece a interface.
"""
import copy

from models import Cpu, EstadoSimulacao, EstadoTarefa, Ocorrencia, TCB, normalizar_id
import padroes
from scheduler import escalonar
from validacao import normalizar_cor, validar_algoritmo, validar_inteiro

ESTADOS_ATIVOS = (EstadoTarefa.PRONTA, EstadoTarefa.EXECUTANDO, EstadoTarefa.SUSPENSA)


class Simulacao:
    # Navegação e histórico

    def __init__(self, estado_inicial: EstadoSimulacao, algoritmo: str):
        estado_inicial.algoritmo = algoritmo.upper()
        # O histórico guarda cada estado da simulação
        self.historico = [estado_inicial]
        self.instante_atual = 0 # aponta para o instante de tempo atual da simulação

    @property
    def estado_atual(self):
        """Snapshot apontado pela navegação, que pode ter um futuro já calculado."""
        return self.historico[self.instante_atual]

    @property
    def algoritmo(self):
        return self.estado_atual.algoritmo or self.historico[0].algoritmo

    @property
    def concluida(self):
        return all(t.estado_tarefa == EstadoTarefa.FINALIZADA for t in self.estado_atual.tarefas)

    def avancar(self, passos: int = 1) -> None:
        for _ in range(passos):
            # Se o futuro já consta no histórico, basta avançar o instante
            if self.instante_atual < len(self.historico) - 1:
                self.instante_atual += 1
            else:
                # Calcula o próximo tick [t, t+1)
                novo_estado = self._executar_um_tick(self.estado_atual)
                self.historico.append(novo_estado)
                self.instante_atual += 1

    def retroceder(self, passos: int = 1) -> None:
        # Retrocede simulação com base no histórico
        self.instante_atual = max(0, self.instante_atual - passos)

    def executar_completa(self) -> EstadoSimulacao:
        """Avança até dez conclusões por tarefa, reutilizando o futuro quando existe."""
        while self.pode_continuar_execucao():
            self.avancar()
        return self.estado_atual

    def pode_continuar_execucao(self):
        """Retorna False no término; explica impedimentos sem avançar o relógio.

        Compartilhada pela CLI e pelos lotes da GUI. Avanço manual de um tick
        continua permitido mesmo com tarefa suspensa.
        """
        if self.concluida:
            return False
        if not self.estado_atual.cpus:
            raise RuntimeError('Execução completa interrompida: há tarefas pendentes, mas nenhuma CPU.')
        for tarefa in self.estado_atual.tarefas:
            if tarefa.estado_tarefa == EstadoTarefa.SUSPENSA:
                raise RuntimeError(
                    f'Execução completa interrompida: tarefa {tarefa.id} suspensa. '
                    'Altere seu estado manualmente antes de continuar.')
        return True

    def _substituir_estado_atual(self, estado):
        """Uma intervenção aceita preserva o passado e invalida somente o futuro."""
        self.historico[self.instante_atual] = estado
        del self.historico[self.instante_atual + 1:]

    # Intervenções manuais: validar antes de aplicar

    def configurar_sistema(self, algoritmo, quantum, quantidade_cpus):
        """Valida tudo antes de substituir o snapshot; retorna se houve mudança."""
        algoritmo = validar_algoritmo(algoritmo)
        validar_inteiro(quantum, 'quantum', 0)
        validar_inteiro(quantidade_cpus, 'quantidade de CPUs', 1)
        anterior = self.estado_atual
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
        self._substituir_estado_atual(novo)
        return True

    def sugerir_tarefa(self):
        estados = self.historico[:self.instante_atual + 1]
        ids = {t.id for s in estados for t in s.tarefas}
        ids.update(e['id_tarefa'] for s in estados for e in s.eventos if 'id_tarefa' in e)
        cores = {t.cor for s in estados for t in s.tarefas}
        cores.update(e['cor'] for s in estados for e in s.eventos if 'cor' in e)
        return padroes.sugerir_tarefa(ids, cores, estados[-1].tick)

    def adicionar_tarefa(self, id_tarefa, cor, ingresso, duracao, periodo, prazo):
        """Inclui uma tarefa futura ou com chegada agora; nunca fabrica passado."""
        id_tarefa = normalizar_id(id_tarefa)
        estados = self.historico[:self.instante_atual + 1]
        if any(t.id == id_tarefa for s in estados for t in s.tarefas) or any(
                e.get('id_tarefa') == id_tarefa for s in estados for e in s.eventos):
            raise ValueError('ID já utilizado neste histórico; escolha outro.')
        for nome, valor, minimo in (('ingresso', ingresso, estados[-1].tick),
                ('duracao', duracao, 1), ('periodo', periodo, 1), ('prazo', prazo, 1)):
            validar_inteiro(valor, nome, minimo)
        cor = normalizar_cor(cor)
        if any(t.cor.lstrip('#').upper() == cor[1:] for t in estados[-1].tarefas):
            raise ValueError('cor já utilizada por outra tarefa.')
        novo = copy.deepcopy(estados[-1])
        novo.tarefas.append(TCB(id_tarefa, cor, ingresso, duracao, periodo, prazo))
        novo.eventos.append(dict(tipo='inclusao', tick=novo.tick, id_tarefa=id_tarefa, cor=cor))
        self._substituir_estado_atual(novo)

    def remover_tarefa(self, id_tarefa):
        """Remove também ocorrências pendentes e libera a CPU, preservando o passado."""
        anterior = self.estado_atual
        tarefa = anterior.tarefas[self._indice_tarefa(id_tarefa)]
        novo = copy.deepcopy(anterior)
        novo.tarefas = [t for t in novo.tarefas if t.id != id_tarefa]
        self._liberar_cpu(novo, id_tarefa)
        novo.eventos.append(dict(tipo='remocao', tick=novo.tick, id_tarefa=id_tarefa, cor=tarefa.cor))
        self._substituir_estado_atual(novo)

    def modificar_tarefa_em_execucao(self, id_tarefa: int | str, **alteracoes) -> None:
        """Prepara e valida numa cópia; só então aplica e descarta o futuro.

        CPU, progresso e contadores pertencem ao motor. PRONTA e SUSPENSA
        preservam a ocorrência; AGUARDANDO abandona a ocorrência e sua fila.
        """
        indice = self._indice_tarefa(id_tarefa)
        if not alteracoes:
            return
        self._validar_campos_tarefa(id_tarefa, alteracoes)
        anterior = self.estado_atual.tarefas[indice]
        nova = copy.deepcopy(anterior)
        for campo, valor in alteracoes.items():
            setattr(nova, campo, valor)
        self._ajustar_ocorrencia_editada(anterior, nova)
        cpu = self._selecionar_cpu_manual(nova)
        nova.id_cpu_atual = cpu.id_cpu if cpu is not None else None
        if anterior.estado_tarefa != EstadoTarefa.EXECUTANDO or nova.estado_tarefa != EstadoTarefa.EXECUTANDO:
            nova.tempo_exec_quantum = 0
        self._aplicar_edicao_tarefa(indice, nova, cpu)

    def _indice_tarefa(self, id_tarefa):
        for indice, tarefa in enumerate(self.estado_atual.tarefas):
            if tarefa.id == id_tarefa:
                return indice
        raise ValueError(f'Tarefa {id_tarefa!r} não encontrada.')

    def _validar_campos_tarefa(self, id_tarefa, alteracoes):
        estado = self.estado_atual
        # Valida apenas a entrada da edição.
        limites = {'ingresso': 0, 'duracao': 1, 'periodo': 1, 'prazo': 1}
        for campo, valor in alteracoes.items():
            if campo in limites:
                validar_inteiro(valor, campo, limites[campo])
            elif campo == 'cor':
                normalizar_cor(valor)
                for outra in estado.tarefas:
                    if outra.id != id_tarefa and outra.cor.lstrip('#').upper() == valor.lstrip('#').upper():
                        raise ValueError("cor já utilizada por outra tarefa.")
            elif campo == 'estado_tarefa':
                if not isinstance(valor, EstadoTarefa):
                    raise ValueError("estado_tarefa deve ser um valor de EstadoTarefa.")
            else:
                raise ValueError(f"{campo} não é um campo editável.")

    def _ajustar_ocorrencia_editada(self, anterior, nova):
        """Recalcula a ocorrência e sua fila numa cópia, antes de aceitar a edição."""
        estado = self.estado_atual
        if nova.estado_tarefa == EstadoTarefa.FINALIZADA and nova.instancias_concluidas < 10:
            raise ValueError("FINALIZADA exige dez ocorrências concluídas.")
        if nova.instancias_concluidas == 10 and nova.estado_tarefa != EstadoTarefa.FINALIZADA:
            raise ValueError("Após dez ocorrências, a tarefa não pode ser reativada.")
        if nova.estado_tarefa in ESTADOS_ATIVOS:
            ativacao = anterior.prazo_absoluto - anterior.prazo
            if anterior.estado_tarefa not in ESTADOS_ATIVOS:
                # Entrar manualmente em PRONTA/EXECUTANDO/SUSPENSA inicia uma ocorrência.
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
        if nova.estado_tarefa == EstadoTarefa.AGUARDANDO and anterior.estado_tarefa in ESTADOS_ATIVOS:
            # Abandona a ocorrência e sua fila.
            nova.tempo_exec_instancia = 0
            nova.perdeu_prazo = False
            nova.ocorrencias_pendentes.clear()
        self._recalcular_prazos_pendentes(anterior, nova)

    def _recalcular_prazos_pendentes(self, anterior, nova):
        """Atualiza os prazos da fila FIFO de sobreposição quando o prazo ou ingresso mudam."""
        if nova.prazo != anterior.prazo:
            for ocorrencia in nova.ocorrencias_pendentes:
                ocorrencia.prazo_absoluto = ocorrencia.ativacao + nova.prazo
                ocorrencia.perdeu_prazo = False
        if any(nova.ingresso > o.ativacao for o in nova.ocorrencias_pendentes):
            raise ValueError("ingresso não pode ser posterior à ativação de uma ocorrência pendente.")
        if nova.prazo_absoluto != anterior.prazo_absoluto:
            # Se o novo prazo já venceu, o próximo tick registra a perda no histórico.
            nova.perdeu_prazo = False

    def _selecionar_cpu_manual(self, nova):
        estado = self.estado_atual
        # EXECUTANDO mantém a CPU atual ou usa uma livre, sem migração manual.
        escolhida = None
        if nova.estado_tarefa == EstadoTarefa.EXECUTANDO:
            for cpu in estado.cpus:
                if cpu.id_tarefa_alocada == nova.id:
                    escolhida = cpu
                    break
                if cpu.id_tarefa_alocada is None and escolhida is None:
                    escolhida = cpu
            if escolhida is None:
                raise ValueError("Não há CPU livre para colocar a tarefa em EXECUTANDO.")
        return escolhida

    def _aplicar_edicao_tarefa(self, indice, nova, cpu):
        """Todas as verificações terminaram; agora pode alterar o snapshot selecionado."""
        estado = self.estado_atual
        self._liberar_cpu(estado, nova.id)
        if cpu is not None:
            cpu.id_tarefa_alocada = nova.id
        estado.tarefas[indice] = nova
        self._substituir_estado_atual(estado)

    # Ciclo automático do tick

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

    def _deve_ativar_no_tick(self, tarefa, t):
        """Verdadeiro no instante de ingresso e nos múltiplos exatos do período."""
        return t >= tarefa.ingresso and (t - tarefa.ingresso) % tarefa.periodo == 0

    def _total_ocorrencias_admitidas(self, tarefa):
        """Soma concluídas, enfileiradas e a ocorrência atualmente ativa."""
        ativa = tarefa.estado_tarefa != EstadoTarefa.AGUARDANDO
        return tarefa.instancias_concluidas + len(tarefa.ocorrencias_pendentes) + int(ativa)

    def _ativar_tarefas(self, estado):
        t = estado.tick
        for tarefa in estado.tarefas:
            if t == tarefa.ingresso:
                estado.eventos.append(dict(tipo='chegada', tick=t, id_tarefa=tarefa.id))
            if tarefa.estado_tarefa == EstadoTarefa.FINALIZADA:
                continue
            if not self._deve_ativar_no_tick(tarefa, t):
                continue
            # A parada em dez execuções também limita o trabalho já admitido.
            if self._total_ocorrencias_admitidas(tarefa) >= 10:
                continue
            ocorrencia = Ocorrencia(t, t + tarefa.prazo)
            estado.eventos.append(dict(tipo='ativacao', tick=t, id_tarefa=tarefa.id))
            if tarefa.estado_tarefa == EstadoTarefa.AGUARDANDO:
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
        ids_selecionadas = [t.id for t in ordenadas[:len(estado.cpus)]]
        self._registrar_preempcoes(estado, candidatas, ids_selecionadas)
        self._registrar_sorteios(estado, sorteios, ids_selecionadas)
        self._alocar_cpus(estado, ordenadas)

    def _registrar_preempcoes(self, estado, candidatas, ids_selecionadas):
        """Perder a CPU por decisão do escalonador é preempção. Migração e
        conclusão não entram aqui: o evento descreve a interrupção da tarefa.
        """
        for tarefa in candidatas:
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO and tarefa.id not in ids_selecionadas:
                estado.eventos.append(dict(tipo='preempcao', tick=estado.tick,
                    id_tarefa=tarefa.id, id_cpu=tarefa.id_cpu_atual))

    def _registrar_sorteios(self, estado, sorteios, ids_selecionadas):
        for indice, ordem in enumerate(sorteios):
            estado.eventos.insert(indice, dict(
                tipo='sorteio', tick=estado.tick, ordem=ordem,
                selecionadas=[id_ for id_ in ordem if id_ in ids_selecionadas]))

    def _alocar_cpus(self, estado, tarefas_ordenadas):
        """Limpa a alocação anterior e vincula cada CPU livre à próxima candidata eleita."""
        for tarefa in estado.tarefas:
            tarefa.id_cpu_atual = None
            if tarefa.estado_tarefa == EstadoTarefa.EXECUTANDO:
                tarefa.estado_tarefa = EstadoTarefa.PRONTA
        for indice, cpu in enumerate(estado.cpus):
            cpu.id_tarefa_alocada = None
            if indice < len(tarefas_ordenadas):
                tarefa = tarefas_ordenadas[indice]
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
            self._executar_uma_unidade(estado, tarefa)
            if tarefa.tempo_exec_instancia >= tarefa.duracao:
                self._concluir_ocorrencia(estado, tarefa)
            elif estado.quantum > 0 and tarefa.tempo_exec_quantum >= estado.quantum:
                self._registrar_fim_quantum(estado, tarefa)

    def _verificar_prazos(self, estado):
        # Conclusões já foram processadas: terminar exatamente no prazo é válido.
        for tarefa in estado.tarefas:
            if tarefa.estado_tarefa in ESTADOS_ATIVOS:
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

    # Operações das ocorrências e das CPUs

    def _iniciar_ocorrencia(self, tarefa, ocorrencia):
        # O prazo conta da ativação original, mesmo após esperar na fila.
        tarefa.estado_tarefa = EstadoTarefa.PRONTA
        tarefa.tempo_exec_instancia = 0
        tarefa.tempo_exec_quantum = 0
        tarefa.prazo_absoluto = ocorrencia.prazo_absoluto
        tarefa.perdeu_prazo = ocorrencia.perdeu_prazo
        tarefa.id_cpu_atual = None

    def _executar_uma_unidade(self, estado, tarefa):
        """Consome um tick e registra a CPU que executou, antes de liberá-la."""
        tarefa.tempo_exec_instancia += 1
        if estado.quantum > 0:
            tarefa.tempo_exec_quantum += 1
        estado.eventos.append(dict(tipo='execucao', tick=estado.tick,
                                  id_tarefa=tarefa.id, id_cpu=tarefa.id_cpu_atual))

    def _concluir_ocorrencia(self, estado, tarefa):
        """Conta a conclusão, libera CPU e promove a próxima ocorrência em FIFO."""
        tarefa.instancias_concluidas += 1
        tarefa.tempo_exec_quantum = 0
        estado.eventos.append(dict(tipo='conclusao', tick=estado.tick + 1,
            id_tarefa=tarefa.id, instancia=tarefa.instancias_concluidas))
        self._liberar_cpu(estado, tarefa.id)
        tarefa.id_cpu_atual = None
        if tarefa.instancias_concluidas == 10:
            tarefa.estado_tarefa = EstadoTarefa.FINALIZADA
        elif tarefa.ocorrencias_pendentes:
            self._iniciar_ocorrencia(tarefa, tarefa.ocorrencias_pendentes.pop(0))
        else:
            tarefa.estado_tarefa = EstadoTarefa.AGUARDANDO

    def _registrar_fim_quantum(self, estado, tarefa):
        estado.eventos.append(dict(tipo='fim_quantum', tick=estado.tick + 1,
            id_tarefa=tarefa.id, id_cpu=tarefa.id_cpu_atual))
        # Reavaliar no próximo tick; expirar a fatia não exige rodízio.
        tarefa.tempo_exec_quantum = 0

    def _liberar_cpu(self, estado, id_tarefa):
        for cpu in estado.cpus:
            if cpu.id_tarefa_alocada == id_tarefa:
                cpu.id_tarefa_alocada = None
