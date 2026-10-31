# Pendências do Projeto A

Ponto de entrada para estudar e apresentar: README.md. Decisões do modelo: docs.md.
Este arquivo descreve o estado atual; os diagnósticos anteriores da interface e do
primeiro build estão preservados como histórico nos documentos específicos.

## Requisitos ainda abertos

- [ ] **Valores padrão (3.2):** sugerir valores para todas as características, com
  substituição explícita pelo usuário. Exemplos e valores iniciais de alguns
  controles não cobrem todo o requisito. O parser rejeita dados ausentes;
  não preenche silenciosamente arquivos inválidos.
- [ ] **Conjunto de tarefas em execução (3.1):** implementar inclusão/remoção com
  validação e sem alterar snapshots anteriores. A edição individual trata
  tarefas já carregadas. Carregar outro arquivo reinicia a simulação.
- [ ] **Homologação da distribuição (geral 5):** testar o ZIP em Windows x64 limpo,
  sem Python/Qt/ferramentas instalados. A verificação local com PATH restrito não
  substitui uma máquina limpa. Detalhes em EMPACOTAMENTO.md.
- [ ] **Ensaio do autor:** abrir um arquivo próprio e explicar um cenário RM e EDF,
  a fila de ocorrências, uma perda de prazo, edição/retrocesso e a exportação final.

## Implementado e coberto por testes

- [x] Ticks, múltiplas CPUs, fila global, RM/EDF preemptivos e desempates.
- [x] Histórico completo, reprodução dos sorteios e edição individual validada.
- [x] Ocorrências sobrepostas em FIFO por tarefa, com ativação e prazo preservados.
- [x] Perda de prazo também durante a espera; dez conclusões sem descartar ativações
  dentro do conjunto admitido; somente uma ocorrência da tarefa executa por vez.
- [x] Configuração global validada no motor; operação sem mudanças preserva futuro;
  RM/EDF, quantum e CPUs restaurados pelo histórico; redução de CPUs reinicia fatias.
- [x] Campos de configuração não truncam números por limites de QSpinBox.
- [x] Gantt agrupado, CPU identificada no zoom, eventos recortados, legenda única,
  barra temporal e rolagem vertical. Ordem física dos IDs verificada.
- [x] Sorteio associado somente às tarefas selecionadas, inclusive múltiplas CPUs.
- [x] SVG vetorial integral independente do zoom e da janela, pela GUI e CLI.
- [x] Imagem final automática, inclusive pelo último passo manual, preservando
  arquivos existentes e resultados quando há falha de escrita.
- [x] Parser de arquivos externos, avisos de aperiódicas e erros com motivo/linha.
- [x] Exemplos das figuras 2.5 e 2.6 do capítulo reproduzidos em testes.
- [x] Script de build inclui .ui, dependências, exemplo e instruções no ZIP.

## Convenções a explicar

quantum=0 remove o limite de fatia e mantém a preempção. Expiração de quantum não
obriga rodízio: RM/EDF são reavaliados a cada tick. Suspensão é manual no Projeto A.
AGUARDANDO abandona a ocorrência atual e sua fila, sem contar conclusões. As regras
de edição de duração, prazo e período estão em docs.md. Não incluir os servidores,
eventos de mutex/E/S ou tarefas aperiódicas/esporádicas do Projeto B nesta entrega.
