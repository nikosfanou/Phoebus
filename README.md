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

## Downloading Browsers and WebDrivers

To download the latest available version of a browser together with its matching WebDriver, run:

```bash
python3 downloader.py -C
```

In the example above, `-C` corresponds to Chrome. Similar flags are available for other supported browsers (e.g., `-F` for Firefox).

To download a specific browser version and its matching WebDriver, specify the desired version:

```bash
python3 downloader.py -C 135.0.7049.84
```

The example above downloads Chrome version `135.0.7049.84` together with the corresponding ChromeDriver.

## Installing Browsers

To install a downloaded browser version, run:

```bash
./scripts/install_browsers.sh -C 135.0.7049.84
```

The example above installs Chrome version `135.0.7049.84`. As with the downloader, `-C` corresponds to Chrome, while other browser-specific flags are available for other supported browsers.

> **Note:** Browser and WebDriver binaries are automatically extracted and configured by Phoebus during test execution if they have already been downloaded. However, the desired browser and WebDriver versions must be downloaded by the user before running tests.

## Running Phoebus

The following example demonstrates how to create and execute a test case for the `content-security-policy/img-src` use case.

### 1. Initialize a Test Case

Create the directory structure for a new test case:

```bash
./scripts/init.sh <TEST_CASE_NAME>
```

Replace `<TEST_CASE_NAME>` with a descriptive name for your use case.

For this example, we will use:

```bash
./scripts/init.sh content-security-policy/img-src
```

### 2. Create a Configuration File

Create a configuration file under the `configs/` directory.

For reference, see:

```text
configs/example-csp-img-src.json
```

> **Note:** The value passed as `<TEST_CASE_NAME>` during initialization must match the value of the `use_case` field in the configuration file.

### 3. Create Templates and Generate Tests

Add test templates under:

```text
use-cases/content-security-policy/img-src/templates
```

For reference, see:

```text
use-cases/content-security-policy/img-src/templates/test-img.php
```

Phoebus uses these templates to generate concrete test cases by expanding the placeholders defined in the configuration file.

Generate the tests by running:

```bash
python3 testGenerator.py --config configs/example-csp-img-src.json
```

The generated tests will be placed in:

```text
use-cases/content-security-policy/img-src/tests
```

For reference, see the generated test:

```text
use-cases/content-security-policy/img-src/tests/test-img.php
```

Comparing the template and generated test files is a useful way to understand how placeholders are expanded.

### 4. (Optional) Create a Selenium Automation Script

If the test case requires page interactions, result collection, or custom automation logic, create a Selenium script under:

```text
use-cases/content-security-policy/img-src/user-scripts
```

For reference, see:

```text
use-cases/content-security-policy/img-src/user-scripts/main.py
```

These scripts are executed during testing and can be used to automate browser interactions and collect results.

### 5. Execute the Test Case

Run the test case using:

```bash
./scripts/run.sh --config configs/example-csp-img-src.json
```

Execution results and traces will be stored in:

```text
db/central.db
```

### 6. Analyze the Results

Generate JSON and HTML reports using:

```bash
python3 analyzer.py --experiments 1 --report-name csp-img-src
```

The generated reports can then be used to identify behavioral differences across browsers and investigate potential security or functional issues.
