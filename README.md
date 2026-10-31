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
| `padroes.py` | Valores iniciais e sugestões de ID/cor disponíveis. |
| `parser.py` | Converter o arquivo em estado inicial, algoritmo e avisos. |
| `linha_tempo.py` | Converter o histórico selecionado em intervalos. |
| `gantt.py` | Um desenho para Canvas e drawsvg: retângulos, linhas, textos e símbolos. |
| `exporter.py` | CLI de execução completa e exportação SVG. |
| `gui.py` | Controles, inspeção e chamadas ao motor; execução em lotes por `after()`. |

CustomTkinter fornece os controles e a aparência; Tkinter fornece o Canvas;
drawsvg escreve o SVG. O projeto posiciona os intervalos e os eventos. Não há
Qt Designer, Matplotlib ou geração manual de XML na aplicação atual.

O snapshot `t` antecede o intervalo `[t, t+1)`. Cada tick copia o estado, ativa
ocorrências, escolhe tarefas, executa uma unidade e verifica conclusões/prazos.
RM prioriza o menor período; EDF prioriza o menor prazo absoluto. Desempates:
quem executava, prazo relativo, ingresso, duração e sorteio. Ocorrências da mesma
tarefa esperam em FIFO e preservam seus prazos; somente uma executa por vez.

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

- [Decisões e convenções](docs/decisoes.md).
- [Requisitos ainda pendentes](docs/pendencias.md).
- [Empacotamento e validação Windows](docs/distribuicao.md).

O enunciado local está em `referencias/simulador-escalonamento.md` e `.pdf`,
preservado fora do versionamento. Os protótipos anteriores e a implementação Qt
permanecem acessíveis no histórico Git (`94ace73`). Esta migração está na branch
`codex/customtkinter-drawsvg`; a main ainda aponta para a versão anterior.

**Ainda falta:** homologação em Windows limpo e ensaio dos exemplos pelo autor.
