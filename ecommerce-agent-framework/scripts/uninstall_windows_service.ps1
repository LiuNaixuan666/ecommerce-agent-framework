param(
    [string]$ServiceName = 'EcommerceAgentFramework'
)

Write-Host "Stopping service '$ServiceName'..."
try {
    Stop-Service -Name $ServiceName -Force -ErrorAction Stop
} catch {
    Write-Warning "无法停止服务，可能服务未运行：$_"
}

Write-Host "Deleting service '$ServiceName'..."
sc.exe delete $ServiceName | Out-Null
Write-Host "Service '$ServiceName' 已删除。"
