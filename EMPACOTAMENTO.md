# Empacotamento Windows — experimento, não entrega final

## Decisão

Usar primeiro **PyInstaller `--onedir --windowed`**: uma pasta com executável,
interpretador Python e bibliotecas Qt incluídos, sem pedir instalação de Python
no destino. **Copiar a pasta inteira**, nunca somente o `.exe`.

| Caminho | Avaliação para este projeto |
| --- | --- |
| PyInstaller onedir | Escolhido e executado; não exigiu compilador nem instalação global. Facilita investigar DLLs/recursos faltantes. |
| PyInstaller onefile | Opção posterior; extrai componentes ao iniciar. Validar primeiro onedir; não foi construído neste experimento. |
| pyside6-deploy / Nuitka | Alternativa recomendada pela documentação Qt; pyside6-deploy envolve o compilador Nuitka. Exige cadeia de compilação C no ambiente de build, não no destino. Não instalado/testado aqui. |

## Resultado real — 31/10/2026

- Uma tentativa de build, concluída com código 0 em aproximadamente 131 segundos.
- Python **3.11.9 x64**, PySide6 **6.12.0**, PyInstaller **6.22.3**,
  hooks-contrib **2026.9**, host Windows 11 x64 (build 26200).
- Ferramenta instalada somente em `.venv-windows` com `uv pip`; `.venv` Linux e
  `requirements.txt` preservados. PyInstaller é dependência de desenvolvimento.
- Pasta autossuficiente gerada: **207 arquivos, 117.467.210 bytes (~112 MiB)**.
  Confirmados `python311.dll` e `PySide6/plugins/platforms/qwindows.dll` no bundle.
- Arquivo interno PYZ contém `engine`, `models`, `parser`; não contém `exporter`
  nem módulos de testes. Não foram copiados diretórios de venv/testes.
- A GUI empacotada é o **protótipo QtWidgets atual, ainda não aprovado**.
  Foi construído antes da migração para Matplotlib: não inclui o novo Gantt nem
  a exportação atual. Precisa ser reconstruído com `requirements.txt` atualizado;
  não representa o simulador final consolidado.

**Executável local:**

```text
C:/Users/pedro/AppData/Local/hermes/cache/scratch/empacotamento-simulador/dist/SimuladorSO/SimuladorSO.exe
```

**Evidências no mesmo scratch:** `build.log`, `SimuladorSO.spec`,
`smoke_windows.py`, `smoke-result.json` e `work/SimuladorSO/warn-SimuladorSO.txt`.
O scratch é descartável e pode ser limpo automaticamente; não é local de release.

### Execução verificada

O `.exe` foi iniciado diretamente, com diretório corrente fora do repositório,
`PATH` restrito a Windows/System32 e variáveis Python/Qt de descoberta removidas:

1. Sem argumentos: PID 22700, janela visível e responsiva
   `Simulador de escalonamento • Projeto A`, encerramento normal com código 0.
2. Com caminho absoluto para `exemplos/configuracao.txt`: PID 26912,
   mesma janela visível e responsiva, encerramento normal com código 0.

A verificação usou enumeração WinAPI por PID e resposta a WM_NULL; WM_CLOSE foi
enviado somente às janelas dos processos criados. Isso prova abertura local,
não auditoria visual, correção dos resultados da simulação ou uso completo dos
controles. O host possui Python; **não foi testado em máquina limpa sem Python**.

### Revalidação independente: falha intermitente ao encerrar

Na repetição pelo assistente principal, ambos os casos abriram janelas visíveis e
responsivas. O caso com configuração externa, porém, encerrou uma vez com código
**3221226505 (`0xC0000409`)**, em vez de zero, após WM_CLOSE. O resultado dessa
falha foi preservado em `smoke-parent-falha.json` no mesmo scratch.

Uma repetição imediata da mesma sonda encerrou os dois casos com código zero.
Logo, há diferença real entre as execuções, e **o build não está validado como
estável**. A causa ainda não foi isolada; não foi aplicado um ajuste especulativo
na aplicação ou nas bibliotecas. O `smoke-result.json` contém a execução mais
recente e não deve ser usado para apagar a evidência da falha anterior.

O experimento confirma geração e abertura local de um bundle, não uma entrega
pronta para a apresentação. Investigar esse encerramento e testar em Windows
limpo permanecem obrigatórios antes de distribuir a versão final.

## Reprodução (bash no Windows)

Substituir `<repo>` e `<scratch>` por caminhos Windows com barras `/`.
Pré-requisito: `.venv-windows` com Python 3.11 x64 e PySide6 6.12.0.

```bash
cd '<repo>'
uv pip install --python .venv-windows/Scripts/python.exe 'pyinstaller==6.22.3' 'pyinstaller-hooks-contrib==2026.9'
.venv-windows/Scripts/python.exe -m PyInstaller \
  --noconfirm --clean --onedir --windowed --name SimuladorSO \
  --distpath '<scratch>/dist' --workpath '<scratch>/work' \
  --specpath '<scratch>' gui.py > '<scratch>/build.log' 2>&1
'<scratch>/dist/SimuladorSO/SimuladorSO.exe'
'<scratch>/dist/SimuladorSO/SimuladorSO.exe' '<repo>/exemplos/configuracao.txt'
```

Criar `<scratch>` antes do redirecionamento. Para repetir a sonda local nesta
máquina: `.venv-windows/Scripts/python.exe '<scratch>/smoke_windows.py'`.
A sonda registra os resultados no JSON e contém o caminho local do repositório;
adequá-lo em outro PC. `--clean` também utiliza/limpa o cache padrão do PyInstaller
em `%LOCALAPPDATA%/pyinstaller`; dist/work/spec/log ficam no scratch indicado.

## Limites e próximo passo

- Este artefato é **Windows x64**; não é pacote Linux/macOS/ARM nem instalador.
- DLLs Qt/Python estão incluídas, mas disponibilidade de runtimes do Windows,
  plugins, permissões, antivírus/SmartScreen e comportamento gráfico exigem
  teste em VM/PC limpo. Não há assinatura de código nem garantia universal.
- `exemplos/configuracao.txt` é entrada **externa**, não foi embutida. Decidir
  distribuição de exemplos/ícones/outros recursos quando a GUI for aprovada;
  não presumir que o diretório corrente seja o repositório.
- Avisos do analisador incluem módulos opcionais POSIX/Jython (`pwd`, `grp`,
  `fcntl`, `org.python` etc.); não impediram os dois testes locais. Não equivalem
  a falha de DLL, tampouco substituem validação funcional.
- Após aprovar a GUI e integrar funcionalidades finais: refazer build, executar
  regressão funcional (incluindo exportação), copiar pasta para VM Windows x64
  sem Python/Qt/ferramentas e validar abertura, carga, simulação e exportação.
  Só então preparar distribuição versionada; onefile permanece opcional.

## Fontes primárias consultadas

- PyInstaller: https://pyinstaller.org/en/stable/operating-mode.html
- PyInstaller/Qt: https://pyinstaller.org/en/v6.22.3/hooks-config.html
- Qt, implantação: https://doc.qt.io/qtforpython-6/deployment/index.html
- Qt, pyside6-deploy: https://doc.qt.io/qtforpython-6/deployment/deployment-pyside6-deploy.html
- Nuitka, compilador e standalone: https://nuitka.net/doc/user-manual.pdf

A extração direta de páginas falhou (backend sem extração/HTTP 403);
a consulta foi recuperada por busca indexada nos domínios oficiais. Não foi
executado pyside6-deploy/Nuitka. Nenhum código da aplicação foi alterado por este
experimento; apenas este documento foi criado no repositório.
