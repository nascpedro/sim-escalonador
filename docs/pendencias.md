# Pendências do Projeto A

## Antes da entrega

- [ ] **Requisito 3.2 — valores padrão:** definir sugestões para todas as
  características e como o usuário as substitui. Exemplos e valores iniciais de
  alguns controles não cobrem todo o requisito. Não preencher arquivo inválido
  silenciosamente para contornar a regra.
- [ ] **Requisito 3.1 — conjunto de tarefas:** incluir/remover tarefas durante a
  simulação, com validação e preservação dos snapshots anteriores. A API atual
  edita tarefas já carregadas; abrir outro arquivo reinicia a simulação.
- [ ] **Requisito geral 5 — máquina limpa:** homologar o pacote em Windows x64
  sem Python/Tcl/Tk/ferramentas instalados. PATH restrito no computador de
  desenvolvimento não substitui esse teste. Ver docs/distribuicao.md.
- [ ] **Ensaio:** executar um arquivo próprio, explicar RM/EDF, preempção,
  sobreposição, perda de prazo, edição no passado e SVG final. Conferir também
  legibilidade/zoom na resolução e escala de tela da apresentação.

## Implementado e verificado

- [x] Interface principal CustomTkinter + Canvas e exportação drawsvg.
- [x] Relógio por ticks, múltiplas CPUs e fila global de candidatas.
- [x] RM/EDF preemptivos, desempates e sorteios preservados no histórico.
- [x] FIFO de ocorrências sobrepostas, prazos na espera e dez conclusões.
- [x] Navegação pelo histórico e edição individual com validação no motor.
- [x] Configuração global transacional e restaurada pelo histórico.
- [x] Cores históricas, CPU e ociosidade, suspensão, eventos e legenda no Gantt.
- [x] SVG integral do prefixo selecionado, independente do zoom e da janela.
- [x] Imagem final automática sem sobrescrever arquivos existentes.
- [x] Parser de arquivos externos, avisos de aperiódicas e erros com motivo/linha.
- [x] Exemplos das figuras 2.5 e 2.6 do capítulo em testes executáveis.
- [x] 86 testes passaram na versão consolidada, sem dependências da interface antiga.
- [x] Novo pacote passou em três exportações e duas execuções da janela, com
  SVG automático e fechamento. ZIP de cerca de 11 MiB conferido por CRC.

A política de quantum e as consequências das edições estão em decisoes.md. Não
incluir recursos do Projeto B nesta entrega. As duas primeiras pendências são
funcionalidades ainda ausentes; limpeza do repositório não as resolve.
