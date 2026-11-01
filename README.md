# Simulador de escalonamento — Projeto A

Simulação preemptiva RM/EDF com múltiplas CPUs, histórico por tick e interface
CustomTkinter. O Canvas do Tkinter mostra o Gantt; drawsvg gera o arquivo vetorial.

## Executar no Windows

O ambiente `.venv-ctk` já está preparado nesta máquina. Na raiz do projeto:

```powershell
.\.venv-ctk\Scripts\python.exe gui.py exemplos/configuracao.txt
```

Em outra instalação, prepare Python 3.11 com `uv`:

```powershell
uv venv --python 3.11 .venv-ctk
uv pip install --python .venv-ctk/Scripts/python.exe -r requirements.txt
.\.venv-ctk\Scripts\python.exe gui.py
```

Abra um arquivo ou clique em Nova simulação e Adicionar. Selecione uma tarefa
para inspecionar, editar ou remover; avance e volte pelos ticks.
Zoom e rolagem só alteram a visualização. Uma edição aceita descarta o futuro do
instante selecionado e preserva os estados anteriores. Executar até o fim termina
após dez ocorrências concluídas por tarefa. Ao concluir, o SVG é salvo ao lado da
configuração; nomes existentes recebem sufixo numérico. Sem arquivo de entrada,
a janela solicita o destino do SVG final. Exportar SVG permite
escolher outro destino ou salvar um estado intermediário.

## Arquivo de entrada

```text
algoritmo;quantum;quantidade_cpus
id;cor;ingresso;duracao;periodo;prazo;lista_eventos
```

Algoritmos: RM e EDF. Tempos em ticks inteiros; cores RGB hexadecimais. Espaços,
linhas vazias, maiúsculas/minúsculas e terminador `;` opcional são tratados.
Aperiódicas (período zero) são ignoradas com aviso. A lista de eventos pertence ao
Projeto B e não é executada. Erros informam o motivo e a linha quando aplicável.
Prazo zero em uma aperiódica é aceito para ignorá-la; tarefas periódicas continuam
exigindo prazo positivo.

## Valores padrão

As sugestões ficam em `padroes.py` e podem ser substituídas antes de aplicar:

| Característica | Sugestão |
|---|---|
| Algoritmo, quantum, CPUs | RM, 0 (sem limite de fatia), 2 |
| ID e cor | Próximo inteiro positivo livre e cor disponível |
| Ingresso | 0 no arquivo; tick atual na inclusão manual |
| Duração, período, prazo relativo | 1, 10, 10 ticks |

O botão Sugerir padrões preenche o formulário; Salvar/Aplicar confirma a mudança.
Na edição, ingresso permanece compatível com o histórico e duração supera o
progresso já executado. Estado, CPU, contadores e prazo absoluto são controlados
pelo motor; a nova tarefa começa AGUARDANDO, sem execuções anteriores.

No arquivo, campos de configuração vazios recebem sugestões com avisos por
campo. Valores explícitos prevalecem. Cabeçalho/registro ausente, número errado
de campos e valores explícitos inválidos continuam sendo erros. Por exemplo:

```text
;;
;;;;;;
```

Isso cria uma tarefa com os padrões. IDs e cores explícitos das linhas seguintes
são reservados antes de gerar sugestões.

## Roteiro para explicar o código

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | Dados de tarefa, ocorrência, CPU e snapshot. |
| `scheduler.py` | Ordenação RM/EDF e desempates. |
| `engine.py` | Ativar, despachar, executar, verificar prazos e guardar histórico. |
| `validacao.py` | Regras básicas de inteiros, cores RGB e algoritmo. |
| `padroes.py` | Valores iniciais e sugestões de ID/cor disponíveis. |
| `parser.py` | Converter o arquivo em estado inicial, algoritmo e avisos. |
| `linha_tempo.py` | Converter o histórico selecionado em intervalos. |
| `gantt.py` | Um desenho para Canvas e drawsvg: retângulos, linhas, textos e símbolos. |
| `exporter.py` | CLI de execução completa e exportação SVG. |
| `gui.py` | Controles, inspeção e chamadas ao motor; execução em lotes por `after()`. |

CustomTkinter fornece os controles e a aparência; Tkinter fornece o Canvas;
drawsvg escreve o SVG. O projeto posiciona os intervalos e os eventos. Não há
Qt Designer, Matplotlib ou geração manual de XML na aplicação atual.

Para acompanhar o motor, comece por `_executar_um_tick` em `engine.py`:

```text
estado t → copiar → ativar → despachar → executar → verificar prazos → estado t+1
```

O snapshot `t` antecede o intervalo `[t, t+1)`. As quatro etapas têm funções
próprias: `_ativar_tarefas`, `_despachar`, `_executar_tarefas` e `_verificar_prazos`.
A execução chama operações menores: `_executar_uma_unidade`,
`_concluir_ocorrencia` e `_registrar_fim_quantum`. `_iniciar_ocorrencia` também
é usada ao promover uma ocorrência que esperava em FIFO.

RM prioriza o menor período; EDF prioriza o menor prazo absoluto. Desempates:
quem executava, prazo relativo, ingresso, duração e sorteio. Ocorrências da mesma
tarefa esperam em FIFO e preservam seus prazos; somente uma executa por vez.

O motor está dividido em quatro seções: navegação/histórico, intervenções
manuais, ciclo automático e operações das ocorrências/CPUs. Para explicar uma
edição, siga `modificar_tarefa_em_execucao`: validar campos → preparar a cópia →
ajustar ocorrência e fila → verificar CPU → aplicar. Rejeições não chegam à
etapa de aplicação. `_substituir_estado_atual` concentra o descarte do futuro.

`concluida` consulta o término; `pode_continuar_execucao` explica impedimentos.
A CLI e os lotes da interface usam essa mesma decisão. A GUI controla quando
agendar outro lote, mantendo a janela responsiva.

No parser, comece por `carregar_configuracao`: `_ler_registros` →
`_ler_cabecalho` → `_ler_tarefas` → construir o estado inicial. `_ler_tarefas`
reserva IDs/cores explícitos antes das sugestões e usa `_ler_tarefa` para cada
registro. As regras básicas estão em `validacao.py`; o parser acrescenta o
número da linha às mensagens de erro.

## Exemplos e verificação

- `exemplos/configuracao.txt`: duas CPUs e três tarefas; termina no tick 185.
- `exemplos/rm-perda-prazo.txt` e `exemplos/edf-prazos.txt`: figura 2.6 do capítulo,
  com IDs 1 e 2 para A e B. Até o tick 60, RM perde o prazo de 2 em 50; EDF não.
- `exemplos/sobreposicao.txt`: duração 5 e período 3; dez conclusões no tick 50.

```powershell
.\.venv-ctk\Scripts\python.exe -B -m unittest discover -v
.\.venv-ctk\Scripts\python.exe exporter.py exemplos/configuracao.txt gantt.svg
```

O SVG contém todo o prefixo selecionado e sua legenda, independentemente do zoom.
Na CLI, a simulação é executada até o fim. O diretório de destino deve existir.

## Documentação e entrega

- [PDF com as telas e a origem dos dados](output/pdf/Projeto-A-Telas-e-Origem-dos-Dados.pdf), para envio avulso no Moodle.
- [Decisões e convenções](docs/decisoes.md).
- [Plano e verificação da refatoração](docs/refatoracao.md).
- [Requisitos ainda pendentes](docs/pendencias.md).
- [Empacotamento e validação Windows](docs/distribuicao.md).

O enunciado local está em `referencias/simulador-escalonamento.md` e `.pdf`,
preservado fora do versionamento. Os protótipos anteriores e a implementação Qt
permanecem acessíveis no histórico Git (`94ace73`). A versão organizada para entrega está na branch
`entrega`, derivada de `codex/customtkinter-drawsvg`; a main permanece na versão anterior.

**Ainda falta:** homologação em Windows limpo e ensaio dos exemplos pelo autor.
