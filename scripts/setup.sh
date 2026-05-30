# Install Apache2
sudo apt update
sudo apt install apache2

# Install PHP for apache
sudo apt install php libapache2-mod-php

# Install Dependencies

# Install cloc for counting lines of code on TestGenerator
sudo apt install cloc

# Install needed python packages
pip3 install -r requirements.txt

# to be able to modify localhost apache files without sudo:
sudo usermod -a -G www-data $(whoami)
sudo chown -R :www-data /etc/apache2
sudo chmod -R g+w /etc/apache2
sudo mkdir /var/www/localhost
sudo chown -R :www-data /var/www/localhost
sudo chmod -R g+w /var/www/localhost
sudo mkdir /usr/lib/apache2/api
sudo chown -R :www-data /usr/lib/apache2/api
sudo chmod -R g+rwx /usr/lib/apache2/api
sudo chown -R :www-data /var/lib/apache2
sudo chmod -R g+w /var/lib/apache2
sudo chown -R :www-data /var/log/apache2
sudo chmod -R g+w /var/log/apache2

# to be able to restart apache2 server on localhost without password
cat <<EOF | sudo tee /etc/sudoers.d/apacherestart
$(whoami) ALL=NOPASSWD: $(whereis systemctl | awk '{print $2}') restart apache2.service 
EOF

# to be able to run docker commands without sudo
sudo usermod -a -G docker $(whoami)

# Create certificates folder
mkdir -p ./certs

# Generate Certification Authority (CA)
python3 env-setup.py --create_ca

# Before running trust_ca.sh, we need to run mitmproxy once to generate its ca if not already generated
timeout 1s mitmdump --set console_eventlog_verbosity=error --quiet

# Add CA on browsers' trusted CA
# NOTE: You may need to install the browsers first.
sudo apt-get install libnss3-tools
./scripts/trust_ca.sh

# Create custom apache image that has php installed and configured
sudo docker build -t custom-httpd-image -f ./dockerfiles/apache/Dockerfile .
echo "Setup completed!"
