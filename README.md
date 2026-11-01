# Simulador de escalonamento - Projeto A
#### Autores:
Pedro Eugenio Marin do Nascimento e Henrique Francisco Knapp

## Executar sem instalar Python ou bibliotecas

No Windows x64, abra **SimuladorSO.exe**. Escolha Abrir arquivo e selecione uma
das configurações desta pasta, ou use Nova simulação para incluir tarefas.


O executável contém Python, Tcl/Tk, CustomTkinter e drawsvg, gerado no modo onefile do PyInstaller.
Na inicialização ele extrai seus recursos para uma pasta temporária.

Também aceita um arquivo por argumento:

```powershell
.\SimuladorSO.exe configuracao.txt
.\SimuladorSO.exe --exportar exemplo_edf.txt resultado.svg
```

A interface permite avançar/voltar, alterar tarefas e configuração, executar até
dez conclusões por tarefa e exportar SVG. Ao terminar pela janela, salva o SVG ao
lado da configuração sem sobrescrever arquivos existentes. Os SVGs resultantes
são saídas do programa.

## Executar a partir do código-fonte ou gerar novamente o executável

Para executar diretamente os fontes em Python 3.11+, instale as duas bibliotecas
utilizadas pelo projeto e inicie `gui.py`:

```powershell
pip install customtkinter==6.0.0 drawsvg==2.4.2
python -B gui.py configuracao.txt
```

Para reconstruir **SimuladorSO.exe** por conta própria no Windows x64, instale o
PyInstaller e execute o comando de empacotamento dentro desta pasta:

```powershell
pip install customtkinter==6.0.0 drawsvg==2.4.2 pyinstaller==6.22.3 pyinstaller-hooks-contrib==2026.9
pyinstaller --noconfirm --clean --onefile --windowed --name SimuladorSO --distpath . --collect-data customtkinter --add-data "ociosa.xbm;." --copy-metadata customtkinter --copy-metadata drawsvg --copy-metadata darkdetect --copy-metadata packaging gui.py
```

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

O estado no tick t mostra o estado após os intervalos anteriores. O próximo avanço processa o intervalo de t até t+1.

Ocorrências sobrepostas aguardam em FIFO.

O escalonador é global e preemptivo.

O Gantt mostra CPUs no topo e tarefas abaixo, legendas para os símbolos podem ser encontradas logo abaixo do diagrama após a plotagem.

O PDF apresenta as telas, a função dos controles e a origem dos dados.

## Bibliotecas

CustomTkinter: https://github.com/TomSchimansky/CustomTkinter

drawsvg: https://github.com/cduck/drawsvg

PyInstaller: https://github.com/pyinstaller/pyinstaller — utilizado para empacotar o simulador e suas dependências em um executável.

A interface usa também Tkinter/Tcl/Tk, fornecidos com o Python.
