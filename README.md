# Simulador de escalonamento - Projeto A

Versão de envio ao Moodle. Esta pasta contém exatamente **20 arquivos**, todos
na raiz: 10 módulos Python, 5 configurações, 1 textura, 1 script de construção,
1 PDF, este README e 1 executável. Envie os arquivos avulsos, sem compactar.

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
são saídas do programa; não fazem parte dos 20 arquivos originais da entrega.

## Gerar novamente o executável: o equivalente ao make

O arquivo **make.ps1** usa **PyInstaller**. Para reconstruir, é necessário Python
3.11 x64 no Windows e acesso à internet para obter as dependências fixadas no
próprio script. No PowerShell, dentro desta pasta:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1
```

Se o comando Python tiver outro nome ou caminho:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\make.ps1 -Python "C:\caminho\python.exe"
```

O script cria um ambiente virtual temporário, instala as versões fixadas e gera
somente SimuladorSO.exe nesta pasta. Os arquivos auxiliares de construção ficam
fora dela e são removidos ao final. Feche o executável antes de reconstruí-lo.
A opção -UsarAmbienteAtual reaproveita um Python que já tenha as quatro
dependências instaladas; serve para desenvolvimento, sem criar outro ambiente.

Para executar diretamente o código, instale customtkinter==6.0.0 e drawsvg==2.4.2
no seu Python e use `python -B gui.py configuracao.txt`. O `-B` evita criar caches
de bytecode ao lado dos fontes.

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
incluída no executável pelo script. O SVG usa sua própria textura vetorial.

## Bibliotecas e licença

CustomTkinter: https://github.com/TomSchimansky/CustomTkinter

drawsvg: https://github.com/cduck/drawsvg

A interface usa também Tkinter/Tcl/Tk, fornecidos com o Python. Metadados e
licenças das bibliotecas coletadas acompanham o executável. A licença do código
do projeto está reproduzida abaixo para manter a entrega em 20 arquivos.

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
