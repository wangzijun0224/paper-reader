# setup_vault.ps1 — 初始化 Obsidian Vault 目录结构
# 运行: powershell -ExecutionPolicy Bypass -File setup_vault.ps1

$projectRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $projectRoot "config\user-config.json"
$config = Get-Content -Raw -Encoding UTF8 $configPath | ConvertFrom-Json
$vault = $config.paths.obsidian_vault
$domains = @($config.domains)
$dailyFolder = $config.paths.daily_papers_folder
$paperFolder = $config.paths.paper_notes_folder
$quickFolder = $config.paths.quick_notes_folder
$surveyFolder = $config.paths.surveys_folder
$conceptFolder = $config.paths.concepts_folder
$zoteroFolder = $config.paths.zotero_folder
$systemFolder = $config.paths.system_folder

$dirs = @(
    "$vault\$dailyFolder\journal-digest",
    "$vault\$quickFolder",
    "$vault\$surveyFolder",
    "$vault\$conceptFolder\0-待分类",
    "$vault\50_我的笔记",
    "$vault\$systemFolder\索引",
    "$vault\$systemFolder\知识图谱",
    "$vault\模板"
)

foreach ($domain in $domains) {
    $dirs += "$vault\$paperFolder\$domain"
    $dirs += "$vault\$surveyFolder\$domain"
    $dirs += "$vault\$zoteroFolder\$domain"
}

foreach ($dir in $dirs) {
    New-Item -ItemType Directory -Force -Path $dir | Out-Null
}
Write-Host "目录创建完成"

# 复制模板文件
$templateSrc = Join-Path $projectRoot "templates"
Get-ChildItem $templateSrc -Filter "*.md" | ForEach-Object {
    Copy-Item -Path $_.FullName -Destination "$vault\模板\$($_.Name)" -Force
}
Write-Host "模板文件已复制"

# 初始化知识图谱
$graphPath = $config.paths.graph_data
if (-not (Test-Path $graphPath)) {
    $initGraph = @{
        nodes = @()
        edges = @()
        surveys = @{}
        last_updated = (Get-Date -Format "yyyy-MM-ddTHH:mm:ss")
    } | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText($graphPath, $initGraph, [System.Text.Encoding]::UTF8)
    Write-Host "知识图谱初始化完成"
}

# 初始化每日推荐历史去重记录
$historyPath = "$vault\$dailyFolder\.history.json"
if (-not (Test-Path $historyPath)) {
    '{"papers": [], "last_30_days": []}' | Out-File -FilePath $historyPath -Encoding utf8
}

Write-Host ""
Write-Host "=== Vault 初始化完成 ==="
Write-Host "路径: $vault"
Write-Host "下一步: 安装 dailypaper-skills 到 ~/.claude/skills/"
Write-Host "       将 boiler-research-system/skills/ 下各目录复制到 ~/.claude/skills/"
