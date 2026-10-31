# Plano de refatoração para a entrega

Objetivo: aproximar a leitura do código da explicação do simulador, preservando
as regras do Projeto A e o comportamento já verificado.

1. Organizar o motor em navegação/histórico, intervenções manuais, ciclo do tick
   e operações das ocorrências. Nomear execução, conclusão e fim de quantum.
2. Dividir a edição manual em validar campos, preparar a ocorrência, verificar
   CPU e aplicar. Rejeições devem preservar todo o histórico.
3. Compartilhar validações básicas e a atualização do histórico; manter contexto
   de erros no parser e no formulário.
4. Concentrar no motor as decisões de término e impedimentos da execução
   completa. A interface continua responsável pelos lotes e callbacks.
5. Organizar o parser em leitura das linhas, cabeçalho, reserva de sugestões e
   carregamento das tarefas. Preservar avisos, números de linha e formatos aceitos.
6. Alinhar o roteiro do README às funções, executar os testes e comparar os
   históricos anteriores e posteriores com sorteio controlado. Reconstruir e
   verificar o executável e o ZIP.

Não criar uma máquina genérica de estados nem uma hierarquia de classes. As
operações devem ter significado concreto: iniciar ocorrência, concluir ocorrência,
liberar CPU. A ordem do tick continua ativar → despachar → executar → verificar.


## Resultado da implementação

Etapas 1 a 5 concluídas na branch `entrega`. O README acompanha o mesmo roteiro
e aponta as funções de cada etapa. Os 93 testes existentes passaram sem mudanças
nas expectativas.

A comparação com `7d8da40` usou 50 conjuntos gerados com semente fixa, cada um em
RM e EDF (100 cenários). Comparou o histórico completo após avanço, retrocesso,
configuração, edição, suspensão/retomada, inclusão/remoção, rejeição de edição,
reaproveitamento do futuro e término. Sorteios tiveram a mesma semente nas duas
versões. Estados, eventos e resultados foram iguais nesses cenários.

Também foram comparadas 12 entradas do parser: exemplos, padrões, aperiódicas,
IDs duplicados e formatos inválidos. Entradas aceitas produziram o mesmo estado
e os mesmos avisos; rejeições mantiveram o tipo de erro. A redação de algumas
mensagens foi uniformizada, preservando campo, motivo e linha.

O relatório dessa comparação está no artefato local ignorado
`build/comparacao-refatoracao.json`.


Etapa 6 concluída: 93 testes aprovados, pacote reconstruído e verificado em três
exportações completas, uma entrada inválida e duas execuções da interface
empacotada, incluindo inclusão/remoção. O ZIP passou na conferência de CRC.
O teste em Windows limpo e o ensaio do autor continuam pendentes, conforme
`pendencias.md`; a refatoração não substitui essas verificações.
