param(
    [string]$ImageName = 'ecommerce-agent-framework',
    [string]$Tag = 'latest',
    [int]$Port = 8000
)

Write-Host "Running Docker image $ImageName:$Tag on port $Port"

docker run --rm -p $Port:8000 --name ecommerce-agent-framework "$ImageName:$Tag"
