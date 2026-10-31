# Decisões do Projeto A — Simulador de escalonamento

Este documento registra as decisões de implementação e as limitações aceitas durante o desenvolvimento. Não substitui o enunciado e não afirma que todos os requisitos já foram atendidos. `PENDENCIAS.md` acompanha o que ainda falta fazer.

## 1. Escopo e forma de desenvolvimento

- Implementar somente o **Projeto A**. A lista de eventos do Projeto B não é executada.
- Priorizar código que o autor consiga ler, explicar e modificar. Evitar abstrações, opções e validações defensivas que não atendam a uma necessidade concreta.
- Avançar em etapas pequenas, verificando o comportamento antes de prosseguir.
- Não adicionar limite arbitrário de passos: a execução completa termina quando todas as tarefas concluem suas dez ocorrências.
- Não implementar agora a opção de escalonamento sem preempção. O comportamento principal continua sendo RM/EDF preemptivo.

## 2. Responsabilidade de cada arquivo

| Arquivo | Responsabilidade atual |
| --- | --- |
| `models.py` | Dados de tarefa (`TCB`), CPU, estado da simulação e estados das tarefas. |
| `scheduler.py` | Ordenar candidatas por RM ou EDF e aplicar os desempates. Não executa ticks nem desenha a interface. |
| `engine.py` | Processar ticks, executar tarefas, administrar CPUs, registrar eventos, navegar pelo histórico e aplicar edições. |
| `parser.py` | Carregar o arquivo de configuração e devolver estado inicial, algoritmo e avisos. |
| `gantt.py` | Converter o histórico em intervalos e desenhar a Figure com Matplotlib, sem Qt e sem executar ticks. |
| `exporter.py` | Exportar o histórico selecionado em SVG vetorial; CLI para execução completa e exportação sem GUI. |
| `gui.py` | Janela PySide6/QtWidgets, tabela, edição, controles e Gantt a partir dos snapshots. |
| `test/test_*.py` | Verificar os comportamentos implementados. `test/__init__.py` permite descobrir a suíte a partir da raiz. |

A janela usa **PySide6/QtWidgets** e o Gantt usa **Matplotlib**. O redesenho do layout está separado desta migração e reservado ao trabalho em `ui/`. `gantt.py` contém o desenho compartilhado; `exporter.py` usa `Figure.savefig` para SVG sem capturar a janela nem construir XML manualmente. O empacotamento tem apenas um experimento anterior, não uma entrega final. `requirements.txt` registra as versões de PySide6 e Matplotlib exercitadas no ambiente de desenvolvimento.

## 3. Tarefas, CPUs e histórico

- Manter uma lista principal de tarefas, com o estado de cada uma no próprio TCB.
- Construir uma lista temporária de candidatas contendo as tarefas `PRONTA` e `EXECUTANDO`. Não manter duas filas permanentes que precisem ser sincronizadas.
- Usar `copy.deepcopy` ao calcular um novo snapshot: mudar o próximo tick não pode alterar os estados anteriores.
- Dentro do mesmo tick, a lista de candidatas referencia os TCBs do snapshot em construção; não são feitas cópias adicionais de cada candidata.
- Acessar o snapshot selecionado explicitamente por `self.historico[self.instante_atual]`, sem a propriedade auxiliar `estado_atual`.
- Avançar sobre um futuro já salvo reutiliza os snapshots e os sorteios registrados; não executa novamente o escalonador.
- Uma edição aceita modifica o snapshot selecionado e descarta apenas os snapshots posteriores. Os anteriores permanecem preservados.
- O despacho atual pode migrar tarefas entre CPUs; não há política de afinidade.

## 4. Fluxo do tick e decisão de escalonamento

O snapshot com relógio `t` representa o estado antes de executar o intervalo `[t, t+1)`.

1. Copiar o estado selecionado para construir o próximo snapshot.
2. Processar chegada inicial e ativações periódicas que o motor consegue efetivar.
3. Ordenar prontas e executando, preservando a informação de quem executava para o desempate.
4. Despachar as candidatas selecionadas para as CPUs.
5. Executar uma unidade de tempo por tarefa alocada e contabilizar CPUs desligadas.
6. Registrar conclusões, término de quantum e perdas de prazo; salvar o estado em `t+1`.

A seleção ocorre a cada tick, e **não somente ao terminar o quantum**. Dessa forma, chegadas e ativações podem provocar preempção antes do fim da fatia. Uma CPU liberada por conclusão ou suspensão fica disponível para a próxima seleção. As edições manuais são consideradas na próxima seleção calculada a partir do estado editado.

Acionar o escalonador não significa obrigatoriamente trocar de tarefa: a atual pode continuar sendo a melhor candidata.

### RM, EDF e desempates

- RM: menor período tem maior prioridade.
- EDF: menor prazo absoluto tem maior prioridade.
- Empates no critério principal seguem: quem executava, menor prazo relativo, menor ingresso, menor duração e, por último, sorteio.
- A ordenação usa uma tupla com esses critérios. O sorteio acontece somente entre candidatas com todas as chaves iguais, e é registrado nos eventos.
- Não transformar executando em pronta antes de consultar a política: isso apagaria a informação necessária ao primeiro desempate.

### Fundamentação e convenções

O material de apoio `2-Sistemas de Tempo Real - Capitulo 2-full.pdf` descreve preempção por tarefas mais prioritárias (página 6 do PDF, impressa 16), RM preemptivo (página 12, impressa 22) e EDF preemptivo com reordenação na chegada de tarefas (página 14, impressa 24).

Isso afasta a interpretação de que uma tarefa mais prioritária precisa sempre aguardar o quantum atual acabar. Já as regras de contador e reinício da fatia abaixo são convenções explícitas do simulador, não transcrições de uma regra detalhada do professor.

## 5. Quantum, progresso e prazos

- `tempo_exec_instancia`: total já executado na ocorrência atual.
- `tempo_exec_quantum`: execução na fatia atual, por tarefa, enquanto ela executa sem interrupção. Uma migração sem interrupção não reinicia a fatia.
- Ao esgotar o quantum, registrar `fim_quantum` em `t+1`, zerar o contador da fatia e permitir nova disputa no mesmo instante, ao calcular o próximo intervalo.
- Preservar quem executava para o desempate. A tarefa pode vencer novamente, sem uma troca de contexto para outra tarefa.
- Preempção, conclusão ou saída manual de `EXECUTANDO` reiniciam a fatia. Isso não apaga o progresso da ocorrência, salvo uma mudança explícita para `AGUARDANDO`, descrita adiante.
- Se a ocorrência concluir exatamente no fim da fatia, registrar a conclusão, sem uma expiração de quantum redundante.
- **Convenção:** `quantum=0` significa sem limite de fatia; não significa desativar a preempção.
- Concluir exatamente no prazo é válido. Uma ocorrência que perde o prazo continua executando; o evento de perda é registrado uma vez para aquela ocorrência, enquanto seu prazo não for editado.
- A tarefa é marcada `FINALIZADA` após dez ocorrências concluídas.
- A execução completa reutiliza `avancar()`. Havendo tarefas pendentes sem CPUs, ou uma tarefa suspensa sem desbloqueio automático, informa a impossibilidade de prosseguir em vez de executar indefinidamente.

## 6. Nova ativação com ocorrência anterior pendente

**Decisão provisória: manter a limitação atual e avançar para a interface.**

Se uma nova ativação periódica estiver prevista enquanto a ocorrência anterior ainda estiver pronta, executando ou suspensa, o motor não cria outra ocorrência. A anterior continua normalmente. Essa ativação ignorada não reinicia seu progresso, seu prazo ou seu quantum, e não gera um evento de ativação efetivada.

Isso é uma simplificação conhecida, **não uma garantia de conformidade integral com a expectativa do professor**. O material distingue as ativações como instâncias diferentes, mas o tratamento exigido para sua sobreposição ainda precisa ser confirmado.

- Não implementar agora filas de ocorrências nem execução simultânea de ocorrências da mesma tarefa.
- Não proibir duração ou prazo maior que período para esconder esse caso.
- Não marcar essa questão como definitivamente resolvida apenas por ela ter sido adiada.

## 7. Carregamento de configuração

API: `estado_inicial, algoritmo, avisos = carregar_configuracao(caminho)`.

- Ler um arquivo externo UTF-8, com ou sem BOM, a partir do caminho fornecido.
- Respeitar espaços, linhas em branco, equivalência de maiúsculas/minúsculas e terminador `;` opcional.
- Validar formato, conversões numéricas, algoritmo, quantidade de CPUs, identificadores e cores. Informar motivos de erro, com linha quando aplicável.
- Identificadores numéricos são inteiros; textuais são normalizados com `casefold`. Cores são normalizadas para `#RRGGBB`.
- Tarefas aperiódicas válidas, identificadas por período zero, são ignoradas com aviso no Projeto A. Período negativo é erro.
- A lista de eventos do Projeto B não é interpretada.
- Não inventar valores padrão silenciosos. A política de padrões exigida pelo requisito 3.2 continua pendente.

## 8. Edição simples por campos

A interface deve informar somente as alterações solicitadas, sem construir um TCB completo:

```python
sim.modificar_tarefa_em_execucao(1, duracao=4)
sim.modificar_tarefa_em_execucao(1, estado_tarefa=EstadoTarefa.SUSPENSA)
```

Campos disponíveis: `ingresso`, `duracao`, `periodo`, `prazo`, `cor` e `estado_tarefa`.

- O motor administra CPU, progresso, contadores, indicadores e prazo absoluto. Esses campos internos e o ID não são entradas editáveis dessa API.
- Validar as entradas fornecidas e sua compatibilidade com a ocorrência atual, não a integridade de todo objeto Python. Não inspecionar atributos removidos de um TCB externo, pois a API não recebe esse objeto.
- Rejeitar com motivo antes de modificar o estado ou descartar o futuro.
- Alternar entre pronta, executando e suspensa preserva a ocorrência atual. Suspender libera sua CPU; solicitar execução exige CPU disponível ou a própria CPU.
- Colocar uma ocorrência ativa em aguardando abandona seu progresso sem contabilizar uma conclusão e espera uma próxima ativação. Sair de aguardando para um estado ativo inicia uma ocorrência no tick atual, se a tarefa já ingressou.
- Alterar prazo recalcula o prazo absoluto a partir da ativação atual. Eventual perda pelo prazo editado será verificada no próximo tick.
- Alterar período orienta as próximas ativações, sem reiniciar a ocorrência atual. Alterar ingresso não pode colocá-lo depois da ativação de uma ocorrência ainda em curso.
- Finalizada corresponde às dez ocorrências efetivamente concluídas pelo motor; não é um atalho para fabricar conclusões.

## 9. Interface e visualização

- Cada snapshot guarda os eventos do intervalo que o produziu, não uma cópia cumulativa de todo o log.
- Os eventos têm timestamp próprio: execução/decisão em `t` e conclusão/fim de quantum em `t+1` podem estar no mesmo snapshot.
- O registro de execução preserva qual CPU executou a tarefa, mesmo quando a conclusão libera a CPU ao final do intervalo.
- A interface lê o motor e seu histórico, sem reimplementar RM/EDF ou alterar TCBs diretamente. Erros de carregamento preservam a simulação anterior e aparecem na janela.
- A janela permite abrir arquivo, consultar tabela e avisos, avançar/retroceder, editar a tarefa selecionada e executar até o fim. Edição usa somente os campos alterados pela API do motor e mantém erros no diálogo.
- O Gantt usa Matplotlib (`Axes.broken_barh`, marcadores, eixos e legenda) em uma `Figure` reutilizada. A janela integra `FigureCanvasQTAgg` e a barra de navegação da biblioteca, em vez de reconstruir um gráfico em `QGraphicsScene`. Mantém IDs numéricos decrescentes, CPU nos blocos, suspensão hachurada, trilhas de CPU desligada e eventos nos ticks reais. Retroceder mostra somente o prefixo selecionado, sem futuro salvo.
- Execução completa usa `QTimer` e lotes pequenos de chamadas a `avancar()` para devolver controle à janela. Os lotes não limitam a duração total da simulação. Os controles de alteração ficam desabilitados durante a execução e o Gantt é redesenhado ao final; fechar a janela interrompe o timer. A UI mantém as mesmas condições de parada e bloqueio da execução completa do motor.
- Exportação em `exporter.py`, sem PySide6, mas com Matplotlib: `exportar_svg(simulacao, caminho)` cria uma Figure, chama o mesmo `desenhar_gantt` e usa `Figure.savefig` para gerar SVG. Não há mais escrita manual de XML. A API não modifica a simulação nem inclui futuro salvo. A CLI carrega, executa completamente e exporta; o botão Exportar SVG usa a API sem cortar pelo zoom atual da janela.
- O gráfico usa cores históricas, CPU explícita, ociosidade, suspensão hachurada e marcadores de formatos distintos descritos na legenda. Agrupa apenas trechos contíguos da mesma tarefa/CPU/cor sem atravessar fronteiras de eventos. O Matplotlib cuida dos eixos, desenho e serialização vetorial; o projeto só faz a conversão dos registros do motor e define sua representação.
- A biblioteca aceita é PySide6. SVG foi escolhido para a exportação vetorial, independente da janela; a menção anterior a Tkinter no README foi substituída.
- **Revisão da interface:** a primeira janela é funcional, mas foi considerada confusa para a apresentação. Preservar o código atual como referência, sem rollback destrutivo. Não confundir testes aprovados com clareza de uso aprovada. Validar uma nova organização antes de reescrever a GUI.
- Proposta em `prototipos/interface.html`: Gantt como área principal, parâmetros em uma área de configuração, detalhes somente da tarefa selecionada e composição de apresentação com menos distrações. A maquete usa dados reais do exemplo no tick 12, mas seus controles de simulação são ilustrativos; não é a aplicação nem uma troca de PySide6 por HTML.
- Evitar tabela permanente de 13 colunas e log técnico competindo com o gráfico. Manter inspeção completa acessível em área secundária. Preservar os requisitos de estados, CPUs, eventos e legenda ao detalhar a proposta; a maquete não comprova que todos já foram acomodados.
- SVG e estudo de empacotamento seguem em paralelo, sem depender da aparência da GUI atual. Um executável experimental da interface atual não deve ser apresentado como a entrega final aprovada.
- A entrega deve executar sem exigir que o destinatário instale Python ou bibliotecas. Um bundle experimental Windows foi produzido com PyInstaller onedir; deve ser copiado como pasta inteira. Houve um encerramento anormal intermitente na revalidação local, e não foi testado em PC limpo. Não considerar o empacotamento finalizado; detalhes em `EMPACOTAMENTO.md`.

## 10. Verificação e próximos passos

Os testes estão no diretório `test/`. Executar a suíte local a partir da raiz com:

```bash
.venv-windows/Scripts/python.exe -B -m unittest discover -q
```

Usar o Python do ambiente com as dependências de `requirements.txt`: Matplotlib é necessário para os testes do Gantt/exportador e PySide6 para os testes da janela. Comandos de instalação e execução estão no README; `exemplos/configuracao.txt` permite testar o fluxo com duas CPUs e três tarefas.

Próximo foco: integrar o formulário do Qt Designer ao canvas Matplotlib e validar a organização com Pedro; depois refazer o empacotamento com as dependências atuais. A exportação integral já está implementada. Manter sobreposição de ocorrências e valores padrão como questões abertas.
