# ─────────────────────────────────────────────────────────────────────────────
# deploy.ps1  –  Publica o app DATAPREV 2026 no Azure App Service (v2)
#
# USO:
#   .\deploy.ps1                         (usa valores padrão abaixo)
#   .\deploy.ps1 -AppName meu-app -RG meu-rg
#
# PRÉ-REQUISITOS:
#   1. Azure CLI instalado: https://docs.microsoft.com/cli/azure/install-azure-cli
#   2. Logado: az login
#   3. Subscription correta: az account set --subscription "Nome ou ID"
# ─────────────────────────────────────────────────────────────────────────────

param(
    [string]$AppName = "dataprev26",    # nome do App Service
    [string]$RG      = "dataprev26-rg"  # resource group
)

if (-not $AppName) { Write-Error "AppName não informado."; exit 1 }
if (-not $RG)      { Write-Error "Resource Group não informado."; exit 1 }

$AppDir  = "$PSScriptRoot"
$ZipPath = "$env:TEMP\dataprev-app-deploy.zip"

Write-Host ""
Write-Host "  App Service : $AppName"
Write-Host "  Grupo       : $RG"
Write-Host "  Origem      : $AppDir"
Write-Host ""

# ── Compactar ─────────────────────────────────────────────────────────────────

Write-Host "→ Compactando arquivos..."

if (Test-Path $ZipPath) { Remove-Item $ZipPath -Force }

# Coleta arquivos raiz (.py, .txt) e subdiretórios templates/ e static/
$rootFiles = Get-ChildItem -Path $AppDir -File | Where-Object {
    $_.Extension -in @(".py", ".txt") -and $_.Name -notlike "__*"
}

$templateFiles = Get-ChildItem -Path "$AppDir\templates" -File -Recurse -ErrorAction SilentlyContinue
$staticFiles   = Get-ChildItem -Path "$AppDir\static"    -File -Recurse -ErrorAction SilentlyContinue

# Cria o zip manualmente para preservar estrutura de subdiretórios
Add-Type -AssemblyName System.IO.Compression.FileSystem
$zip = [System.IO.Compression.ZipFile]::Open($ZipPath, 'Create')

function Add-ToZip($zip, $file, $entryName) {
    [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile($zip, $file.FullName, $entryName, 'Optimal') | Out-Null
}

foreach ($f in $rootFiles)    { Add-ToZip $zip $f $f.Name }
foreach ($f in $templateFiles){ Add-ToZip $zip $f "templates/$($f.Name)" }
foreach ($f in $staticFiles)  { Add-ToZip $zip $f "static/$($f.Name)" }

$zip.Dispose()

Write-Host "   → $ZipPath criado ($([Math]::Round((Get-Item $ZipPath).Length / 1KB, 1)) KB)"

# ── Deploy ────────────────────────────────────────────────────────────────────

Write-Host "→ Fazendo deploy no Azure..."

az webapp deploy `
    --resource-group $RG `
    --name $AppName `
    --src-path $ZipPath `
    --type zip `
    --async false

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deploy falhou (exit code $LASTEXITCODE)"
    Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue
    exit $LASTEXITCODE
}

Remove-Item $ZipPath -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "✓ Deploy concluído!"
Write-Host "  URL: https://$AppName.azurewebsites.net"
Write-Host ""