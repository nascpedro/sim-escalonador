
# Simulador de Sistema Operacional Multitarefa de Tempo Compartilhado

Simulador de escalonamento preemptivo multiprocessador com foco em sistemas de tempo real periódicos (Rate Monotonic e Earliest Deadline First), com suporte a múltiplos núcleos e controle de avançar e retroceder a simulação (time-travel debugging).

---

## 1. Como a Simulação Funciona: O Ciclo do Tick `[t, t+1)`

A simulação avança em ticks inteiros discretos ($t = 0, 1, 2, \dots$). Toda operação ocorre no intervalo $[t, t+1)$:

* **No instante $t$ (Decisão):**
  * Chegada de novas instâncias periódicas ($t \ge \text{ingresso}$ e no início do período).
  * Definição do prazo absoluto ($d = t + \text{prazo}$).
  * Ordenação da fila global de tarefas prontas pelo algoritmo escolhido (RM ou EDF).
  * Alocação das tarefas com maior prioridade nos processadores livres (nenhum núcleo fica ocioso se houver tarefa pronta). Núcleos sem tarefa são marcados como desligados.
* **Durante $[t, t+1)$ (Execução):**
  * Cada tarefa alocada executa 1 unidade de tempo.
  * CPUs sem tarefas acumulam 1 tick de ociosidade/desligamento.
* **No instante $t+1$ (Conclusão e Verificação):**
  * Tarefas que atingiram a duração encerram sua instância e aguardam o próximo período (terminam em definitivo após 10 execuções).
  * Tarefas ativas que atingiram o prazo limite sem terminar marcam perda de prazo (continuam executando até terminar a duração, sem serem abortadas).
  * O relógio avança para $t+1$ e o estado é salvo no histórico.

---

## 2. Avançar e Retroceder (Histórico de Estados)

Para permitir inspecionar o sistema passo a passo:

* O simulador salva uma lista com o **estado instantâneo** de cada tick na memória.
* **Avançar (+1 tick):** Se já estiver no histórico, apenas anda para a frente; se estiver no fim, calcula o próximo tick e salva na lista.
* **Retroceder (-1 tick):** Apenas volta o ponteiro para o estado gravado anteriormente, sem necessidade de calcular lógica reversa.
* **Modificação no Passado:** Se o usuário alterar uma tarefa em um tick anterior, os estados futuros gravados são descartados para recalcular a nova linha temporal a partir daquele ponto.

---

## 3. Algoritmos de Escalonamento e Desempate

### 3.1 Políticas Suportadas
* **Rate Monotonic (RM) Preemptivo:** Prioridade fixa baseada no período. Quanto menor o período da tarefa, maior a sua prioridade.
* **Earliest Deadline First (EDF) Preemptivo:** Prioridade dinâmica baseada no prazo absoluto ($d$). Quanto mais próximo o deadline absoluto da instância, maior a prioridade.

### 3.2 Regras de Desempate (Ordem Obrigatória)
1. **Tarefa que já estava executando:** Evita troca de contexto desnecessária.
2. **Menor prazo relativo:** Prioridade para a de menor deadline.
3. **Menor ingresso:** Prioridade para a que entrou mais cedo no sistema.
4. **Menor duração:** Prioridade para a de menor tempo de computação.
5. **Sorteio:** Caso haja empate em todos os critérios anteriores (com marcação visual no log/Gantt).

---

## 4. Estruturas de Dados Principais

* **TCB (Task Control Block):**
  * *Estáticos:* `id`, `cor`, `ingresso`, `duracao`, `periodo`, `prazo`.
  * *Dinâmicos:* `estado` (Aguardando, Pronta, Executando, Suspensa, Finalizada), `instancias_concluidas`, `tempo_exec_instancia`, `prazo_absoluto`, `id_cpu_atual`, `perdeu_prazo`.
* **CPU:**
  * `id_cpu`, `id_tarefa_alocada`, `tempo_desligada`.
* **EstadoSimulacao (Instantâneo):**
  * `tick`, lista de cópias dos `TCBs`, lista de cópias das `CPUs`, lista de eventos do tick.

---

## 5. Estrutura do Código

```text
simulador_so/
│
├── models.py       # Classes de dados: TCB, CPU, EstadoSimulacao e enums
├── scheduler.py    # Algoritmos RM e EDF + regras em cascata de desempate
├── engine.py       # Motor da simulação: avanço/retrocesso de ticks e despacho
├── parser.py       # Leitura e validação do arquivo de entrada (.txt)
├── gui.py          # Interface gráfica Tkinter com Gantt e painel de depuração
└── exporter.py     # Exportador do gráfico de Gantt completo para SVG
````

## 6. Formato do Arquivo de Configuração

O arquivo de entrada `.txt` segue o formato:

```
algoritmo_escalonamento; quantum; qtde cpus
id; cor; ingresso; duracao; periodo; prazo; lista_eventos
```

**Exemplo:**

```
RM; 0; 2
1; #FF5733; 0; 2; 10; 6;
2; #33FF57; 0; 2; 10; 8;
3; #3357FF; 0; 8; 20; 16;
```