# OpsGuard - create Secrets Manager secrets (run once per AWS account)
# Usage: edit the JSON files below, then run this script in PowerShell.

$Region = "ap-northeast-2"

$OpenAiJson = @"
{"OPENAI_API_KEY":"PASTE_YOUR_OPENAI_KEY_HERE"}
"@

$SlackJson = @"
{"SLACK_BOT_TOKEN":"xoxb-PASTE_HERE","SLACK_WEBHOOK_URL":"https://hooks.slack.com/services/PASTE_HERE"}
"@

$Tmp = Join-Path $env:TEMP "opsguard-secrets"
New-Item -ItemType Directory -Force -Path $Tmp | Out-Null

$OpenAiFile = Join-Path $Tmp "opsguard-openai.json"
$SlackFile = Join-Path $Tmp "opsguard-slack.json"

$OpenAiJson | Out-File -FilePath $OpenAiFile -Encoding utf8NoBOM
$SlackJson | Out-File -FilePath $SlackFile -Encoding utf8NoBOM

Write-Host "Creating opsguard/openai ..."
aws secretsmanager create-secret --name opsguard/openai --secret-string file://$OpenAiFile --region $Region 2>$null
if ($LASTEXITCODE -ne 0) {
    aws secretsmanager put-secret-value --secret-id opsguard/openai --secret-string file://$OpenAiFile --region $Region
}

Write-Host "Creating opsguard/slack ..."
aws secretsmanager create-secret --name opsguard/slack --secret-string file://$SlackFile --region $Region 2>$null
if ($LASTEXITCODE -ne 0) {
    aws secretsmanager put-secret-value --secret-id opsguard/slack --secret-string file://$SlackFile --region $Region
}

Remove-Item $Tmp -Recurse -Force
Write-Host "Done. Verify with: aws secretsmanager get-secret-value --secret-id opsguard/openai --region $Region"
