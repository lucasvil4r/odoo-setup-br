@echo off
rem Cria na area de trabalho os atalhos "ERP" e "PDV", que abrem o Odoo numa
rem janela propria (Edge em modo app): icone, barra de tarefas e nada de barra
rem de endereco. Continua sendo o Odoo do servidor; o navegador comum segue
rem funcionando normalmente para quem preferir.
rem
rem Uso:  atalhos-windows.bat [servidor] [porta] [banco] [id_do_pdv]
rem   ex: atalhos-windows.bat 192.168.0.10 8069 odoo-br_oficina 1
rem
rem Sem argumentos aponta para localhost:8069. O banco so e necessario quando o
rem servidor tem mais de um (o db_filter aceita o banco do projeto e derivados).
rem
rem Texto sem acentos de proposito: o cmd le o .bat na pagina de codigo do
rem console, e acento vira lixo na tela.
rem Os echo finais usam !VAR! (expansao atrasada): com %VAR%, o "&" da URL do
rem PDV seria lido como separador de comandos.
setlocal EnableExtensions EnableDelayedExpansion

set "SERVIDOR=%~1"
if "%SERVIDOR%"=="" set "SERVIDOR=localhost"
set "PORTA=%~2"
if "%PORTA%"=="" set "PORTA=8069"
set "BANCO=%~3"
set "PDV_ID=%~4"
if "%PDV_ID%"=="" set "PDV_ID=1"

set "BASE=http://%SERVIDOR%:%PORTA%"

rem Com banco, entra pelo /web/login?db=...: e a rota que troca o banco da
rem sessao. O redirect leva o PDV direto ao caixa depois do login.
if "%BANCO%"=="" (
  set "URL_ERP=%BASE%/odoo"
  set "URL_PDV=%BASE%/pos/ui?config_id=%PDV_ID%"
) else (
  set "URL_ERP=%BASE%/web/login?db=%BANCO%"
  set "URL_PDV=%BASE%/web/login?db=%BANCO%&redirect=/pos/ui?config_id=%PDV_ID%"
)

set "EDGE=%ProgramFiles(x86)%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" set "EDGE=%ProgramFiles%\Microsoft\Edge\Application\msedge.exe"
if not exist "%EDGE%" (
  echo Microsoft Edge nao encontrado nesta maquina.
  exit /b 1
)

set "PASTA=%LOCALAPPDATA%\OdooApp"
if not exist "%PASTA%" mkdir "%PASTA%"
set "ICONE=%PASTA%\odoo.ico"

rem O PDV roda num perfil proprio do Edge: --kiosk-printing (imprime direto na
rem impressora padrao, sem a janela de impressao) so vale quando o processo do
rem navegador nasce com ela. No perfil comum, um Edge ja aberto ignoraria a flag.
set "PERFIL_PDV=%PASTA%\perfil-pdv"

rem As URLs vao para o PowerShell por variavel de ambiente, nao por argumento:
rem o "&" da query string quebraria a linha de comando do cmd.
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$ErrorActionPreference = 'Stop';" ^
  "$ico = $env:ICONE;" ^
  "try { Invoke-WebRequest -UseBasicParsing -Uri ($env:BASE + '/web/static/img/favicon.ico') -OutFile $ico }" ^
  "catch { Write-Host 'Aviso: servidor fora do ar, atalhos ficam com o icone do Edge.'; $ico = $env:EDGE + ',0' };" ^
  "$q = [char]34;" ^
  "$desk = [Environment]::GetFolderPath('Desktop');" ^
  "$sh = New-Object -ComObject WScript.Shell;" ^
  "function Atalho($nome, $args_) {" ^
  "  $lnk = $sh.CreateShortcut((Join-Path $desk ($nome + '.lnk')));" ^
  "  $lnk.TargetPath = $env:EDGE; $lnk.Arguments = $args_;" ^
  "  $lnk.IconLocation = $ico; $lnk.Description = 'Odoo - ' + $nome; $lnk.Save() };" ^
  "Atalho 'ERP' ('--app=' + $q + $env:URL_ERP + $q);" ^
  "Atalho 'PDV' ('--app=' + $q + $env:URL_PDV + $q + ' --kiosk-printing --no-first-run --user-data-dir=' + $q + $env:PERFIL_PDV + $q)"
if errorlevel 1 (
  echo Falha ao criar os atalhos.
  exit /b 1
)

echo.
echo Atalhos criados na area de trabalho:
echo   ERP  !URL_ERP!
echo   PDV  !URL_PDV!
echo.
echo O PDV imprime direto na impressora PADRAO do Windows.
endlocal
