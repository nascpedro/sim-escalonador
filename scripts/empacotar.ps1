# Gera uma pasta Windows autossuficiente e um ZIP. Não instala dependências.
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path $PSScriptRoot -Parent
$PythonProjeto = Join-Path $Raiz '.venv-ctk\Scripts\python.exe'
$Dist = Join-Path $Raiz 'dist'
$Build = Join-Path $Raiz 'build'

# Restringe a busca de DLLs ao Windows durante a análise do build.
$PathAnterior = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $PythonProjeto -m PyInstaller --noconfirm --clean --onedir --windowed --name SimuladorSO `
        --collect-data customtkinter `
        --copy-metadata customtkinter --copy-metadata drawsvg `
        --copy-metadata darkdetect --copy-metadata packaging `
        --distpath $Dist --workpath (Join-Path $Build 'pyinstaller') --specpath $Build `
        (Join-Path $Raiz 'gui.py')
    if ($LASTEXITCODE -ne 0) { throw 'Falha no PyInstaller.' }
} finally {
    $env:PATH = $PathAnterior
}

$Pacote = Join-Path $Dist 'SimuladorSO'
Copy-Item -LiteralPath (Join-Path $Raiz 'exemplos') -Destination $Pacote -Recurse -Force
Copy-Item -LiteralPath (Join-Path $Raiz 'LICENSE') -Destination $Pacote -Force
@'
Simulador de escalonamento - Projeto A

Extraia a pasta inteira antes de executar SimuladorSO.exe.
Abra exemplos/configuracao.txt pelo botao Abrir arquivo, ou use Nova simulacao.
Adicionar/Editar/Remover alteram tarefas no instante selecionado.
Sugestoes: RM, quantum 0, 2 CPUs; tarefa de duracao 1, periodo e prazo 10.
Os formularios permitem substituir as sugestoes antes de aplicar.
Avance, retroceda e selecione uma tarefa para inspecionar ou editar.
O botao Executar ate o fim conclui dez ocorrencias de cada tarefa.
O SVG final e salvo ao lado da configuracao, sem sobrescrever arquivos existentes.
Use Exportar SVG para escolher outro destino ou exportar um estado intermediario.

Linha de comando, sem janela:
SimuladorSO.exe --exportar exemplos/configuracao.txt resultado.svg

Distribuicao Windows x64. Nao e necessario instalar Python ou bibliotecas.
O pacote ainda precisa de homologacao em uma maquina Windows limpa.
Sem arquivo de entrada, a janela solicita o destino do SVG ao concluir.
'@ | Set-Content -LiteralPath (Join-Path $Pacote 'LEIA-ME.txt') -Encoding UTF8
$Relatorio = & $PythonProjeto -B (Join-Path $PSScriptRoot 'verificar_distribuicao.py') $Pacote
if ($LASTEXITCODE -ne 0) { throw 'O executavel falhou na verificacao; ZIP nao atualizado.' }
$Relatorio | Set-Content -LiteralPath (Join-Path $Build 'verificacao-distribuicao.json') -Encoding UTF8
Compress-Archive -LiteralPath $Pacote -DestinationPath (Join-Path $Dist 'SimuladorSO-windows-x64.zip') -Force
Write-Output "Distribuicao: $Pacote"
Write-Output "ZIP: $(Join-Path $Dist 'SimuladorSO-windows-x64.zip')"
