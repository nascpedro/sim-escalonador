# Gera uma pasta Windows autossuficiente e um ZIP. Não instala dependências.
$ErrorActionPreference = 'Stop'
$Raiz = Split-Path $PSScriptRoot -Parent
$PythonProjeto = Join-Path $Raiz '.venv-windows\Scripts\python.exe'
$Dist = Join-Path $Raiz 'dist'
$Build = Join-Path $Raiz 'build'

# O PATH de desenvolvimento pode conter outra icuuc.dll (ex.: Poppler).
# O Qt usa a ICU do Windows; restringir a busca evita empacotar uma incompatível.
$PathAnterior = $env:PATH
try {
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $PythonProjeto -m PyInstaller --noconfirm --clean --onedir --windowed --name SimuladorSO `
        --hidden-import matplotlib.backends.backend_svg `
        --add-data "$Raiz\ui\janela_principal.ui;ui" `
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
Abra exemplos/configuracao.txt pelo botao Abrir configuracao.
Avance, retroceda e selecione uma tarefa para inspecionar ou editar.
O botao Executar ate o fim conclui dez ocorrencias de cada tarefa.
O SVG final e salvo ao lado da configuracao, sem sobrescrever arquivos existentes.
Use Exportar SVG para escolher outro destino ou exportar um estado intermediario.

Linha de comando, sem janela:
SimuladorSO.exe --exportar exemplos/configuracao.txt resultado.svg

Distribuicao Windows x64. Nao e necessario instalar Python ou bibliotecas.
O pacote ainda precisa de homologacao em uma maquina Windows limpa.
Limitacoes: inclusao/remocao de tarefas durante a simulacao e sugestoes de
valores padrao para todas as caracteristicas ainda nao estao implementadas.
'@ | Set-Content -LiteralPath (Join-Path $Pacote 'LEIA-ME.txt') -Encoding UTF8
$Relatorio = & $PythonProjeto -B (Join-Path $PSScriptRoot 'verificar_distribuicao.py') $Pacote
if ($LASTEXITCODE -ne 0) { throw 'O executavel falhou na verificacao; ZIP nao atualizado.' }
$Relatorio | Set-Content -LiteralPath (Join-Path $Build 'verificacao-distribuicao.json') -Encoding UTF8
Compress-Archive -LiteralPath $Pacote -DestinationPath (Join-Path $Dist 'SimuladorSO-windows-x64.zip') -Force
Write-Output "Distribuicao: $Pacote"
Write-Output "ZIP: $(Join-Path $Dist 'SimuladorSO-windows-x64.zip')"
