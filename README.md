# Phoebus

Phoebus is a generic differential testing framework for uncovering security and functional bugs in web browsers.

## Prerequisites

Phoebus has been tested on **Ubuntu 22.04** with the following dependencies:

* Python 3.10
* Docker
* Apache HTTP Server

## Installation

To install Phoebus and its dependencies, run:

```bash
./scripts/setup.sh
```

## Running Phoebus

Start Phoebus using:

```bash
./scripts/run.sh --config <CONFIG_PATH>
```

Replace `<CONFIG_PATH>` with the path to your configuration file.

---

## Installing WebKitGTK

**TODO:** Add WebKitGTK installation instructions.

## Downloading and Installing browsers

**TODO:** Add install_browsers.sh and downloader.py commands

## Running example **TODO**

* init.sh {Use case name}
* create config
* create templates
* expand to tests
* optionally create selenium script
* run
* report analysis
