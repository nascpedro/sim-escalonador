
# Simulador de Sistema Operacional Multitarefa de Tempo Compartilhado

> **Branch experimental `codex/customtkinter-drawsvg`:** a nova interface está em
> `gui_ctk.py` e o desenho compartilhado Canvas/SVG em `gantt_svg.py`.
> Execução e limites do experimento: [EXPERIMENTO_CTK.md](EXPERIMENTO_CTK.md).
> A versão Qt continua disponível em `gui.py`; os comandos abaixo descrevem essa versão.

Simulador de escalonamento preemptivo multiprocessador com foco em sistemas de tempo real periódicos (Rate Monotonic e Earliest Deadline First), com suporte a múltiplos núcleos e controle de avançar e retroceder a simulação (time-travel debugging).

Comece por este README para executar e apresentar o **Projeto A**. [docs.md](docs.md) registra as decisões; [PENDENCIAS.md](PENDENCIAS.md) acompanha os requisitos ainda abertos. [REVISAO_INTERFACE.md](REVISAO_INTERFACE.md) e [EMPACOTAMENTO.md](EMPACOTAMENTO.md) guardam o histórico técnico dessas frentes; não são pré-requisitos para entender o fluxo principal.

## Roteiro curto para apresentar o Projeto A

O programa lê tarefas periódicas de um arquivo, decide quem recebe CPU a cada tick e guarda uma cópia do estado para permitir avançar, retroceder e editar. RM prioriza o menor período; EDF prioriza o prazo absoluto mais próximo. Após dez ocorrências concluídas por tarefa, a execução completa termina.

Leia o código nesta ordem:

1. `models.py`: quais dados uma tarefa, uma CPU e um estado guardam.
2. `scheduler.py`: como ordenar as candidatas e desempatar.
3. `engine.py`: `avancar()` calcula ou recupera um estado; `_executar_um_tick()` chama as etapas de ativação, despacho, execução e verificação de prazos. A fila de ocorrências fica no TCB. `retroceder()` move o índice do histórico.
4. `parser.py`: `carregar_configuracao()` lê as linhas, `_ler_cabecalho()` interpreta o sistema e `_ler_tarefa()` interpreta cada tarefa. O carregador verifica duplicidades e avisa sobre aperiódicas ignoradas.
5. `gui.py`: `_conectar_sinais()` liga os botões às operações; `atualizar()` mostra o snapshot selecionado.
6. `gantt.py` e `exporter.py`: os eventos viram intervalos; Matplotlib desenha e salva SVG.

**Ferramentas utilizadas:** PySide6 fornece a janela e os controles; o formulário visual está em `ui/janela_principal.ui`, editável no Qt Designer. Matplotlib fornece gráfico, barra de navegação e exportação SVG. O parser usa a biblioteca padrão do Python. A lógica específica do simulador está no motor e no escalonador.

Para a demonstração, abra `exemplos/configuracao.txt`, avance alguns ticks, retroceda, selecione e edite uma tarefa, avance para recalcular, execute até o fim e exporte o SVG. Sem edições, o exemplo termina no tick 185. Uma edição aceita descarta os estados futuros, preservando os anteriores. O zoom altera somente a visualização.

Para explicar RM e EDF, compare `exemplos/rm-perda-prazo.txt` e `exemplos/edf-prazos.txt`: são os dados da figura 2.6 do capítulo, com IDs 1 e 2 para A e B. Até o tick 60, RM perde o prazo da tarefa 2 no tick 50; EDF não perde prazos. `exemplos/sobreposicao.txt` mostra uma tarefa de duração 5 e período 3: as ocorrências esperam em fila, e a tarefa conclui dez vezes no tick 50 usando somente uma das duas CPUs.

**Limites a declarar:** sugestões completas de valores padrão e inclusão/remoção de tarefas durante a execução ainda estão pendentes; a distribuição Windows precisa de homologação em máquina limpa. O SVG final é gerado automaticamente ao lado da configuração, com sufixo numérico para preservar arquivos existentes. Falhas de escrita permitem exportar novamente para outro destino.

Na simplificação para a apresentação foram retirados o modo apresentação e o acompanhamento automático do tick. Permanecem zoom, barra temporal, rolagem vertical e exportação integral. A retirada desses opcionais não resolve as pendências acima.

---

## Executar a interface (Windows)

Na raiz do projeto, prepare um ambiente de desenvolvimento com Python 3.11 e `uv`:

```powershell
uv venv --python 3.11 .venv-windows
uv pip install --python .venv-windows/Scripts/python.exe -r requirements.txt
.\.venv-windows\Scripts\python.exe gui.py
```

O ambiente `.venv-windows` fica separado de uma eventual `.venv` criada em outro sistema. Para abrir o exemplo diretamente:

```powershell
.\.venv-windows\Scripts\python.exe gui.py exemplos/configuracao.txt
```

O exemplo inclui duas CPUs, três tarefas e quantum 3. A janela permite carregar outro arquivo, navegar pelo histórico, executar até o fim, editar uma tarefa pela API do motor e exportar SVG. Ao concluir, gera também o SVG final ao lado da configuração, sem sobrescrever arquivos existentes. O Gantt é Matplotlib integrado ao PySide6 por `FigureCanvasQTAgg`, com a barra de navegação da biblioteca. Não há desenho manual paralelo em Graphics View.

Os testes ficam em `test/`. Execute a partir da raiz, incluindo a interface em modo offscreen:

```powershell
.\.venv-windows\Scripts\python.exe -B -m unittest discover -v
```

Esses comandos são para **desenvolvimento**. A distribuição Windows é gerada por `powershell -ExecutionPolicy Bypass -File scripts/empacotar.ps1`. Extraia o ZIP inteiro de `dist/SimuladorSO-windows-x64.zip` e abra `SimuladorSO.exe`. A validação local e a limitação de não haver teste em máquina limpa estão em [EMPACOTAMENTO.md](EMPACOTAMENTO.md).

Para preparar a máquina de build, instale `requirements-build.txt` no mesmo ambiente Python 3.11. O script não instala nada; gera a pasta, verifica a exportação empacotada e só então atualiza o ZIP. Os arquivos de `build/` e `dist/` ficam fora do Git.

## Exportar o Gantt em SVG

A exportação não depende da aparência da janela nem de PySide6: usa a mesma função Matplotlib que desenha os snapshots e eventos na tela. Instale as dependências de `requirements.txt` também para usar a CLI.

```powershell
.\.venv-windows\Scripts\python.exe exporter.py exemplos/configuracao.txt gantt.svg
```

Esse comando carrega a configuração, executa a simulação completa e grava toda a linha do tempo no SVG. Abra `gantt.svg` em um navegador ou editor vetorial e use seu zoom para inspecionar os detalhes. O gráfico inclui todo o intervalo temporal; isso não garante legibilidade de todos os detalhes na escala reduzida.

A API `exportar_svg(simulacao, caminho)` não executa ticks nem altera a simulação. Exporta até o instante selecionado; após retroceder, não inclui o futuro salvo. O exemplo completo termina no tick 185. Erros de entrada/escrita são informados no terminal. O diretório de destino deve existir.

O SVG inclui identificação de CPU, ociosidade, suspensão hachurada, marcadores de eventos e legenda. O botão **Exportar SVG** salva todo o prefixo selecionado, mesmo que a tela esteja ampliada em um trecho. A barra do Matplotlib serve para navegar e ampliar; o botão próprio faz a exportação integral.

## Como explicar o Gantt

- `engine.py` decide quem executa; não foi alterado nesta migração.
- `gantt.py` transforma os registros em intervalos `(início, duração)` e usa `Axes.broken_barh`, marcadores e rótulos do Matplotlib.
- `gui.py` apresenta uma `Figure` dentro do Qt com `FigureCanvasQTAgg`.
- `exporter.py` chama o mesmo desenho e `Figure.savefig(..., format='svg')`. O Matplotlib gera o SVG; não há construção manual de XML.

A integração já está em `gui.py`: `QUiLoader` carrega o formulário, o canvas é inserido em `graficoContainer` e a mesma `Figure` é atualizada por `desenhar_gantt(simulacao, figura)` e `canvas.draw_idle()`. Não é necessário gerar `ui_janela_principal.py` para executar. Mantenha `ui/janela_principal.ui` junto do projeto.

**Navegação do gráfico — etapa 1 implementada:** use **+ Zoom** para aproximar e a barra horizontal abaixo do gráfico para percorrer o tempo sem avançar a simulação. **Ajustar tudo** mostra novamente todo o prefixo selecionado. O zoom é preservado ao avançar/retroceder, ajustando apenas o que ultrapassar o instante selecionado. Quando o gráfico for alto, use a rolagem vertical para acessar as demais trilhas e a legenda ao final. A legenda é única e os eventos fora do intervalo visível são recortados. A configuração global passa pela API do motor e seu algoritmo acompanha o histórico.

## 1. Como a Simulação Funciona: O Ciclo do Tick `[t, t+1)`

A simulação avança em ticks inteiros discretos ($t = 0, 1, 2, \dots$). Toda operação ocorre no intervalo $[t, t+1)$:

* **No instante $t$ (Decisão):**
  * Chegada de novas instâncias periódicas ($t \ge \text{ingresso}$ e no início do período).
  * Se a anterior estiver pendente, a nova ocorrência entra na fila FIFO da tarefa, preservando ativação e prazo.
  * Definição do prazo absoluto ($d = t + \text{prazo}$).
  * Ordenação da fila global de tarefas prontas pelo algoritmo escolhido (RM ou EDF).
  * Alocação das tarefas com maior prioridade nos processadores livres (nenhum núcleo fica ocioso se houver tarefa pronta). Núcleos sem tarefa são marcados como desligados.
* **Durante $[t, t+1)$ (Execução):**
  * Cada tarefa alocada executa 1 unidade de tempo.
  * CPUs sem tarefas acumulam 1 tick de ociosidade/desligamento.
* **No instante $t+1$ (Conclusão e Verificação):**
  * Tarefas que atingiram a duração encerram sua ocorrência e tornam pronta a próxima pendente, ou aguardam o próximo período. Terminam em definitivo após 10 conclusões.
  * Ocorrências atuais ou pendentes que atingiram o prazo limite sem terminar marcam perda de prazo (continuam executando até terminar a duração, sem serem abortadas).
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
├── gantt.py        # Desenho Matplotlib compartilhado pela tela e exportação
├── exporter.py     # Exportação SVG vetorial independente da janela + CLI
├── gui.py          # Interface PySide6/QtWidgets com Gantt e inspeção do estado
├── ui/             # Formulário Qt Designer carregado em tempo de execução
├── REVISAO_INTERFACE.md # Diagnóstico e critérios de aceite da revisão da GUI
├── requirements.txt # Dependência gráfica
├── exemplos/       # Configuração para experimentar a interface
└── test/           # Testes unittest do motor, parser e interface
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
