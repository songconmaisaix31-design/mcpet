$ErrorActionPreference = 'Stop'
Push-Location (Split-Path -Parent $PSScriptRoot)
try {
    $result = & bl speech synthesize --text '鲸鲸看了看，小钱包只剩四块三毛七啦。先别慌，我来陪你盯着。' --model cosyvoice-v3-flash --voice longhua_v3 --format wav --sample-rate 24000 --rate 1.08 --out 'public/audio/worry-voice-source.wav' --output json
    if ($LASTEXITCODE -ne 0) { throw 'Aliyun 配音合成失败；原始失败请保留，不使用其他语音替代。' }
    # 不输出服务返回的临时签名下载链接。
    Write-Host 'Aliyun 配音已保存，请执行 npm run prepare 重新测量和混音。'
} finally { Pop-Location }
