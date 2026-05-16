param(
    [string]$ServiceName = 'EcommerceAgentFramework',
    [string]$PythonExe = 'python',
    [string]$ProjectRoot = 'D:\develop_python\system\ecommerce-agent-framework',
    [string]$Host = '0.0.0.0',
    [int]$Port = 8000
)

try {
    $pythonPath = (Get-Command $PythonExe -ErrorAction Stop).Source
} catch {
    Write-Error "找不到 Python 可执行文件 '$PythonExe'。请指定有效的 Python 路径。"
    exit 1
}

$workingDir = Resolve-Path $ProjectRoot
if (-not (Test-Path $workingDir)) {
    Write-Error "项目根目录不存在：$ProjectRoot"
    exit 1
}

$command = "`"$pythonPath`" -m uvicorn app.main:app --host $Host --port $Port"
$binPath = "cmd.exe /c $command"

Write-Host "Creating Windows service '$ServiceName'..."
sc.exe create $ServiceName binPath= "$binPath" start= auto DisplayName= "E-commerce Agent Framework" | Out-Null
sc.exe description $ServiceName "Run the E-commerce Agent Framework FastAPI backend as a Windows service." | Out-Null

Write-Host "Service '$ServiceName' created. 使用 'Start-Service $ServiceName' 启动服务。"
Write-Host "如果需要卸载，可执行 scripts\uninstall_windows_service.ps1。"
