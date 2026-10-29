# Pendências do Projeto A

Este arquivo acompanha o escopo; item em aberto não significa requisito atendido.

## Rodada atual

- [x] Parser: carregar arquivo texto UTF-8, validar formato e parâmetros e informar tarefas aperiódicas ignoradas. API: carregar_configuracao(caminho) retorna (estado_inicial, algoritmo, avisos). Valores padrão continuam pendentes, não há interface de seleção de arquivo.
- [x] Motor: registrar ingresso inicial e ativações periódicas com os instantes corretos, preservando o histórico.

## Próximas pendências do motor

- [ ] Validar semanticamente alterações de tarefas, sem modificar o estado nem descartar o futuro se a alteração for rejeitada.
- [ ] Definir a aplicação do quantum em RM/EDF antes de implementar sua contabilização. Hoje o valor é apenas armazenado.
- [ ] Definir o tratamento de uma nova ativação quando a ocorrência anterior ainda não terminou. Hoje a nova ativação só ocorre se a tarefa estiver AGUARDANDO; não rejeitar duração ou prazo maior que período apenas para contornar essa lacuna.

## Pontos a verificar com o parser

- [ ] Confirmar política de valores padrão exigida pelo requisito 3.2; o enunciado não especifica os valores concretos. Não preencher silenciosamente campos inválidos.
- [x] Integrar o resultado do carregamento ao motor e verificar execução completa e passo a passo com arquivos reais, incluindo retrocesso.
- [x] Manter mensagens de erro e avisos disponíveis para a futura interface, sem implementar Projeto B.
- [ ] Alinhar as anotações de tipo de IDs em TCB e edição: o parser aceita IDs textuais e inteiros, mas as anotações existentes declaram somente int. A integração em execução funciona com ambos.

## Ainda fora desta rodada

Interface de controle/edição, Gantt com legenda e eventos, exportação integral da imagem e distribuição sem instalação de runtime. Apenas Projeto A.
