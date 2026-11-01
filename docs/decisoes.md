# Decisões do Projeto A

## Escopo e bibliotecas

Somente Projeto A: tarefas periódicas, RM/EDF preemptivos e dez ocorrências
concluídas por tarefa. Eventos de mutex/E/S, servidores, aperiódicas e esporádicas
do Projeto B não são implementados. Priorizar código que o autor consiga explicar;
evitar novas abstrações e opções sem uma necessidade concreta.

A interface usa CustomTkinter com Canvas público do Tkinter. O formulário é
montado diretamente em Python. O mesmo desenho de `gantt.py` atende a tela e a
exportação drawsvg por quatro operações: retângulo, linha, texto e polígono.
A aplicação não depende de Qt ou Matplotlib. A versão anterior está no Git.

Fontes das bibliotecas: [CustomTkinter](https://github.com/TomSchimansky/CustomTkinter),
[Tk Canvas](https://www.tcl-lang.org/man/tcl8.6/TkCmd/canvas.htm),
[drawsvg](https://github.com/cduck/drawsvg). As licenças das versões distribuídas
acompanham suas bibliotecas; a licença do código do projeto está em LICENSE.

## Ciclo de execução e histórico

O snapshot `t` é o estado antes de executar `[t, t+1)`. O motor copia o snapshot
com deepcopy e chama, em sequência, ativação, despacho, execução e verificação de
prazos. Eventos de chegada/decisão usam `t`; conclusão e fim de quantum usam `t+1`.
O registro de execução preserva a CPU que trabalhou mesmo se ela for liberada ao fim.

Avançar sobre um futuro existente reutiliza snapshots e sorteios. Retroceder move
o índice do histórico e restaura o relógio. Uma edição aceita descarta somente os
snapshots posteriores; rejeições e configuração global sem mudanças preservam tudo.
Algoritmo, quantum e CPUs pertencem ao snapshot. O desenho lê somente o prefixo
selecionado; zoom não avança ticks e exportação não altera a simulação.

## Organização para leitura e apresentação

O motor tem seções para navegação/histórico, intervenções manuais, ciclo do tick
e operações de ocorrências/CPUs. O ciclo continua com quatro etapas explícitas;
execução, conclusão e fim de quantum possuem operações com nomes do domínio.
Uma função genérica de troca de estado esconderia efeitos sobre CPU, progresso
e fila, por isso não foi introduzida.

A edição valida campos e prepara uma cópia da tarefa, ajusta ocorrência/fila,
verifica disponibilidade de CPU e só então aplica. `_substituir_estado_atual`
concentra a atualização do histórico. A consulta `estado_atual` evita repetir
índices na interface. `concluida` e `pode_continuar_execucao` concentram término
e impedimentos, mantendo o avanço manual de um tick independente dessa regra.

`validacao.py` compartilha regras de inteiro, RGB e algoritmo. Conversão de texto
e contexto dos erros pertencem ao parser/formulário. O parser expõe uma leitura
sequencial: registros → cabeçalho → tarefas → estado inicial. A reserva de valores
explícitos anteriores às sugestões continua necessária.

## Escalonamento e quantum

A fila de candidatas é global e temporária, com tarefas prontas ou executando.
RM usa período; EDF usa prazo absoluto. Desempates: quem executava, menor prazo
relativo, menor ingresso, menor duração e sorteio. O motor consulta a política
antes de apagar a informação de quem executava. Não há afinidade de CPU: uma
tarefa pode migrar entre ticks. CPUs sem candidata acumulam ociosidade.

Quantum zero remove o limite de fatia, mantendo preempção. Com quantum positivo,
o contador mede execução contínua da tarefa. Migração sem interrupção preserva a
fatia. Preempção, suspensão e conclusão reiniciam a fatia. Ao expirar, registra-se
fim_quantum e reinicia-se o contador; a tarefa pode vencer novamente. A seleção
ocorre a cada tick, inclusive antes de esgotar o quantum. Essa semântica de fatia
é uma convenção do simulador, compatibilizada com o campo exigido pelo enunciado.

Concluir exatamente no prazo é válido. Uma ocorrência atrasada continua até
completar sua duração e registra uma única perda por prazo vigente.

## Tarefa e ocorrências

O TCB guarda parâmetros da tarefa e os dados da ocorrência atual. Novas ativações
em `ingresso + k * periodo` entram em `ocorrencias_pendentes` quando a atual ainda
não terminou. Cada pendente guarda ativação, prazo absoluto e indicador de perda.
A fila é FIFO: a próxima só recebe CPU após a anterior terminar. Uma mesma tarefa
não ocupa duas CPUs simultaneamente. O prazo também pode vencer na fila.

A soma de ocorrências concluídas, atual e pendentes é limitada a dez. O motor
termina após dez conclusões; não descarta liberações dentro desse conjunto admitido.
Ao promover uma pendente, conserva seu prazo e sua eventual perda já registrada.

Fundamento conferido no capítulo fornecido: seção 2.2 (ativações como instâncias)
e seção 2.5.3, página impressa 33 / página 23 do PDF (execução posterior aguarda
liberações anteriores). Figuras 2.5 e 2.6 têm testes no repositório. O enunciado
exige múltiplas CPUs; os exemplos de uma CPU não provam otimalidade multiprocessador.

## Edição e configuração

A GUI envia somente campos alterados à API do motor. CPU, progresso e contadores
não são entradas editáveis. PRONTA/EXECUTANDO/SUSPENSA preservam a ocorrência;
AGUARDANDO abandona a ocorrência e sua fila sem fabricar conclusões. Iniciar uma
ocorrência manualmente antes do ingresso é rejeitado. FINALIZADA exige dez conclusões.

- Duração vale para ocorrências ainda não concluídas; deve superar o progresso atual.
- Prazo é recalculado desde as ativações da atual e das pendentes. Indicadores de
  perda são reiniciados; a verificação do prazo editado ocorre no próximo tick.
- Período altera somente ativações futuras. Ingresso não pode ultrapassar a ativação
  de uma ocorrência ainda em curso ou pendente. Cores devem permanecer distintas.
- Reduzir CPUs libera tarefas interrompidas e reinicia suas fatias. Alterar quantum
  também reinicia as fatias. Algoritmo é restaurado ao navegar pelo histórico.

Suspensão é manual no Projeto A. Execução completa informa a impossibilidade de
prosseguir com tarefa suspensa ou sem CPUs, em vez de entrar em laço infinito.
A janela usa lotes curtos com `after()` e desenha o resultado ao terminar.

## Arquivo e exportação

O parser aceita UTF-8 com/sem BOM, espaços, linhas vazias e terminador opcional.
IDs numéricos viram inteiros; textuais usam casefold. Cores viram #RRGGBB. IDs são
únicos no arquivo; cores são distintas entre periódicas incluídas. Registros
aperiódicos válidos geram avisos e são ignorados. Não há máximos arbitrários de
tarefas, CPUs ou duração. Campos de configuração vazios recebem os padrões de
`padroes.py`, com aviso individual; valores explícitos inválidos e formato errado
são rejeitados. Eventos vazios são normais e não recebem valores do Projeto B.

O prazo zero é aceito em registros aperiódicos (período zero), pois não são
executados no Projeto A; eles são ignorados com aviso. Periódicas continuam
exigindo prazo positivo. Prazos negativos ou não inteiros são rejeitados.

Os padrões são RM, quantum 0, duas CPUs, duração 1, período e prazo 10.
São escolhas didáticas, editáveis, sem tentativa de inferir um conjunto escalonável.
ID e cor sugeridos ficam livres; IDs explícitos posteriores no arquivo são
reservados antes. Inclusão manual sugere ingresso no tick atual e rejeita passado.
O botão de sugestão só preenche entradas, sem alterar a simulação por si só.
Na edição preserva ID/estado, não avança o ingresso original e sugere uma duração
maior que o progresso atual.

Inclusão/remoção substituem o snapshot selecionado por cópia e descartam somente
o futuro. A remoção abandona a tarefa e suas ocorrências pendentes, libera CPU e
não registra conclusão artificial. Ambas geram eventos próprios no Gantt;
linhas de tarefas removidas continuam visíveis no prefixo histórico. IDs usados
nesse prefixo não podem ser reutilizados, evitando juntar tarefas diferentes.
As sugestões também evitam cores históricas; cores explícitas precisam ser únicas
entre as tarefas presentes. Nova simulação reinicia o histórico.

SVG conserva o prefixo inteiro, a escala padrão de 24 px/tick e a legenda, sem
recortar pelo viewport. Texto é escapado pelo drawsvg. Suspensão tem preenchimento
distinto e eventos têm formas próprias. Sorteio marca somente selecionadas. IDs
numéricos maiores ficam acima dos menores. Na tela, zoom recalcula coordenadas
horizontais e mantém fonte fixa; detalhes estreitos precisam de aproximação.

Ao concluir pela janela, salva SVG ao lado da configuração. Um nome existente
recebe sufixo numérico. Sem arquivo de entrada, solicita o destino ao concluir;
cancelar mantém o resultado disponível para exportação posterior. Falhas de escrita preservam resultados e permitem escolher
outro destino. Na CLI, o destino é explícito. Não se criam diretórios de saída.
