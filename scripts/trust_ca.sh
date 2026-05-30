#!/bin/bash

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
mitmproxy_certfile="~/.mitmproxy/mitmproxy-ca-cert.pem"
mitmproxy_certname="mitmproxy"
servers_certfile="./certs/phoebusCA.pem"
servers_certname="PHOEBUS_CA"

# Trust Servers CA
certutil -A -n "${servers_certname}" -t "TCu,Cu,Tu" -i ${servers_certfile} -d sql:${certdir}

# Trust mitmproxy CA
# NOTE: Check this in case you face mitmproxy SSL issues: https://askubuntu.com/questions/73287/how-do-i-install-a-root-certificate/94861#94861
certutil -A -n "${mitmproxy_certname}" -t "TCu,Cu,Tu" -i ${mitmproxy_certfile} -d sql:${certdir}

# Check that CAs are imported/trusted
# certutil -d sql:$HOME/.pki/nssdb -L
check_cert "$servers_certname" "$certdir"
check_cert "$mitmproxy_certname" "$certdir"

# Update trust stores immediately
modutil -force -dbdir sql:${certdir} -list