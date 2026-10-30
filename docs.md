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
| `gui.py` | Janela PySide6/QtWidgets, tabela, edição, controles e Gantt a partir dos snapshots. |
| `test_*.py` | Verificar os comportamentos implementados. |

A primeira interface e o Gantt estão implementados com **PySide6/QtWidgets** em `gui.py`. Não usam QML nem biblioteca adicional de gráficos. `exporter.py` continua planejado; a exportação e o empacotamento não foram implementados. `requirements.txt` registra a versão de PySide6 exercitada no ambiente de desenvolvimento.

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
- O Gantt usa `QGraphicsScene`/`QGraphicsView`, com rolagem e zoom, IDs numéricos decrescentes, CPU nos blocos, suspensão preta hachurada, trilhas de CPU desligada, legenda e marcadores com timestamps/tooltips. Mostra somente o prefixo do histórico até o instante selecionado; retroceder não exibe o futuro salvo.
- Execução completa usa `QTimer` e lotes pequenos de chamadas a `avancar()` para devolver controle à janela. Os lotes não limitam a duração total da simulação. Os controles de alteração ficam desabilitados durante a execução e o Gantt é redesenhado ao final; fechar a janela interrompe o timer. A UI mantém as mesmas condições de parada e bloqueio da execução completa do motor.
- Exportar o gráfico completo a partir dos dados/desenho, não capturar somente a parte visível da janela.
- A biblioteca aceita é PySide6. O formato e a implementação da exportação integral ainda precisam ser definidos; a menção anterior a Tkinter no README foi substituída.
- A entrega deve executar sem exigir que o destinatário instale Python ou bibliotecas. O empacotamento ainda precisa ser implementado e testado fora do ambiente de desenvolvimento.

## 10. Verificação e próximos passos

Executar a suíte local com:

```bash
python -B -m unittest discover -q
```

Para exercitar também os testes da interface, usar o Python do ambiente com PySide6 (`.venv-windows/Scripts/python.exe` no Windows). Em interpretadores sem PySide6, os testes gráficos são ignorados e os testes do motor continuam disponíveis. Comandos de instalação e execução estão no README; `exemplos/configuracao.txt` permite testar o fluxo com duas CPUs e três tarefas.

Próximo foco: avaliar a primeira interface com casos de uso e implementar a exportação integral e a distribuição. Manter sobreposição de ocorrências e valores padrão como questões abertas. Não adicionar recursos opcionais antes de concluir esse fluxo.
