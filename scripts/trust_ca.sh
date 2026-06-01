#!/bin/bash

set -e

# Function to check if a cert is imported
check_cert() {
    local name="$1"
    local path="$2"
    if certutil -L -d sql:"$path" | grep -q "$name"; then
        echo "Certificate '$name' is present in '$path'."
    else
        echo "Certificate '$name' NOT found in '$path'."
    fi
}

certdir="$HOME/.pki/nssdb"
mitmproxy_path="$HOME/.mitmproxy"
mitmproxy_certfile="mitmproxy-ca-cert.pem"
mitmproxy_certfile_crt="mitmproxy-ca-cert.crt"
mitmproxy_certname="mitmproxy"
servers_certfile="./certs/phoebusCA.pem"
servers_certname="PHOEBUS_CA"
trust_store_path="/usr/share/ca-certificates/phoebus"

# Trust Servers CA -- NSS database
# Delete if already exists, and re-add
certutil -D -n "$servers_certname" -d sql:"$certdir" 2>/dev/null || true
certutil -A -n "$servers_certname" -t "TCu,Cu,Tu" -i "$servers_certfile" -d sql:"$certdir"

# Trust mitmproxy CA -- NSS database
certutil -D -n "$mitmproxy_certname" -d sql:"$certdir" 2>/dev/null || true
certutil -A -n "$mitmproxy_certname" -t "TCu,Cu,Tu" -i "$mitmproxy_path/$mitmproxy_certfile" -d sql:"$certdir"

# Trust mitmproxy CA -- System trust store
# https://askubuntu.com/questions/73287/how-do-i-install-a-root-certificate/94861#94861
sudo mkdir -p "$trust_store_path"
openssl x509 -in "$mitmproxy_path/$mitmproxy_certfile" -inform PEM -out "$mitmproxy_path/$mitmproxy_certfile_crt"
sudo cp "$mitmproxy_path/$mitmproxy_certfile_crt" "$trust_store_path/$mitmproxy_certfile_crt"
sudo update-ca-certificates

# Check that CAs are imported/trusted
# certutil -d sql:$HOME/.pki/nssdb -L
check_cert "$servers_certname" "$certdir"
check_cert "$mitmproxy_certname" "$certdir"

# Update trust stores immediately
modutil -force -dbdir sql:"$certdir" -list
