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

Abra um arquivo, avance/volte, selecione uma tarefa para inspecionar ou editar.
Zoom e rolagem só alteram a visualização. Uma edição aceita descarta o futuro do
instante selecionado e preserva os estados anteriores. Executar até o fim termina
após dez ocorrências concluídas por tarefa. Ao concluir, o SVG é salvo ao lado da
configuração; nomes existentes recebem sufixo numérico. Exportar SVG permite
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

## Roteiro para explicar o código

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | Dados de tarefa, ocorrência, CPU e snapshot. |
| `scheduler.py` | Ordenação RM/EDF e desempates. |
| `engine.py` | Ativar, despachar, executar, verificar prazos e guardar histórico. |
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

**Ainda falta:** política completa de valores padrão, inclusão/remoção de tarefas
durante a execução, homologação em Windows limpo e ensaio dos exemplos pelo autor.
