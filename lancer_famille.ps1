$ErrorActionPreference = "Stop"

$DossierProjet = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python = Join-Path $DossierProjet ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Environnement Python introuvable. Crée d'abord .venv et installe requirements.txt."
}

$CartesActives = [System.Net.NetworkInformation.NetworkInterface]::GetAllNetworkInterfaces() |
    Where-Object {
        $_.OperationalStatus -eq [System.Net.NetworkInformation.OperationalStatus]::Up -and
        $_.NetworkInterfaceType -in @(
            [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211,
            [System.Net.NetworkInformation.NetworkInterfaceType]::Ethernet
        )
    } |
    Sort-Object @{
        Expression = {
            if ($_.NetworkInterfaceType -eq [System.Net.NetworkInformation.NetworkInterfaceType]::Wireless80211) { 0 }
            else { 1 }
        }
    }

$AdresseIPv4 = $null
foreach ($Carte in $CartesActives) {
    $AdressePasserelleIPv4 = $Carte.GetIPProperties().GatewayAddresses |
        Where-Object { $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork } |
        Select-Object -First 1
    if (-not $AdressePasserelleIPv4) { continue }

    $Adresse = $Carte.GetIPProperties().UnicastAddresses |
        Where-Object {
            $_.Address.AddressFamily -eq [System.Net.Sockets.AddressFamily]::InterNetwork -and
            -not $_.Address.IsLoopback -and
            $_.Address.ToString() -notlike "169.254.*"
        } |
        Select-Object -First 1
    if ($Adresse) {
        $AdresseIPv4 = $Adresse.Address.ToString()
        break
    }
}

if (-not $AdresseIPv4) {
    throw "Aucune adresse IPv4 Wi-Fi/Ethernet trouvée. Vérifie la connexion au réseau puis réessaie."
}

try {
    $null = Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3
    Write-Host "Ollama est joignable sur cet ordinateur." -ForegroundColor Green
}
catch {
    Write-Warning "Ollama ne répond pas sur le port 11434. Démarre Ollama avant de poser des questions."
}

Write-Host ""
Write-Host "Adresse à ouvrir sur les appareils du même Wi-Fi :" -ForegroundColor Cyan
Write-Host "http://${AdresseIPv4}:8000/?v=tyson-ai-v2" -ForegroundColor White
Write-Host "Les PDF importés seront enregistrés sur cet ordinateur et partagés par le chatbot."
Write-Host "Garde cette fenêtre ouverte pendant l'essai. Pour arrêter le serveur : Ctrl+C."
Write-Host ""

Set-Location -LiteralPath $DossierProjet
& $Python -m uvicorn main:app --host $AdresseIPv4 --port 8000
