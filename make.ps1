# Equivalente ao make: transforma os fontes em um executavel Windows x64.
# Sem opcoes, usa um ambiente virtual temporario; nao instala pacotes globais.
param(
    [string]$Python = 'python',
    [switch]$UsarAmbienteAtual
)

$ErrorActionPreference = 'Stop'
$RaizEnvio = $PSScriptRoot
$BaseTemporaria = [IO.Path]::GetFullPath([IO.Path]::GetTempPath()).TrimEnd('\')
$AreaBuild = Join-Path $BaseTemporaria ('simulador-build-' + [guid]::NewGuid().ToString('N'))
$PathAnterior = $env:PATH
New-Item -ItemType Directory -Path $AreaBuild | Out-Null

try {
    # Resolve o interpretador antes de restringir o PATH para a coleta de DLLs.
    $PythonBase = (& $Python -B -c "import sys; print(sys.executable)").Trim()
    if ($LASTEXITCODE -ne 0) { throw 'Interpretador Python indisponivel.' }
    $PythonBuild = $PythonBase
    if (-not $UsarAmbienteAtual) {
        # Reprodutibilidade: as dependencias ficam fixadas aqui, sem outro arquivo.
        & $PythonBase -m venv (Join-Path $AreaBuild 'venv')
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel criar o ambiente Python.' }
        $PythonBuild = Join-Path $AreaBuild 'venv\Scripts\python.exe'
        & $PythonBuild -m pip install 'customtkinter==6.0.0' 'drawsvg==2.4.2' `
            'PyInstaller==6.22.3' 'pyinstaller-hooks-contrib==2026.9'
        if ($LASTEXITCODE -ne 0) { throw 'Nao foi possivel instalar as dependencias.' }
    }

    # Evita coletar DLLs de outras ferramentas instaladas no computador.
    $env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
    & $PythonBuild -B -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name SimuladorSO --collect-data customtkinter `
        --add-data "$(Join-Path $RaizEnvio 'ociosa.xbm');." `
        --copy-metadata customtkinter --copy-metadata drawsvg `
        --copy-metadata darkdetect --copy-metadata packaging `
        --distpath (Join-Path $AreaBuild 'dist') `
        --workpath (Join-Path $AreaBuild 'work') --specpath $AreaBuild `
        (Join-Path $RaizEnvio 'gui.py')
    if ($LASTEXITCODE -ne 0) { throw 'Falha ao gerar o executavel.' }

    # Somente o resultado e copiado para a pasta da entrega: um arquivo .exe.
    Copy-Item -LiteralPath (Join-Path $AreaBuild 'dist\SimuladorSO.exe') `
        -Destination (Join-Path $RaizEnvio 'SimuladorSO.exe') -Force
    Write-Output "Executavel gerado: $(Join-Path $RaizEnvio 'SimuladorSO.exe')"
} finally {
    $env:PATH = $PathAnterior
    # A limpeza fica restrita a pasta temporaria unica criada por este script.
    $AlvoLimpeza = (Resolve-Path -LiteralPath $AreaBuild).Path
    if ($AlvoLimpeza -ne [IO.Path]::GetFullPath($AreaBuild) -or
        -not $AlvoLimpeza.StartsWith($BaseTemporaria + '\', [StringComparison]::OrdinalIgnoreCase)) {
        throw 'Pasta temporaria inesperada; limpeza cancelada.'
    }
    Remove-Item -LiteralPath $AlvoLimpeza -Recurse -Force
}
