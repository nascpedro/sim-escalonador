# Simulador de escalonamento - Projeto A

Versão de envio ao Moodle. Esta pasta contém exatamente **19 arquivos**, todos
na raiz: 10 módulos Python, 5 configurações, 1 textura, 1 PDF, este README e 1
executável. Envie os arquivos avulsos, sem compactar.

## Executar sem instalar Python ou bibliotecas

No Windows x64, abra **SimuladorSO.exe**. Escolha Abrir arquivo e selecione uma
das configurações desta pasta, ou use Nova simulação para incluir tarefas.
O executável contém Python, Tcl/Tk, CustomTkinter e drawsvg. Não separe nenhum
outro arquivo de runtime: o programa foi gerado no modo onefile do PyInstaller.
Na inicialização ele extrai seus recursos para uma pasta temporária.

Também aceita um arquivo por argumento:

```powershell
.\SimuladorSO.exe configuracao.txt
.\SimuladorSO.exe --exportar exemplo_edf.txt resultado.svg
```

A interface permite avançar/voltar, alterar tarefas e configuração, executar até
dez conclusões por tarefa e exportar SVG. Ao terminar pela janela, salva o SVG ao
lado da configuração sem sobrescrever arquivos existentes. Os SVGs resultantes
são saídas do programa; não fazem parte dos 19 arquivos originais da entrega.

## Executar a partir do código-fonte ou gerar novamente o executável

Para executar diretamente os fontes em Python 3.11+, instale as duas bibliotecas
utilizadas pelo projeto e inicie `gui.py`:

```powershell
pip install customtkinter==6.0.0 drawsvg==2.4.2
python -B gui.py configuracao.txt
```

Para reconstruir **SimuladorSO.exe** por conta própria no Windows x64, instale o
PyInstaller e execute o comando de empacotamento dentro desta pasta (feche o
executável antes, caso esteja aberto):

```powershell
pip install customtkinter==6.0.0 drawsvg==2.4.2 pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
pyinstaller --noconfirm --clean --onefile --windowed --name SimuladorSO --distpath . --collect-data customtkinter --add-data "ociosa.xbm;." --copy-metadata customtkinter --copy-metadata drawsvg --copy-metadata darkdetect --copy-metadata packaging gui.py
```

O comando gera `SimuladorSO.exe` diretamente nesta pasta. As pastas auxiliares
`build/` e o arquivo `SimuladorSO.spec` criados pelo PyInstaller durante a
compilação podem ser apagados em seguida.

## Configurações incluídas

| Arquivo | Exemplo |
|---|---|
| configuracao.txt | RM, duas CPUs, três tarefas; termina no tick 185. |
| exemplo_edf.txt | EDF, duas CPUs; tarefa aperiódica ignorada com aviso; termina no tick 94. |
| rm-perda-prazo.txt | RM com perda de prazo, exemplo da figura 2.6 do capítulo. |
| edf-prazos.txt | Mesmo conjunto da figura 2.6 usando EDF. |
| sobreposicao.txt | Duração 5 e período 3; fila de ocorrências e dez conclusões no tick 50. |

Formato: `algoritmo;quantum;quantidade_cpus`, seguido de uma tarefa por linha:
`id;cor;ingresso;duracao;periodo;prazo;lista_eventos`. Campos de configuração
vazios recebem sugestões com aviso; valores explícitos prevalecem. Aperiódicas
(período zero) são ignoradas no Projeto A, inclusive com prazo zero. O campo
lista_eventos pertence ao Projeto B e não é executado.

Os exemplos e o PDF foram reunidos na raiz para o envio. O conteúdo corresponde
aos arquivos citados no PDF; referências antigas à subpasta exemplos indicam os
mesmos arquivos agora presentes nesta pasta.

## Organização do código

| Arquivo | Responsabilidade |
|---|---|
| models.py | TCB, ocorrência, CPU e snapshot. |
| scheduler.py | Prioridades RM/EDF, desempates e sorteios. |
| engine.py | Histórico, intervenções e ciclo do tick. |
| parser.py | Leitura e validação da configuração. |
| padroes.py | Valores sugeridos de configuração e tarefa. |
| validacao.py | Regras básicas de inteiros, cores e algoritmo. |
| linha_tempo.py | Intervalos de execução, prontas, suspensão e ociosidade. |
| gantt.py | Desenho compartilhado entre Canvas e SVG. |
| exporter.py | Exportação por linha de comando. |
| gui.py | Interface CustomTkinter e formulários. |

O ciclo do motor é copiar → ativar → despachar → executar → verificar prazos.
O estado no tick t antecede [t,t+1). Ocorrências sobrepostas aguardam em FIFO.
O escalonador é global e preemptivo. Quantum zero mantém preempção e remove
somente o limite de fatia. O Gantt mostra CPUs no topo, prontas com contorno,
suspensas com pontilhado e preempções com duas barras magenta. Chegada usa o
polígono circular azul; conclusão usa o triângulo verde para baixo.

O PDF **Projeto-A-Telas-e-Origem-dos-Dados.pdf** apresenta as telas, a função dos
controles e a origem dos dados. A textura ociosa.xbm é usada pelo Canvas e
incluída no executável pelo PyInstaller. O SVG usa sua própria textura vetorial.

## Bibliotecas e licença

CustomTkinter: https://github.com/TomSchimansky/CustomTkinter

drawsvg: https://github.com/cduck/drawsvg

A interface usa também Tkinter/Tcl/Tk, fornecidos com o Python. Metadados e
licenças das bibliotecas coletadas acompanham o executável. A licença do código
do projeto está reproduzida abaixo para manter a entrega em 19 arquivos.

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
