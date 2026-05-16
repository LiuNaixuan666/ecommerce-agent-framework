param(
    [string]$ImageName = 'ecommerce-agent-framework',
    [string]$Tag = 'latest'
)

$root = Resolve-Path "$PSScriptRoot/.."
Write-Host "Building Docker image $ImageName:$Tag from $root"

docker build -t "$ImageName:$Tag" -f "$root/Dockerfile" "$root"
