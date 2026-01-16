#!/bin/bash
# Generate self-signed TLS certificates for MQTT Broker
# Run this script once to create the certificates

CERT_DIR="./certs"
mkdir -p "$CERT_DIR"

echo "Generating TLS certificates for Mosquitto MQTT Broker..."

# Generate CA private key
openssl genrsa -out "$CERT_DIR/ca.key" 2048

# Generate CA certificate
openssl req -new -x509 -days 365 -key "$CERT_DIR/ca.key" \
  -out "$CERT_DIR/ca.crt" \
  -subj "/CN=mosquitto-ca/O=CloudSecurity/C=US"

# Generate server private key
openssl genrsa -out "$CERT_DIR/server.key" 2048

# Generate server certificate signing request
openssl req -new -key "$CERT_DIR/server.key" \
  -out "$CERT_DIR/server.csr" \
  -subj "/CN=mosquitto/O=CloudSecurity/C=US"

# Sign server certificate with CA
openssl x509 -req -in "$CERT_DIR/server.csr" \
  -CA "$CERT_DIR/ca.crt" -CAkey "$CERT_DIR/ca.key" \
  -CAcreateserial -out "$CERT_DIR/server.crt" \
  -days 365 -sha256

# Set proper permissions
chmod 644 "$CERT_DIR/ca.crt"
chmod 644 "$CERT_DIR/server.crt"
chmod 600 "$CERT_DIR/server.key"

echo "✓ Certificates generated successfully in $CERT_DIR/"
echo "  - ca.crt (CA certificate - for clients)"
echo "  - server.crt (Server certificate)"
echo "  - server.key (Server private key)"
