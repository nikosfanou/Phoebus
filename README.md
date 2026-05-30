# Phoebus
A generic differential testing framework for uncovering security and functional bugs in web browsers.

## Prerequisities

* Python (tested with versions 3.8 and 3.10)
* Docker
* Apache

## Installation

Run `./scripts/setup.sh`

## How to run

Run `./scripts/run.sh --config {CONFIG_PATH}`


## Installation Details

### Python 3.8

* `sudo apt update`
* `sudo apt install python3.8 python3.8-venv python3.8-dev`
* `curl https://bootstrap.pypa.io/get-pip.py -o get-pip.py`
* `sudo python3.8 get-pip.py`

### Docker

* <https://docs.docker.com/engine/install/ubuntu/>
* Also see `install_docker.sh`

### Apache

* <https://ubuntu.com/tutorials/install-and-configure-apache>
* Installed by `setup.sh`

### WebKitGTK

* TODO: Add gold installation

## Troubleshooting

1. Apache has a default limit of 5 restarts per 10 seconds (StartLimitIntervalSec=10s and StartLimitBurst=5). That will create problems when running the tests as we are changing the apache configs and restart the servers repeatedly. Follow these steps:
   1. `sudo nano /lib/systemd/system/apache2.service` or `sudo nano /etc/systemd/system/apache2.service`
   2. Look for a section called `[Service]`. In this section, change (or add if not exist) the lines to `StartLimitIntervalSec=1s` and `StartLimitBurst=5000`. These settings define the time interval and the number of allowed restart attempts within that interval.
   3. `sudo systemctl daemon-reload`
   4. `sudo systemctl restart apache2`
2. If you cannot import the Certificate Authority into the browsers, check if the CA certificate is owned by root (that happens if you run `python3 env-setup.py --generate` with sudo). If it is, follow these steps:
   * Go to the generated `certs` folder which contains the certificates and keys for each domain and the CA.
   * Run `sudo chown {your username}:{your username} phoebusCA.pem` so you can import it in your browsers. Run `whoami` to find your username.
