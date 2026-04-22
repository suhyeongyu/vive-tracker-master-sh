# Prevent character encoding issues
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

#$port = 7400
$port = 13758
$udpClient = $null

# Define a variable to track the loop status
$running = $true

# Register an event to catch Ctrl+C specifically
[console]::TreatControlCAsInput = $false

try {
    $endpoint = New-Object System.Net.IPEndPoint([System.Net.IPAddress]::Any, $port)
    $udpClient = New-Object System.Net.Sockets.UdpClient($port)

    Write-Host "`n[Success] Waiting for packets on UDP port $port... (Press Ctrl+C to stop)" -ForegroundColor Cyan

    while ($running) {
        # Check if there is data waiting in the buffer
        if ($udpClient.Available -gt 0) {
            $content = $udpClient.Receive([ref]$endpoint)
            $message = [System.Text.Encoding]::UTF8.GetString($content)
            Write-Host "[$($endpoint.Address):$($endpoint.Port)] : $message" -ForegroundColor Yellow
        }
        else {
            # Sleep for a tiny bit (100ms) so the CPU doesn't hit 100%
            # This 'gap' is when PowerShell checks for the Ctrl+C signal
            Start-Sleep -Milliseconds 100
        }
    }
}
catch {
    Write-Host "`n[Error] Could not open port or an error occurred." -ForegroundColor Red
    Write-Host "Details: $($_.Exception.Message)" -ForegroundColor Gray
}
finally {
    if ($udpClient -ne $null) {
        $udpClient.Close()
        Write-Host "Socket has been closed." -ForegroundColor Green
    }
}