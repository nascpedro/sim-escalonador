# Simulador de escalonamento — Projeto A

Simulação de tarefas periódicas em múltiplas CPUs, com escalonamento RM e EDF,
histórico por tick e visualização em Gantt.

## Execução

No Windows x64, abra `SimuladorSO.exe`. Na interface, escolha **Abrir arquivo**
ou **Nova simulação**. O executável inclui Python e as bibliotecas necessárias.
Também é possível informar a configuração ou exportar o Gantt sem abrir a janela:

```powershell
.\SimuladorSO.exe configuracao.txt
.\SimuladorSO.exe --exportar exemplo_edf.txt resultado.svg
```

Para executar pelo código-fonte, use Python 3.11+ com Tkinter disponível.
Na pasta do projeto, instale as dependências e inicie a interface:

```sh
python -m pip install customtkinter==6.0.0 drawsvg==2.4.2
python -B gui.py
```

Para carregar uma configuração na inicialização ou gerar somente o SVG:

```sh
python -B gui.py configuracao.txt
python -B exporter.py exemplo_edf.txt resultado.svg
```

## Modelo da simulação

O relógio global avança em ticks. O snapshot no instante `t` representa o estado
antes da execução do intervalo `[t, t+1)`. Cada avanço segue esta sequência:

1. Copiar o snapshot atual.
2. Ativar as ocorrências previstas para o tick.
3. Ordenar as tarefas candidatas e despachá-las para as CPUs.
4. Executar uma unidade de tempo, processando conclusões e fim de quantum.
5. Verificar os prazos e incrementar o relógio.

O escalonamento é global e preemptivo: tarefas prontas ou em execução disputam
as CPUs disponíveis. RM prioriza o menor período; EDF, o menor prazo absoluto.
Os desempates consideram, nesta ordem: já estar executando, menor prazo relativo,
menor ingresso, menor duração e sorteio. Quantum zero remove o limite de fatia,
mas mantém a preempção.

Cada ativação tem prazo absoluto igual ao instante de ativação mais o prazo
relativo. Terminar exatamente no prazo é válido. Uma ocorrência que perde o
prazo continua executando até concluir.

Se uma nova ocorrência chegar antes de a anterior terminar, ela aguarda em FIFO,
com seu prazo contado desde a ativação original. Duas ocorrências da mesma tarefa
não executam simultaneamente. Cada tarefa termina após dez conclusões.

O histórico mantém os snapshots para avançar e retroceder. Ao avançar sobre um
futuro já calculado, o motor reutiliza os estados armazenados. Uma edição aceita
altera o snapshot selecionado e descarta os posteriores, preservando o passado.

No Projeto A, tarefas aperiódicas (período zero) são ignoradas com aviso. O campo
`lista_eventos` pertence ao Projeto B e não é executado.

## Componentes do código

| Arquivo | Responsabilidade |
|---|---|
| `models.py` | TCB, ocorrência, CPU, estados da tarefa e snapshot da simulação. |
| `parser.py` | Leitura da configuração, conversão dos campos e avisos de entrada. |
| `validacao.py` | Validação de inteiros, cores e algoritmo. |
| `padroes.py` | Sugestões de configuração, IDs e cores disponíveis. |
| `scheduler.py` | Prioridades RM/EDF, desempates e sorteios. |
| `engine.py` | Ciclo do tick, histórico e intervenções manuais. |
| `linha_tempo.py` | Conversão do histórico em intervalos de execução, espera, suspensão e ociosidade. |
| `gantt.py` | Geometria, barras, eventos e legenda do Gantt para Canvas e SVG. |
| `gui.py` | Interface CustomTkinter, formulários e controles da simulação. |
| `exporter.py` | Execução completa e exportação SVG por linha de comando. |

O fluxo dos dados é: configuração → motor e escalonador → histórico → intervalos
→ Gantt. A interface solicita operações ao motor e apresenta seus resultados.
O desenho usa as mesmas funções para a tela (Canvas Tkinter) e para o arquivo
SVG (drawsvg), por meio de adaptadores de retângulo, linha, texto e polígono.

## Geração do executável

O empacotamento usa PyInstaller. Para reconstruir a versão Windows, execute os
comandos abaixo na pasta do projeto, com o executável fechado:

```powershell
python -m pip install customtkinter==6.0.0 drawsvg==2.4.2 pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
python -m PyInstaller --noconfirm --clean --onefile --windowed --name SimuladorSO --distpath . --collect-data customtkinter --add-data "ociosa.xbm;." --copy-metadata customtkinter --copy-metadata drawsvg --copy-metadata darkdetect --copy-metadata packaging gui.py
```

O resultado é `SimuladorSO.exe` na própria pasta. O comando inclui os recursos
do CustomTkinter, a textura `ociosa.xbm` e os metadados das bibliotecas. O modo
`onefile` reúne o programa em um executável que extrai seus recursos para uma
pasta temporária ao iniciar. `build/` e `SimuladorSO.spec` são saídas auxiliares
do empacotamento.

Para executar os fontes, é necessário instalar Python e as dependências; para
usar o executável compatível com o sistema, essas instalações não são necessárias.
O PyInstaller deve ser executado no sistema de destino: Windows para Windows,
Linux para Linux e macOS para macOS. O comando acima e a aplicação foram
validados no Windows x64; outros sistemas precisam de adaptação e validação.

## Licença

```text
MIT License

Copyright (c) 2026 Pedro Nascimento

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```
