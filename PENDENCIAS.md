# Pendências do Projeto A

Este arquivo acompanha o escopo; item em aberto não significa requisito atendido.

## Rodada atual

- [x] Parser: carregar arquivo texto UTF-8, validar formato e parâmetros e informar tarefas aperiódicas ignoradas. API: carregar_configuracao(caminho) retorna (estado_inicial, algoritmo, avisos). Valores padrão continuam pendentes, não há interface de seleção de arquivo.
- [x] Motor: registrar ingresso inicial e ativações periódicas com os instantes corretos, preservando o histórico.

## Próximas pendências do motor

- [x] Edição por campos: `modificar_tarefa_em_execucao(id_tarefa, **alteracoes)`. Campos disponíveis: ingresso, duracao, periodo, prazo, cor e estado_tarefa. Valida somente as entradas e sua compatibilidade com a ocorrência atual. CPU e prazo absoluto são administrados pelo motor, não enviados pelo usuário. Rejeição preserva o estado e o futuro; aceitação copia a tarefa, sincroniza CPUs e descarta só o futuro. O parser permanece responsável pela entrada do arquivo.

### Semântica da edição

- Trocar entre PRONTA, EXECUTANDO e SUSPENSA preserva o progresso e o instante da ativação atual. EXECUTANDO exige CPU livre ou a própria CPU, escolhida pelo motor.
- Colocar uma ocorrência ativa em AGUARDANDO abandona seu progresso sem contabilizar conclusão e espera uma próxima ativação. Sair de AGUARDANDO para um estado ativo inicia uma ocorrência no tick atual, desde que a tarefa já tenha ingressado.
- Alterar prazo recalcula o prazo absoluto a partir da ativação atual; eventual perda pelo novo prazo será verificada no próximo tick. Alterar ingresso não pode colocá-lo depois de uma ativação que ainda está em curso. Alterar período passa a orientar as próximas ativações, sem reiniciar a ocorrência atual.
- FINALIZADA corresponde às dez ocorrências concluídas pelo motor. ID e campos internos (CPU, progresso, contadores e indicadores) não fazem parte da entrada editável.

### Ainda pendente no motor

- [ ] Definir a aplicação do quantum em RM/EDF antes de implementar sua contabilização. Hoje o valor é apenas armazenado.
- [ ] Definir o tratamento de uma nova ativação quando a ocorrência anterior ainda não terminou. Hoje a nova ativação só ocorre se a tarefa estiver AGUARDANDO; não rejeitar duração ou prazo maior que período apenas para contornar essa lacuna.

## Pontos a verificar com o parser

- [ ] Confirmar política de valores padrão exigida pelo requisito 3.2; o enunciado não especifica os valores concretos. Não preencher silenciosamente campos inválidos.
- [x] Integrar o resultado do carregamento ao motor e verificar execução completa e passo a passo com arquivos reais, incluindo retrocesso.
- [x] Manter mensagens de erro e avisos disponíveis para a futura interface, sem implementar Projeto B.
- [x] Alinhar as anotações de tipo de IDs em TCB e edição com o parser: int ou str.

## Ainda fora desta rodada

Interface de controle/edição, Gantt com legenda e eventos, exportação integral da imagem e distribuição sem instalação de runtime. Apenas Projeto A.
