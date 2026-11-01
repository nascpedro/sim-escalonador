# Distribuição Windows

## Gerar o pacote

Use Python 3.11 x64 no ambiente `.venv-ctk`. As dependências estão fixadas em
requirements.txt e requirements-build.txt. Na raiz do repositório:

```powershell
uv pip install --python .venv-ctk/Scripts/python.exe -r requirements-build.txt
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/empacotar.ps1
```

O script gera `dist/SimuladorSO/` e `dist/SimuladorSO-windows-x64.zip`.
Extraia/copie a pasta inteira antes de executar `SimuladorSO.exe`.
Para preparar somente a pasta executável, use `scripts/empacotar.ps1 -SemZip`.
No Moodle, envie os arquivos avulsos conforme as regras; não envie o ZIP.
Python, Tcl/Tk, CustomTkinter, fontes/temas e drawsvg acompanham o pacote.
Não há dependência de Qt/Matplotlib nem arquivo de formulário .ui.

O PyInstaller usa onedir/windowed e coleta os dados de CustomTkinter, além dos
metadados/licenças das bibliotecas distribuídas. O PATH é
restrito ao Windows durante a análise para evitar DLLs de outras ferramentas.
Exemplos, licença e instruções são copiados para a distribuição. O script só
atualiza o ZIP depois de aprovar a verificação do executável.

## Verificação reproduzível

```powershell
.\.venv-ctk\Scripts\python.exe -B -m unittest discover -v
.\.venv-ctk\Scripts\python.exe -B scripts/verificar_distribuicao.py dist/SimuladorSO
```

A sonda usa diretório temporário fora do repositório e PATH limitado ao
Windows/System32. Verifica três exportações completas até o tick 185 e uma
entrada inválida. Também instancia a janela empacotada duas vezes, avança/volta,
executa por callbacks até o fim, confere o Canvas e o SVG automático, e fecha a
janela. Também cria uma simulação sem arquivo, inclui e remove uma tarefa e
exporta seu histórico. Temas e Tcl/Tk são assim exercitados no executável, além dos testes do código.
As janelas de diagnóstico ficam ocultas e os SVGs usam pastas temporárias.
O relatório local é salvo em `build/verificacao-distribuicao.json`.

Uso da exportação sem abrir janela:

```powershell
.\SimuladorSO.exe --exportar exemplos/configuracao.txt resultado.svg
```

## Limites da validação

Resultado local em 31/10/2026: **99 testes aprovados, sem testes ignorados**.
O pacote passou em três exportações (SVG vetorial completo), uma entrada
inválida e duas inicializações/execuções/fechamentos da interface empacotada. Cada
execução da janela chegou ao tick 185 com 30 conclusões e gerou SVG automático.
O ZIP foi conferido por CRC e tem cerca de **11 MiB**, sem Qt/Matplotlib.

O teste local não é homologação em Windows limpo: o host tem Python instalado.
O ensaio visual da interface e um teste em VM/PC sem ferramentas continuam
necessários. O pacote é Windows x64; não foi preparado para Linux/macOS/ARM.

Os builds antigos Qt e seus diagnósticos permanecem no histórico Git. Eles não
representam a distribuição atual. As pastas build/ e dist/ são artefatos locais
ignorados, não código-fonte. Ambientes .venv* também ficam fora do versionamento.
