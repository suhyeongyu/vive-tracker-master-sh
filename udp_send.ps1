# Set the output encoding of the current session to UTF-8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# Specify the recipient's IP address and port
#$remoteIp = "172.30.1.122"
$remoteIp = "172.30.1.98"
#$port = 7400
$port = 13758

$udpClient = New-Object System.Net.Sockets.UdpClient

try {
    # Connect to the remote host
    $udpClient.Connect($remoteIp, $port)

    # Convert the message string to bytes
    $message = [System.Text.Encoding]::ASCII.GetBytes("Hello DDS from Windows")

    # Send the packet
    $sentBytes = $udpClient.Send($message, $message.Length)

    if ($sentBytes -gt 0) {
        Write-Host "Packet sent successfully to $remoteIp`:$port." -ForegroundColor Green
        Write-Host "Please verify the reception on the receiver side using a packet capture tool (e.g., Wireshark) or 'nc -lu $port'." -ForegroundColor Cyan
    }
}
catch {
    Write-Host "An error occurred while sending the packet: $($_.Exception.Message)" -ForegroundColor Red
}
finally {
    # Ensure the client is closed
    $udpClient.Close()
}