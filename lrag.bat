@echo off
REM lrag — Local RAG CLI (Windows)
setlocal enabledelayedexpansion

set "LRAG_DIR=%~dp0"
if "%LRAG_API_URL%"=="" (set "LRAG_API_URL=http://localhost:8000")

set "cmd=%~1"
if "%cmd%"=="" set "cmd=help"

if "%cmd%"=="up" (
    echo Starting local-rag-starter...
    cd /d "%LRAG_DIR%"
    docker compose up -d
    echo Waiting for services...
    timeout /t 5 /nobreak >nul
    echo Ready! API at http://localhost:8000, UI at http://localhost:3000
    goto :eof
)

if "%cmd%"=="down" (
    cd /d "%LRAG_DIR%"
    docker compose down
    goto :eof
)

if "%cmd%"=="status" (
    cd /d "%LRAG_DIR%"
    docker compose ps
    goto :eof
)

if "%cmd%"=="add" (
    set "path=%~2"
    if "!path!"=="" set "path=."
    echo Ingesting: !path!
    curl -s -X POST "%LRAG_API_URL%/ingest/path" -F "path=!path!"
    goto :eof
)

if "%cmd%"=="ask" (
    set "question=%*"
    set "question=!question:ask =!"
    if "!question!"=="" (
        echo Usage: lrag ask ^<question^>
        exit /b 1
    )
    curl -s -X POST "%LRAG_API_URL%/ask" -H "Content-Type: application/json" -d "{\"question\": \"!question!\", \"top_k\": 5}"
    goto :eof
)

if "%cmd%"=="list" (
    curl -s "%LRAG_API_URL%/documents"
    goto :eof
)

if "%cmd%"=="remove" (
    curl -s -X DELETE "%LRAG_API_URL%/documents/%~2"
    goto :eof
)

if "%cmd%"=="logs" (
    cd /d "%LRAG_DIR%"
    docker compose logs --tail=50 -f
    goto :eof
)

echo local-rag-starter -- One-command local RAG
echo.
echo Usage:
echo   lrag up              Start all services
echo   lrag down            Stop all services
echo   lrag status          Show service status
echo   lrag add ^<path^>      Ingest a file or directory
echo   lrag ask ^<question^>  Ask a question
echo   lrag list            List ingested documents
echo   lrag remove ^<name^>   Remove a document
echo   lrag logs            Tail service logs
