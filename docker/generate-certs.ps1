# PowerShell script to generate TLS certificates for MQTT Broker
# Run this script once to create the certificates

$CERT_DIR = ".\certs"
if (-not (Test-Path $CERT_DIR)) {
    New-Item -ItemType Directory -Path $CERT_DIR | Out-Null
}

Write-Host "Generating TLS certificates for Mosquitto MQTT Broker..." -ForegroundColor Cyan

# Check if OpenSSL is available
if (-not (Get-Command openssl -ErrorAction SilentlyContinue)) {
    Write-Host "ERROR: OpenSSL is not installed or not in PATH" -ForegroundColor Red
    Write-Host "Install OpenSSL from: https://slproweb.com/products/Win32OpenSSL.html" -ForegroundColor Yellow
    exit 1
}

# Generate CA private key
openssl genrsa -out "$CERT_DIR\ca.key" 2048

# Generate CA certificate
openssl req -new -x509 -days 365 -key "$CERT_DIR\ca.key" `
  -out "$CERT_DIR\ca.crt" `
  -subj "/CN=mosquitto-ca/O=CloudSecurity/C=US"

# Generate server private key
openssl genrsa -out "$CERT_DIR\server.key" 2048

# Generate server certificate signing request
openssl req -new -key "$CERT_DIR\server.key" `
  -out "$CERT_DIR\server.csr" `
  -subj "/CN=mosquitto/O=CloudSecurity/C=US"

# Sign server certificate with CA
openssl x509 -req -in "$CERT_DIR\server.csr" `
  -CA "$CERT_DIR\ca.crt" -CAkey "$CERT_DIR\ca.key" `
  -CAcreateserial -out "$CERT_DIR\server.crt" `
  -days 365 -sha256

Write-Host "✓ Certificates generated successfully in $CERT_DIR/" -ForegroundColor Green
Write-Host "  - ca.crt (CA certificate - for clients)" -ForegroundColor Green
Write-Host "  - server.crt (Server certificate)" -ForegroundColor Green
Write-Host "  - server.key (Server private key)" -ForegroundColor Green
