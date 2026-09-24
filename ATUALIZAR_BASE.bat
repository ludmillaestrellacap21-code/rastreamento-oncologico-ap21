@'
@echo off
chcp 65001 > nul
title Atualização da Base - Rastreamento Oncológico AP 2.1
cd /d "%~dp0"

echo ============================================================
echo     RASTREAMENTO ONCOLOGICO - AP 2.1
echo     ATUALIZACAO DA BASE POPULACIONAL
echo ============================================================
echo.
echo Verificando arquivo FICHA A...
echo.

if not exist "entrada\vitacare\*FICHA_A*.csv" (
    echo ERRO: Nenhum arquivo FICHA_A foi encontrado.
    echo.
    echo Coloque o CSV do VitaCare na pasta:
    echo entrada\vitacare
    echo.
    pause
    exit /b 1
)

echo Arquivo encontrado.
echo.
echo ATENCAO:
echo Esta rotina ira processar a FICHA A e atualizar
echo a base do Rastreamento Oncologico no Supabase.
echo.
choice /C SN /M "Deseja continuar"

if errorlevel 2 (
    echo.
    echo Atualizacao cancelada.
    pause
    exit /b 0
)

echo.
echo ============================================================
echo Iniciando atualizacao...
echo Nao feche esta janela.
echo ============================================================
echo.

py scripts_v2\atualizar_v2.py

if errorlevel 1 (
    echo.
    echo ============================================================
    echo ERRO NA ATUALIZACAO
    echo A base nao foi concluida corretamente.
    echo ============================================================
    echo.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo ATUALIZACAO CONCLUIDA COM SUCESSO
echo ============================================================
echo.
echo A rotina de processamento e sincronizacao foi finalizada.
echo Voce ja pode conferir o painel online.
echo.
pause
'@ | Set-Content -Encoding UTF8 ATUALIZAR_BASE.bat