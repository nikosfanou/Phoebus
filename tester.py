from argparse import ArgumentParser
import asyncio
import itertools
import multiprocessing
import os
import socket
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import logging
import importlib.util
from copy import deepcopy
import tempfile
from pyvirtualdisplay import Display

from utils.MiTM_proxy import MiTMProxy
from utils.PerformanceDegradationDetector import PerformanceDegradationDetector
from utils.SQLiteHandler import SQLiteHandler
from utils.utility import *
from utils.ResilientDriver import wrap_driver
from utils.ApacheConfigurations import *
from utils.HashGenerator import HashGenerator
from utils.HashContentExtractor import JSContentExtractor, CSSContentExtractor
from utils.clear_browser_data_util import *

from selenium import webdriver
# Chrome, Opera, Brave
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
# Firefox, Tor
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.firefox.options import Options as FirefoxOptions
# Edge
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.edge.service import Service as EdgeService
# WebKit
from selenium.webdriver.webkitgtk.options import Options as WebKitGTKOptions
from selenium.webdriver.webkitgtk.service import Service as WebKitGTKService
from selenium.webdriver.common.proxy import Proxy, ProxyType

WrappedChrome = wrap_driver(webdriver.Chrome)
WrappedEdge = wrap_driver(webdriver.Edge)
WrappedFirefox = wrap_driver(webdriver.Firefox)
WrappedWebKitGTK = wrap_driver(webdriver.WebKitGTK)

class Constants:
    ENABLE_PERFORMANCE_DEGRADATION_OBSERVER = True
    VIRTUAL_DISPLAY_ENABLED = False
    VIRTUAL_DISPLAY_VISIBLE = False
    DISPLAY_FOR_VIRTUAL_DISPLAY = None
    AUTOMATED_BROWSER_INSTALLATION = True
    CENTRAL_DB = "central.db"
    LOGGER = None
    MAX_BOOT_ATTEMPTS = 3
    ENDPOINTS_PATH = "./endpoint-scripts"
    ENV_SETUP_CONFIG = "./configs/env-setup.json"
    MODE_SUPPORTED_VALUES = ["regular", "replay"]
    MECHANISMS_CONFIG = "./configs/mechanisms.jsonc"
    BROWSERS_INFO_CONFIG = "./configs/browsers-info.json"
    DEFAULT_FILES_PATH = "./default-files/tests"
    APACHE_FILES_HOST_PATH = "./apache-files"
    LOCALHOST_HOST_PATH = "/var/www/localhost"
    APACHE_CONFIG_PATH = "./apache-configs"
    LOCALHOST_CONFIG_PATH = LOCALHOST_PREPENDS_HOST_PATH = "/etc/apache2"
    APACHE_PREPENDS_HOST_PATH = "./apache-prepends"
    LOCALHOST_HTTPD_CUSTOM_PATH = "/etc/apache2/localhost_custom.conf"
    APACHE_HTTPD_CUSTOM_PATH = "./apache-configs/%s/httpd_custom.conf"
    APACHE_ENDPOINTS_PATH = "/usr/local/apache2/api"
    LOCALHOST_ENDPOINTS_PATH = "/usr/lib/apache2/api"
    SUPPORTED_BROWSERS = [
        "Brave",
        "Chrome",
        "Edge",
        "Firefox",
        "Opera",
        "Tor",
        "WebKit"
    ]
    OWN_URL_PARAMS = ["browser", "version", "results_id", "deployment_id"]
    ENV_PHP_FILE = 'env.php'
    RUNTIME_PHP_FILE = 'runtime.php'

# Get the command line arguments
def get_args():
    parser = ArgumentParser()
    # both modes
    parser.add_argument("-mo", "--mode", dest="mode", default = 'regular', type=str, help = "Supported values: 1. regular (default value) & 2. replay. Tester, in regular mode, runs new experiments based on a configuration file. In replay mode however, it re-runs a previously ran experiment to verify the correctness of its results.")
    parser.add_argument("-db", "--database", default = Constants.CENTRAL_DB, dest = "database", type=str, help = f"The database file where we store the execution results. Default value is {Constants.CENTRAL_DB}")
    # regular mode
    parser.add_argument("-e", "--example", dest = "example", type=str, help = "The value that will replace the {EXAMPLE} placeholder.")
    parser.add_argument("-ce", "--crossexample", dest = "crossexample", type=str, help = "The value that will replace the {CROSSEXAMPLE} placeholder.")
    parser.add_argument("-mc", "--mainConfig", dest = "mainConfig", type=str,  help = "The main configuration file. Contains the Mechanisms to test and their options.")
    parser.add_argument("-c", "--config", default = Constants.ENV_SETUP_CONFIG, dest = "config", type=str, help = f"The environment setup configuration file. Default value is {Constants.ENV_SETUP_CONFIG}")
    # replay mode
    parser.add_argument("-de", "--deployments", dest = "deployments", nargs='+', type=int, help = f"The exact deployment IDs to re-run. Only for replay mode.")
    parser.add_argument("-exp", "--experiment", dest="experiment", type=int, help = "The experiment to re-run. Only for replay mode.")
    args = parser.parse_args()
    # validation
    if args.mode not in Constants.MODE_SUPPORTED_VALUES:
        parser.error(f"Mode supported values are: {Constants.MODE_SUPPORTED_VALUES}")
    if args.mode == 'regular' and (args.mainConfig is None or args.example is None or args.crossexample is None):
        parser.error("In regular mode,\n\t-m/--mainConfig\n\t-e/--example\n\t-ce/--crossexample\narguments are required!")
    if args.mode == 'replay' and args.experiment is None:
        parser.error("In replay mode, -exp/--experiment argument is required!")
    if args.mode == 'replay' and args.experiment is not None and args.experiment <= 0:
        parser.error("The argument -exp/--experiment must be a positive integer!")
    return args

def create_environment_info(configuration, example, crossexample):
    environment_info = {}
    environment_info['containers_dict'] = {
        "{EXAMPLE}" : example,
        "{SUB_EXAMPLE}" : f"sub.{example}",
        "{SUB2_EXAMPLE}" : f"sub2.{example}",
        "{CROSSEXAMPLE}" : crossexample,
        "{SUB_CROSSEXAMPLE}" : f"sub.{crossexample}",
    }
    environment_info['ports_dict'] = {
        "{PORT}" : "8090",
        "{SSL_PORT}" : "8091"
    }
    environment_info['ws_dict'] = {
        "host" : configuration['docker']['websocket-server']['ip'],
        "port" : str(configuration['docker']['websocket-server']['port']),
        "ssl_port" : str(configuration['docker']['websocket-server']['ssl_port'])
    }
    environment_info['localhost_ws_dict'] = {
        "host" : "localhost",
        "port" : str(configuration['docker']['websocket-server']['port']),
        "ssl_port" : str(configuration['docker']['websocket-server']['ssl_port'])
    }
    environment_info['ssl_dict'] = {
        "ca" : os.path.join(configuration['ssl']['target-path']['docker'], configuration['ssl']['CA'] + '.pem'),
        "crt" : os.path.join(configuration['ssl']['target-path']['docker'], "server.crt"),
        "key" : os.path.join(configuration['ssl']['target-path']['docker'], "server.key")
    }
    environment_info['localhost_ssl_dict'] = {
        "ca" : os.path.join(configuration['ssl']['target-path']['localhost'], configuration['ssl']['CA'] + '.pem'),
        "crt" : os.path.join(configuration['ssl']['target-path']['localhost'], "server.crt"),
        "key" : os.path.join(configuration['ssl']['target-path']['localhost'], "server.key")
    }
    environment_info['ip_dict'] = {
        "{EXAMPLE_IP}" : configuration['docker']['containers'][environment_info['containers_dict']['{EXAMPLE}']],
        "{SUB_EXAMPLE_IP}" : configuration['docker']['containers'][environment_info['containers_dict']['{SUB_EXAMPLE}']],
        "{SUB2_EXAMPLE_IP}" : configuration['docker']['containers'][environment_info['containers_dict']['{SUB2_EXAMPLE}']],
        "{CROSSEXAMPLE_IP}" : configuration['docker']['containers'][environment_info['containers_dict']['{CROSSEXAMPLE}']],
        "{SUB_CROSSEXAMPLE_IP}" : configuration['docker']['containers'][environment_info['containers_dict']['{SUB_CROSSEXAMPLE}']]
    }
    environment_info['paths_dict'] = {
        "localhost" : configuration['localhost']["path-to-serve-paths"],
        "other" : configuration['docker']["path-to-serve-paths"]
    }
    environment_info['ips'] = list(environment_info['ip_dict'].values())
    environment_info['ips'].append('127.0.0.1')
    environment_info['ip_to_domain_dict'] = {value: environment_info['containers_dict'][match_ip_domain(ip_placeholder=key)] for key, value in environment_info['ip_dict'].items()}
    environment_info['ip_to_domain_dict']['127.0.0.1'] = 'localhost'
    environment_info['domain_to_ip_dict'] = {value: key for key, value in environment_info['ip_to_domain_dict'].items()}
    environment_info['servers'] = list(environment_info['ip_to_domain_dict'].values())
    environment_info['domains'] = [server + '.com' if server != 'localhost' else server for server in environment_info['servers']]
    environment_info['ports'] = ["80", "443", environment_info['ports_dict']["{PORT}"], environment_info['ports_dict']["{SSL_PORT}"]]
    environment_info['endpoints'] = get_endpoints()
    return environment_info

def match_ip_domain(ip_placeholder):
    matches = {
        "{EXAMPLE_IP}" : "{EXAMPLE}",
        "{SUB_EXAMPLE_IP}" : "{SUB_EXAMPLE}",
        "{SUB2_EXAMPLE_IP}" : "{SUB2_EXAMPLE}",
        "{CROSSEXAMPLE_IP}" : "{CROSSEXAMPLE}",
        "{SUB_CROSSEXAMPLE_IP}" : "{SUB_CROSSEXAMPLE}"
    }
    return matches[ip_placeholder]

def get_endpoints():
    folder = Constants.ENDPOINTS_PATH
    return list_files(folder=folder, file_extension=".php")

# NOTE: This method checks fields to have the correct format, and in some cases replaces non-existing values in the config, with the default values.
def check_use_case(use_case_info, environment_info):
    ### threads
    threads = use_case_info.get("threads", 1)
    if type(threads) is not int or threads < 1:
        print('[ERROR] threads field must be a positive integer!')
        return False
    use_case_info['threads'] = threads
    ### custom_headers
    custom_headers = use_case_info.get("custom_headers", [])
    use_case_info['custom_headers'] = custom_headers
    if type(custom_headers) is not list:
        print('[ERROR] custom_headers field must be a list of lists, where each inner list contains a dict (headers, set_on) and optionally a list of int (status_codes)!')
        return False
    for custom_headers_list in custom_headers:
        if type(custom_headers_list) is not list:
            print('[ERROR] custom_headers field must be a list of lists, where each inner list contains a dict (headers, set_on) and optionally a list of int (status_codes)!')
            return False
        for index, custom_header_obj in enumerate(custom_headers_list.copy()):
            if type(custom_header_obj) is dict:
                #### headers -- list of str
                headers = custom_header_obj.get('headers', None)
                if type(headers) is not list:
                    print('[ERROR] The field `headers` inside the `custom_headers` field must be a list of str, representing the list of header(s) to be set!')
                    return False
                else:
                    for header in headers:
                        if type(header) is not str:
                            print('[ERROR] The field `headers` inside the `custom_headers` field must be a list of str, representing the list of header(s) to be set!')
                            return False
                #### set_on -- str or list of str
                set_on = custom_header_obj.get('set_on', None)
                if type(set_on) is not list:
                    if set_on is None:
                        custom_header_obj['set_on'] = ["{EXAMPLE}"]
                    elif type(set_on) is str:
                        custom_header_obj['set_on'] = [set_on]
                    else:
                        print('[ERROR] The field `set_on` inside the `custom_headers` field must be an str or a list of str, representing the domain(s) where the header(s) should be set!')
                        return False
                else:
                    for set_domain in set_on:
                        if type(set_domain) is not str:
                            print('[ERROR] The field `set_on` inside the `custom_headers` field must be an str or a list of str, representing the domain(s) where the header(s) should be set!')
                            return False
            elif type(custom_header_obj) is list:
                #### status_codes
                for status_code in custom_header_obj:
                    if type(status_code) is not int:
                        print('[ERROR] The status codes inside the `custom_headers` field must be a list of int!')
                        return False
            elif type(custom_header_obj) is int:
                #### 1 status code
                # if int, add it in a list
                custom_headers_list.pop(index)
                custom_headers_list.insert(index, [custom_header_obj])
            else:
                print('[ERROR] custom_headers field must be a list of lists, where each inner list contains a dict (headers, set_on) and optionally a list of int (status_codes)!')
                return False


    ### sticky_headers
    sticky_headers = use_case_info.get("sticky_headers", [])
    use_case_info['sticky_headers'] = sticky_headers
    if type(sticky_headers) is not list:
        print('[ERROR] sticky_headers field must be a list of dict!')
        return False
    for sticky_header_obj in sticky_headers:
        if type(sticky_header_obj) is not dict:
            print('[ERROR] sticky_headers field must be a list of dict!')
            return False
        #### headers -- list of str
        headers = sticky_header_obj.get('headers', None)
        if type(headers) is not list:
            print('[ERROR] The field `headers` inside the `sticky_headers` field must be a list of str, representing the list of header(s) to be set!')
            return False
        else:
            for header in headers:
                if type(header) is not str:
                    print('[ERROR] The field `headers` inside the `sticky_headers` field must be a list of str, representing the list of header(s) to be set!')
                    return False
        #### set_on -- str or list of str
        set_on = sticky_header_obj.get('set_on', None)
        if type(set_on) is not list:
            if set_on is None:
                sticky_header_obj['set_on'] = ["{EXAMPLE}"]
            elif type(set_on) is str:
                sticky_header_obj['set_on'] = [set_on]
            else:
                print('[ERROR] The field `set_on` inside the `sticky_headers` field must be an str or a list of str, representing the domain(s) where the header(s) should be set!')
                return False
        else:
            for set_domain in set_on:
                if type(set_domain) is not str:
                    print('[ERROR] The field `set_on` inside the `sticky_headers` field must be an str or a list of str, representing the domain(s) where the header(s) should be set!')
                    return False

    ### run_on
    run_on = use_case_info.get("run_on", None)
    if run_on is not None:
        if type(run_on) is not list:
            if type(run_on) is str:
                run_on = [run_on]
            else:
                print('[ERROR] run_on field must be a string or a list of str!')
                return False
        supported_domains = list(environment_info['containers_dict'].keys()) + ['localhost']
        for domain in run_on.copy():
            if domain not in supported_domains:
                run_on.remove(domain)
        if not run_on:
            print('[ERROR] The field `run_on` was not assigned valid values.')
            return False
    else:
        run_on = ['{EXAMPLE}'] # by default
    use_case_info['run_on'] = run_on

    ### mechanisms
    mechanisms = use_case_info.get("mechanisms", [])
    if type(mechanisms) is dict:
        mechanisms = [mechanisms]
    elif type(mechanisms) is not list:
        print('[ERROR] mechanisms field must be a list of dict!')
        return False
    for mechanism_entry in mechanisms:
        if type(mechanism_entry) is not dict:
            print('[ERROR] mechanisms field must be a list of dict!')
            return False
        #### mechanism
        if mechanism_entry.get('mechanism', None) is None:
            print('[ERROR] The field `mechanism` is missing. One of the mechanism descriptions (in the mechanisms field) does not contain a mechanism name!')
            return False
        #### set_on
        set_on = mechanism_entry.get("set_on", None)
        if set_on is not None:
            if type(set_on) is not list:
                if type(set_on) is str:
                    set_on = [set_on]
                else:
                    print('[ERROR] set_on field must be a string or a list of str!')
                    return False
            supported_domains = list(environment_info['containers_dict'].keys()) + ['localhost']
            for domain in set_on.copy():
                if domain not in supported_domains:
                    set_on.remove(domain)
            if not set_on:
                print('[ERROR] The field `set_on` was not assigned valid values.')
                return False
        else:
            set_on = ['{EXAMPLE}']
        mechanism_entry['set_on'] = set_on
        #### group
        group = mechanism_entry.get("group", None)
        if group is None:
            mechanism_entry['group'] = 1
        elif type(group) is not int or group < 1:
            print('[WARN] The field `group` was not assigned valid values and is now assigned to 1')
            mechanism_entry['group'] = 1
    use_case_info["mechanisms"] = mechanisms

    ### browsers
    browsers = use_case_info.get("browsers", {})
    if type(browsers) is not dict:
        print('[ERROR] browsers field must be a dict!')
        return False
    browsers_config = read_json(file=Constants.BROWSERS_INFO_CONFIG)
    for browser_name, version in browsers.copy().items():
        if browser_name not in Constants.SUPPORTED_BROWSERS:
            print(f'[WARN] Browser {browser_name} is not supported, will skip it!')
            del browsers[browser_name]
            continue # TODO?: Change these warnings to errors and return False ?
        if browser_name.lower() not in browsers_config:
            print(f'[WARN] Browser {browser_name} is not defined in {Constants.BROWSERS_INFO_CONFIG}, will skip it!')
            del browsers[browser_name]
            continue
        if version == 'latest':
            valid_version = browsers_config[browser_name.lower()].get('latest-version', None)
            if valid_version is not None:
                browsers[browser_name] = valid_version
            else:
                print(f'[WARN] The latest version for browser {browser_name} is not defined in {Constants.BROWSERS_INFO_CONFIG}, will skip it!')
                del browsers[browser_name]
                continue
    if len(browsers.keys()) < 2:
        print('[ERROR] Less than 2 browsers were given!')
        return False
    
    ### use_case
    use_case = use_case_info.get("use_case", None)
    if not use_case:
        print('[ERROR] The field `use_case` was not given')
        return False
    if type(use_case) is not str:
        print('[ERROR] use_case field must be a string!')
        return False
    use_case_info["use_case"] = os.path.join('use-cases', use_case)

    ### options
    options = use_case_info.get("options", {})
    if type(options) is not dict:
        print('[ERROR] options field must be a dict!')
        return False
    use_case_info['options'] = options
    #### mechanism_values_db
    mechanism_values_db = options.get("mechanism_values_db", "")
    if type(mechanism_values_db) is not str:
        print('[ERROR] mechanism_values_db field must be a str!')
        return False
    #### flags
    flags = options.get('flags', {})
    if type(flags) is not dict:
        print('[ERROR] flags field must be a dict!')
        return False
    options['flags'] = flags
    #### clear_browser_data
    clear_browser_data = options.get('clear_browser_data', False)
    if type(clear_browser_data) is not bool:
        print('[ERROR] clear_browser_data field must be a bool!')
        return False
    options['clear_browser_data'] = clear_browser_data
    #### reboot_browsers
    reboot_browsers = options.get('reboot_browsers', False)
    if type(reboot_browsers) is not bool:
        print('[ERROR] reboot_browsers field must be a bool!')
        return False
    options['reboot_browsers'] = reboot_browsers
    #### disable_browser_cache
    disable_browser_cache = options.get('disable_browser_cache', False)
    if type(disable_browser_cache) is not bool:
        print('[ERROR] disable_browser_cache field must be a bool!')
        return False
    options['disable_browser_cache'] = disable_browser_cache
    #### capture_requests
    capture_requests = options.get('capture_requests', False)
    if type(capture_requests) is not bool:
        print('[ERROR] capture_requests field must be a bool!')
        return False
    options['capture_requests'] = capture_requests
    #### capture_request_headers
    capture_request_headers = options.get('capture_request_headers', [])
    if type(capture_request_headers) is not list:
        print('[ERROR] capture_request_headers field must be a list!')
        return False
    options['capture_request_headers'] = capture_request_headers
    
    ### mechanisms_combinations
    mechanisms_combinations = use_case_info.get('mechanisms_combinations', False)
    if type(mechanisms_combinations) is not bool:
        print('[ERROR] mechanisms_combinations field must be a bool!')
        return False
    use_case_info['mechanisms_combinations'] = mechanisms_combinations

    ### status_codes
    status_codes = use_case_info.get('status_codes', None)
    if status_codes is not None:
        if type(status_codes) is int:
            status_codes = [status_codes]
        elif type(status_codes) is list:
            for code in status_codes:
                if type(code) is not int:
                    print('[ERROR] A given status code was not an integer!')
                    return False
        else:
            print('[ERROR] status_codes field must be an int or a list of int!')
            return False
    else:
        status_codes = []
    use_case_info['status_codes'] = status_codes
    return True

def insert_experiment(generated_values_db, config, env_config, example, crossexample, database):
    try:
        with SQLiteHandler(database) as db:
            result, id = db.insert_experiments_table(
                db=generated_values_db,
                config=config,
                env_config=env_config,
                example=example,
                crossexample=crossexample
            )
            return result, id

    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        print(log_msg)
        return False, False

# for compatibility, and for potential future enhancements !!
def convert_browsers_dict_to_list_of_dicts(use_case_info):
    browsers_dict = use_case_info['browsers']
    threads = use_case_info['threads']
    browsers_list = []
    include_Tor = None
    for name, version in browsers_dict.items():
        if name == 'Tor':
            if threads == 1:
                include_Tor = {'name': 'Tor', 'version': version, 'thread': 0}
                continue
            else:
                raise NotImplementedError("Tor does not allow userAgent override, and thus it cannot be used in parallel execution with more than 1 threads")
        for thread in range(threads):
            browsers_list.append({'name': name, 'version': version, 'thread': thread})
    if include_Tor is not None:
        browsers_list.append(include_Tor)
    return browsers_list

def set_loggers(mode, experiment_id, date, browsers_info):
    folder_name = f"experiment{experiment_id}-{mode}-{date}"
    os.makedirs(f'./logs/{folder_name}', exist_ok=True)
    for browser_dict in browsers_info:
        browser_dict['logger'] = create_logger(f"{browser_dict['name']}{browser_dict['thread']}", os.path.join('./logs', folder_name, f"{browser_dict['name']}-{browser_dict['thread']}.log"))
    return create_logger('tester', os.path.join('./logs', folder_name, "tester.log"))

def create_logger(name, filename):
    logger = logging.getLogger(name)    
    logger.setLevel(logging.DEBUG)
    file_handler = logging.FileHandler(filename)
    file_handler.setLevel(logging.DEBUG)
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(funcName)s - %(levelname)s - %(message)s')
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger

# 1. Every PHP file (in the main and resources folders) gets the php variables about testing environment (domain names, ips etc.)!
# 2. PHP files in the main folder (except index.php) will be executed!
# 3. PHP files in resources folder will NOT be executed!
# 4. PHP files in the main or resources folder that start with _ (underscore) will not set any mechanism values! However, they will contain the mechanism values in predefined variables so that they can be used, if needed, by the user.
# 5. execute field stores the main test files to be visited by browsers.
# 6. execute_once field stores the main test files to be visited by browsers but only on the first deployment.
# 7. set field stores the php files where the mechanism values should be set.
# 8. not_set field stores the php files where the mechanism values should NOT be set.
# 9. other field stores helper files like .js .html etc.
def get_tests(tests_path):
    if not os.path.exists(path=tests_path):
        return {}
    discovered_tests = {'execute': [], 'execute_once': [], 'set': [], 'not_set': [], 'other': []}
    for root, _, files in os.walk(tests_path):
        current_dir = os.path.relpath(root, tests_path) # '.' if same path
        if current_dir == '.':
            current_dir = ''
        elif current_dir != 'resources':
            # NOTE: We only copy root and resources folders' files in the servers
            continue
        for file in files:
            full_file = os.path.join(current_dir, file)
            if file.endswith('.php'):
                # if starts with _, will not set mechanisms, status codes etc. in this file
                if file.startswith('_'):
                    discovered_tests['not_set'].append(full_file)
                else:
                    discovered_tests['set'].append(full_file)
            else:
                # store other files like .js etc.
                discovered_tests['other'].append(full_file)
        if current_dir == '':
            # the php files located in the main folder are planned to be executed
            for test in discovered_tests['set'] + discovered_tests['not_set']:
                if test == 'index.php': continue # index.php should not be executed though
                if test.endswith('.once.php'): # it should be executed only the 1st time!
                    discovered_tests['execute_once'].append(test)
                else:
                    discovered_tests['execute'].append(test)
    return discovered_tests

# copies all test files to all domains (one time at the begining)
def copy_all_files(tests_path, servers):
    src_path = os.path.join(tests_path, '*')
    for server in servers:
        dst_path = os.path.join(Constants.APACHE_FILES_HOST_PATH, server) if server!='localhost' else Constants.LOCALHOST_HOST_PATH
        subprocess.run(f'cp -r {src_path} {dst_path}', shell=True)

def get_automation_tests(path): # get selenium tests (python & js)
    if not os.path.exists(path=path):
        return [], []
    python_tests = list_files(folder=path, file_extension=".py")
    js_tests = list_files(folder=path, file_extension=".js")
    return python_tests, js_tests

def call_generator(config_content, db, json_file=None):
    # create an intermediate config for generator
    config_uid = generate_uuid()
    config_name = f"generator_config_{config_uid}.json"
    write_json(file=config_name, data=config_content)
    generator_cmd = f"python3 generator.py --database {db} --config {config_name}"
    if json_file is not None:
        generator_cmd += f" --json {json_file}"
    # call generator
    proc = subprocess.run(generator_cmd, shell=True)
    if proc.returncode != 0:
        Constants.LOGGER.critical(f"Generator returned code `{proc.returncode}`!")
        exit(1) 
    # when finished, remove the intermediate config
    subprocess.run(f"rm {config_name}", shell=True)

def install_browsers(browsers):
    install_command = './scripts/install_browsers.sh'
    for browser_dict in browsers:
        install_command += f" --{browser_dict['name']} {browser_dict['version']}"
    installation_status = subprocess.run(install_command, shell=True)
    return installation_status.returncode == 0

def start_mitm_proxies(use_case_info, allow_hosts):
    num_of_browsers = len(use_case_info['browsers'])
    available_ports = find_available_ports(num=num_of_browsers)
    count = 0
    for browser_dict in use_case_info['browsers']:
        browser_dict['proxy_port'] = available_ports[count]
        count += 1
        # use multiprocessing queue for retrieving the data from inside the processes
        browser_dict['queue'] = multiprocessing.Queue()
        browser_dict['process'] = multiprocessing.Process(target=run_proxy, args=(browser_dict['name'], browser_dict['proxy_port'], browser_dict['queue'], allow_hosts))
        browser_dict['process'].start()
    return

def find_available_ports(num, range_start=8000, range_end=9999):
    available_ports = []
    for port in range(range_start, range_end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            if s.connect_ex(("127.0.0.1", port)) != 0:
                available_ports.append(port)
                if len(available_ports) >= num:
                    break
    if len(available_ports) < num:
        Constants.LOGGER.error(f"Could not find {num} free ports in the given range ({range_start}-{range_end})")
        exit(1)
    return available_ports

def run_proxy(name, port, queue, allow_hosts):
    try:
        Constants.LOGGER.info(f'Starting proxy for {name} browser on port {port}')
        asyncio.run(start_proxy(name, port, queue, allow_hosts))
    except Exception as e:
        Constants.LOGGER.error(f"Error in {name} proxy: {e}")

async def start_proxy(name, port, queue, allow_hosts):
    # Disable http2 because browsers by default do not use it, and we want to test browsers under conditions that a regular user would experience.
    # Set allow_hosts, because we only care about the requests from our domains.
    options = {'listen_port': port, 'ssl_insecure': True, 'allow_hosts': allow_hosts, 'http2': False, 'http3': False}
    proxy = MiTMProxy(name=name, queue=queue, options=options)
    proxy.create()
    requests_addon = "CaptureRequestsAddon"
    proxy.add_addon(requests_addon)

    try:
        await proxy.run()
    except Exception as e:
        Constants.LOGGER.info(f"{name} proxy on port {port} stopped with error: {e}")
    finally:
        proxy.shutdown()

def clearBrowserData(browser_dict, flags):
    browser_name = browser_dict['name']
    logger = browser_dict['logger']
    try:
        if browser_name == 'Firefox' or browser_name == 'Tor':
            firefox_clear_browser_data(browser_dict['driver'])
        elif browser_name == 'Chrome':
            chrome_clear_browser_data(browser_dict['driver'])
        elif browser_name == 'Brave':
            brave_clear_browser_data(browser_dict['driver'])
        elif browser_name == 'Edge':
            edge_clear_browser_data(browser_dict['driver'])
        elif browser_name == 'Opera':
            opera_clear_browser_data(browser_dict['driver'])
        elif browser_name == 'WebKit':
            raise Exception("clearBrowserData method cannot be implemented for browser WebKit!")
    except Exception as e:
        logger.error(f'clearBrowserData method failed. Will close and re-open webdriver...')
        log_msg = extract_log_msg(exception=e)
        logger.exception(log_msg)
        # if clearBrowserData fails reboot the browser
        close_driver(browser_dict=browser_dict)
        reboot_start = time.time()
        living = try_to_live(max_attempts=3, browser_dict=browser_dict, flags=flags)
        if living is False:
            return False
        reboot_time = time.time() - reboot_start
        logger.info(f"Re-opening {browser_name}, Reboot Time: {reboot_time}")
    return True


def rebootBrowser(browser_dict, flags):
    browser_name = browser_dict['name']
    logger = browser_dict['logger']
    close_driver(browser_dict=browser_dict)
    # Giving 3 attempts to re-open the webdriver before exiting
    living = try_to_live(max_attempts=3, browser_dict=browser_dict, flags=flags)
    if living is False:
        logger.critical(f"Failed to reboot {browser_name}!")
    return living

def get_drivers_with_threads(use_case_info):
    threads = []
    # Boot ALL browsers in parallel
    for browser_dict in use_case_info['browsers']:
        thread = threading.Thread(target=try_to_live, args=(3, browser_dict, use_case_info['options']['flags']))
        thread.start()
        threads.append(thread)
    # Wait until all browsers are ready
    for thread in threads:
        thread.join()
    if shouldExitAll(browser_info=use_case_info['browsers']) is True:
        # try to close drivers and exit!
        clear_before_exit(use_case_info=use_case_info)
        exit(1)

def try_to_live(max_attempts, browser_dict, flags):
    counter = 0
    logger = browser_dict['logger']
    while counter < max_attempts:
        get_driver(browser_dict=browser_dict, flags=flags)
        if browser_dict.get('error', False) is False:
            logger.info(f"[Attempt {counter}] Booted {browser_dict['name']} browser successfully.")
            return True
        logger.error(f"[Attempt {counter}] Failed to boot {browser_dict['name']} browser.")
        counter += 1
    logger.critical(f"Exceeded maximum attempts to open the {browser_dict['name']} browser.")
    return False

def get_driver(browser_dict, flags):
    driver = None
    browser = browser_dict['name']
    version = browser_dict['version']
    proxy_port = browser_dict['proxy_port'] if 'proxy_port' in browser_dict else None
    archive_path = f"./archive/{browser}/{version}"
    try:
        if browser == "Firefox":
            webdriver_path = find_file(archive_path, 'geckodriver')
            executable_path = find_file(archive_path, 'firefox')
            service = FirefoxService(webdriver_path)
            options = FirefoxOptions()
            options.binary_location = executable_path
            set_flags(options=options, flags=flags, browser=browser)
            if proxy_port is not None:
                set_firefox_proxy(options=options, port=proxy_port)
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            options.set_preference("general.useragent.override", f"Mozilla/5.0 (X11; Linux x86_64; rv:{version}) Gecko/20100101 Firefox/{version} ({browser_dict['expected_ua']})")
            driver = WrappedFirefox(options=options, service=service)
        
        elif browser == "Chrome":
            webdriver_path = find_file(archive_path, 'chromedriver')
            executable_path = "/usr/bin/google-chrome"
            service = ChromeService(webdriver_path)
            options = ChromeOptions()
            options.binary_location = executable_path
            set_flags(options=options, flags=flags, browser=browser)
            if proxy_port is not None:
                set_chromium_proxy(options=options, port=proxy_port)
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{version} Safari/537.36 ({browser_dict['expected_ua']})")
            driver = WrappedChrome(options=options, service=service)
        
        elif browser == "Opera":
            webdriver_path = find_file(archive_path, 'operadriver')
            executable_path = "/usr/bin/opera"
            service = ChromeService(webdriver_path)
            options = ChromeOptions()
            options.binary_location = executable_path
            set_flags(options=options, flags=flags, browser=browser)
            options.add_experimental_option('w3c', True)
            if proxy_port is not None:
                set_chromium_proxy(options=options, port=proxy_port)
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Opera/{version} Safari/537.36 ({browser_dict['expected_ua']})")
            driver = WrappedChrome(service = service, options=options)
        
        elif browser == "Brave":
            webdriver_path = find_file(archive_path, 'chromedriver')
            executable_path = "/usr/bin/brave-browser"
            service = ChromeService(webdriver_path)
            options = ChromeOptions()
            options.binary_location = executable_path
            set_flags(options=options, flags=flags, browser=browser)
            if proxy_port is not None:
                set_chromium_proxy(options=options, port=proxy_port)
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Brave/{version} Safari/537.36 ({browser_dict['expected_ua']})")
            driver = WrappedChrome(options=options, service=service)

        elif browser == "Edge":
            webdriver_path = find_file(archive_path, 'msedgedriver')
            executable_path = "/usr/bin/microsoft-edge"
            service = EdgeService(webdriver_path)
            options = EdgeOptions()
            options.binary_location = executable_path
            set_flags(options=options, flags=flags, browser=browser)
            if proxy_port is not None:
                set_chromium_proxy(options=options, port=proxy_port)
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            options.add_argument("--disable-features=msSmartScreenProtection") # to stop it from blocking our self-signed (SSL) pages.
            options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/{version} Safari/537.36 ({browser_dict['expected_ua']})")
            driver = WrappedEdge(service=service, options=options)

        elif browser == "Tor":
            webdriver_path = find_file(archive_path, 'geckodriver')
            executable_path = find_file(archive_path, 'start-tor-browser')
            service = FirefoxService(webdriver_path)
            options = FirefoxOptions()
            options.binary_location = executable_path
            # these to import self-signed CA
            options.set_preference("security.nocertdb", False) # to trust self-signed certificate!!
            options.set_preference("security.OCSP.enabled", 0)
            # these to remove Tor network and use local dns and /etc/hosts file
            options.set_preference("network.dns.disabled", False)
            options.set_preference("network.dns.echconfig.enabled", True)
            options.set_preference("network.dns.disablePrefetch", False)
            options.set_preference("network.proxy.socks", "")
            options.set_preference("network.proxy.socks_port", 0)
            options.set_preference("network.proxy.socks_remote_dns", False)
            options.set_preference("network.proxy.type", 5)
            options.set_preference("extensions.torlauncher.start_tor", False)
            if proxy_port is not None:
                set_tor_proxy(options=options, port=proxy_port)
            set_flags(options=options, flags=flags, browser=browser) # set also user defined arguments and preferences
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                options.add_argument(f'--display={Constants.DISPLAY_FOR_VIRTUAL_DISPLAY}')
            # options.set_preference("privacy.resistFingerprinting", False) # Tor doesn't allow UA overrides anymore :/
            # options.set_preference("general.useragent.override", f"Mozilla/5.0 (X11; Linux x86_64; rv:{version}) Gecko/20100101 Tor/{version} ({browser_dict['expected_ua']})")
            driver = WrappedFirefox(options=options, service=service)
        
        elif browser == "WebKit":
            executable_path = find_file(archive_path, 'MiniBrowser')
            webdriver_path = find_file(archive_path, 'WebKitWebDriver')
            os.environ['WEBKITGTK_DRIVER_PATH'] = webdriver_path
            
            # NOTE: New clear profile each time, Selenium does not create that automatically like for the rest of the browsers, and we need clean profiles after reboots.
            tmp_data = tempfile.mkdtemp(prefix="wk_data_")
            tmp_cache = tempfile.mkdtemp(prefix="wk_cache_")
            env = os.environ.copy()
            env["XDG_DATA_HOME"] = tmp_data
            env["XDG_CACHE_HOME"] = tmp_cache
            if Constants.VIRTUAL_DISPLAY_ENABLED and Constants.DISPLAY_FOR_VIRTUAL_DISPLAY:
                env["DISPLAY"] = Constants.DISPLAY_FOR_VIRTUAL_DISPLAY

            service = WebKitGTKService(env=env, driver_path_env_key="WEBKITGTK_DRIVER_PATH")
            options = WebKitGTKOptions()
            options.accept_insecure_certs = True
            options.binary_location = executable_path
            # NOTE: The following is the only way to override the user agent in WebKitGTK. Flag --automation must be set and come first.
            options.add_argument("--automation")
            # NOTE: options.set_preference() does not exist in WebKitGTKOptions
            set_flags(options=options, flags=flags, browser=browser)
            if proxy_port is not None:
                set_webkit_proxy(options=options, port=proxy_port)
            options.add_argument(f"--user-agent=Mozilla/5.0 (X11; Ubuntu; Linux x86_64) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/60.5 Safari/605.1.15 ({browser_dict['expected_ua']})")
            driver = WrappedWebKitGTK(options=options, service=service)

        browser_dict['driver'] = driver
        browser_dict['error'] = False
    except Exception as e:
        browser_dict['logger'].critical(f"Couldn't boot {browser} browser normally.")
        log_msg = extract_log_msg(exception=e)
        browser_dict['logger'].exception(log_msg)
        browser_dict['error'] = True

def set_firefox_proxy(options, port):
    options.set_preference("network.proxy.no_proxies_on", "")
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.http", "127.0.0.1")
    options.set_preference("network.proxy.http_port", port)
    options.set_preference("network.proxy.ssl", "127.0.0.1")
    options.set_preference("network.proxy.ssl_port", port)
    options.set_preference("network.proxy.allow_hijacking_localhost", True)

def set_tor_proxy(options, port):
    # Ensure DNS resolution works outside Tor
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.http", "127.0.0.1")
    options.set_preference("network.proxy.http_port", port)
    options.set_preference("network.proxy.ssl", "127.0.0.1")
    options.set_preference("network.proxy.ssl_port", port)
    options.set_preference("network.proxy.no_proxies_on", "")
    # to capture localhost traffic
    options.set_preference("network.proxy.allow_hijacking_localhost", True)
    # to let Tor use mitmproxy
    options.set_preference("extensions.torbutton.use_nontor_proxy", True)

def set_chromium_proxy(options, port):
    options.add_argument(f'--proxy-server=http://127.0.0.1:{port}')
    # to capture localhost traffic
    options.add_argument("--proxy-bypass-list=<-loopback>")

# NOTE: WebKit seems to send localhost requests as well, without requiring to explicitly set it.
def set_webkit_proxy(options,port):
    proxy = Proxy({
        "proxyType": ProxyType.MANUAL["string"],
        "httpProxy": f"127.0.0.1:{port}",
        "sslProxy": f"127.0.0.1:{port}",
    })
    options.proxy = proxy

def set_flags(options, flags, browser):
    # set arguments - for all browsers
    for flag, browsers in flags.get('argument', {}).items():
        if browser in browsers:
            options.add_argument(flag)
    # set preferences - for firefox/tor
    preference_list = flags.get('preference', [])
    for preference_dict in preference_list:
        if browser in preference_dict.get('browsers', []):
            browser_preferences = preference_dict.get('name', [])
            if type(browser_preferences) is not list:
                browser_preferences = [browser_preferences]
            for pref in browser_preferences:
                options.set_preference(pref, preference_dict.get('value', ""))
    # set experimental options - for Chromium
    experimental_options_list = flags.get('experimental_option', [])
    for experimental_option_dict in experimental_options_list:
        if browser in experimental_option_dict.get('browsers', []):
            browser_experimental_options = experimental_option_dict.get('name', [])
            if type(browser_experimental_options) is not list:
                browser_experimental_options = [browser_experimental_options]
            for experimental_option in browser_experimental_options:
                options.add_experimental_option(experimental_option, experimental_option_dict.get('value', ""))
    # set capabilities - for all browsers
    capabilities_list = flags.get('capability', [])
    for capability_dict in capabilities_list:
        if browser in capability_dict.get('browsers', []):
            browser_capabilities = capability_dict.get('name', [])
            if type(browser_capabilities) is not list:
                browser_capabilities = [browser_capabilities]
            for capability in browser_capabilities:
                options.set_capability(capability, capability_dict.get('value', ""))

def shouldExitAll(browser_info):
    for browser_dict in browser_info:
        if shouldExit(browser_dict=browser_dict) is True:
            return True
    return False

def shouldExit(browser_dict):
    return browser_dict.get('error', False)

def clear_before_exit(use_case_info):
    close_drivers(use_case_info=use_case_info)
    stop_mitm_proxies(use_case_info=use_case_info)

def close_drivers(use_case_info):
    for browser_dict in use_case_info['browsers']:
        close_driver(browser_dict=browser_dict)

def close_driver(browser_dict):
    try:
        if browser_dict.get('driver', None):
            _close_driver(driver=browser_dict['driver'], logger=browser_dict['logger'])
            browser_dict['driver'] = None
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        browser_dict['logger'].exception(log_msg)

def _close_driver(driver, logger):
    try:
        driver.close()
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        logger.error("driver.close() failed")
        logger.error(log_msg)
    
    try:
        # Check if the browser is still running - Noticed in Brave
        _ = driver.title
        logger.info("Browser is still open, calling driver.quit()")
        driver.quit()
    except Exception as e:
        logger.info("Browser is already closed.")

def stop_mitm_proxies(use_case_info):
    for browser_dict in use_case_info['browsers']:
        stop_mitm_proxy(browser_dict=browser_dict)

def stop_mitm_proxy(browser_dict):
    if browser_dict.get('process', None) is None:
        return
    try:
        # terminate the mitmproxy processes
        browser_dict['process'].terminate()
        # wait until it has stopped before closing it
        while browser_dict['process'].is_alive():
            pass
        browser_dict['process'].close()
        browser_dict['process'] = None
        # close the queues
        browser_dict['queue'].close()
        browser_dict['queue'] = None
    except Exception as e:
        log_msg = extract_log_msg(e)
        Constants.LOGGER.exception(log_msg)

def update_experiment_metrics(id, values_generation_time, values_retrieval_time, database):
    try:
        with SQLiteHandler(database) as central_db:
            return central_db.update_experiment_metrics(id=id, values_generation_time=values_generation_time, values_retrieval_time=values_retrieval_time)
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)
        return False

def update_experiment_time(id, exec_time, database):
    central_db = None
    try:
        with SQLiteHandler(database) as central_db:
            return central_db.update_experiment_execution_time(id=id, exec_time=exec_time)
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)
        return False

def remove_files_from_servers(servers):
    for server in servers:
        if server != 'localhost':
            path = os.path.join(Constants.APACHE_FILES_HOST_PATH, server, '*')
        else:
            path = os.path.join(Constants.LOCALHOST_HOST_PATH, '*')
        subprocess.run(f"rm -r {path}", shell=True)

def process_cmd_arguments(args):
    env_config = read_json(file=args.config)
    use_cases_list = read_json(file=args.mainConfig)
    return use_cases_list, env_config, args.database, args.example, args.crossexample

def group_values(data, group_num):
    result = []
    for i in range(0, len(data), group_num):
        result.append(data[i:i + group_num])
    return result

# Group mechanism values based on `group` field.
def enforce_group_field(mechanism_values, use_case_info):
    for entry in mechanism_values:
        index = entry['index']
        values = entry['values']
        group_num = use_case_info['mechanisms'][index]['group']
        if group_num: # even if group_num == 1, we put it into a list for ease, for the algorithms that follow
            values = group_values(data=values, group_num=group_num)
            entry['values'] = values

def get_generated_mechanism_values(mechanism_values, mechanisms, should_generate_hashes, environment_info, database):
    configured_mechanisms = [mechanism_entry['mechanism'] for mechanism_entry in mechanisms]
    mechanisms_in_db = get_generated_mechanisms(database=database)
    iteration = 0 # as we run configured_mechanisms.pop(index), all mechanisms lose 1 index, so we need this variable to keep correct ordering.
    for id, mechanism_name in mechanisms_in_db:
        try:
            index = configured_mechanisms.index(mechanism_name)
            configured_mechanisms.pop(index) # required, to not get the same values for a 2nd occurence of the mechanism
            real_index = index + iteration
            iteration += 1
            # get values and their metadata
            generated_values = get_generated_values_per_mechanism(mechanism_id=id, database=database)
            generated_values = filter_values(generated_values=generated_values, should_generate_hashes=should_generate_hashes, environment_info=environment_info)
            mechanism_values.append({"index": real_index, "values": generated_values})
        except ValueError as err:
            pass

def filter_values(generated_values, should_generate_hashes, environment_info):
    filtered_values = []
    for entry in generated_values.copy():
        value, metadata_str = entry
        filtered_metadata = json.loads(metadata_str)
        filtered_value = json.loads(value)
        # replace e.g., {EXAMPLE} with example.com
        filtered_value = replace_placeholders(value=filtered_value, should_generate_hashes=should_generate_hashes, environment_info=environment_info)
        filtered_values.append([filtered_value, filtered_metadata])
        generated_values.remove(entry)
    return filtered_values

def get_generated_mechanisms(database):
    try:
        with SQLiteHandler(db_name=database) as db:
            return db.get_mechanism_ids_names()
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)
        return []

def get_generated_values_per_mechanism(mechanism_id, database):
    try:
        with SQLiteHandler(db_name=database) as db_handler:
            return db_handler.get_mechanism_values_by_mechanism_id(mechanism_id)
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)
        return []

def extract_user_methods(use_case_info):
    use_case_info['automation_test_methods'] = []
    for selenium_test in use_case_info['automation_tests']['py']:
        module_name = selenium_test.split('.')[0]
        selenium_test_path = os.path.join(use_case_info["automation_tests_path"], selenium_test)
        spec = importlib.util.spec_from_file_location(module_name, selenium_test_path)
        user_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(user_module)
        use_case_info['automation_test_methods'] += list(user_module.METHODS_TO_EXECUTE)

def extract_user_js_script(use_case_info):
    use_case_info['automation_js_scripts'] = {}
    for js_file in use_case_info['automation_tests']['js']:
        with open(js_file, 'r') as fp:
            content = fp.read()
        if content.strip():
            use_case_info['automation_js_scripts'][js_file] = content

def run_experiment(args, mechanisms_config):
    overall_start = time.time()

    # process the command line arguments
    use_cases_list, env_config, database, example, crossexample = process_cmd_arguments(args)

    # collect info about servers, containers, endpoints, ips etc.
    environment_info = create_environment_info(configuration=env_config, example=example, crossexample=crossexample)
    # some default php variables (domains, ips and ports), will be given to user to help him define his tests
    php_environment_info = {
        'example': environment_info['containers_dict']['{EXAMPLE}'] + '.com',
        'crossexample': environment_info['containers_dict']['{CROSSEXAMPLE}'] + '.com',
        'sub_example': environment_info['containers_dict']['{SUB_EXAMPLE}'] + '.com',
        'sub2_example': environment_info['containers_dict']['{SUB2_EXAMPLE}'] + '.com',
        'sub_crossexample': environment_info['containers_dict']['{SUB_CROSSEXAMPLE}'] + '.com',
        'example_ip': environment_info['ip_dict']['{EXAMPLE_IP}'],
        'crossexample_ip': environment_info['ip_dict']['{CROSSEXAMPLE_IP}'],
        'sub_example_ip': environment_info['ip_dict']['{SUB_EXAMPLE_IP}'],
        'sub2_example_ip': environment_info['ip_dict']['{SUB2_EXAMPLE_IP}'],
        'sub_crossexample_ip': environment_info['ip_dict']['{SUB_CROSSEXAMPLE_IP}'],
        'custom_port': environment_info['ports_dict']['{PORT}'],
        'custom_ssl_port': environment_info['ports_dict']['{SSL_PORT}']
    }
    # Write env.php -- We add the environmental php variables like $example in all php files and all domains, even if we won't set the mechanism values there!
    # That could assist in the test generation and give flexibility
    for server in environment_info['servers']:
        insert_variables_in_php_file(server=server, php_file=Constants.ENV_PHP_FILE, placeholders_dict=php_environment_info)

    # start regular/run mode
    for use_case_info in use_cases_list:
        # A quick check whether the supported fields have the expected data types
        is_ok = check_use_case(use_case_info, environment_info)
        if not is_ok:
            exit(1)
        
        experiment_start = time.time()
        
        # create our testing mechanism values database if not given
        formatted_datetime = get_datetime_iso_format()
        default_mech_values_db = f"testing_mechanisms_{formatted_datetime}.db"
        mech_values_db = use_case_info['options'].get("mechanism_values_db", default_mech_values_db)
        # print(f'Mechanism values database to be used for this test case: {mech_values_db}')
        
        # make entry in experiments table
        isInserted, experiment_id = insert_experiment(generated_values_db=mech_values_db, config=use_case_info, env_config=env_config, example=example, crossexample=crossexample, database=database)
        if isInserted is False:
            print("[ERROR] Couldn't create entry in `experiments` table. Exiting...")
            exit(1)

        # where the browser tests are located
        use_case_info["tests_path"] = os.path.join(use_case_info["use_case"], "tests")
        # where the Selenium automation tests are located
        use_case_info["automation_tests_path"] = os.path.join(use_case_info["use_case"], "user-scripts")
        use_case_info['automation_tests'] = {}

        # convert dict to list of dicts format, for compatibility, and because in the future we may support multiple same browsers of different versions or other Nightly/Canary versions etc.
        use_case_info['browsers'] = convert_browsers_dict_to_list_of_dicts(use_case_info)
        # Set tester.log for the module, and {browser}.log for each browser
        Constants.LOGGER = set_loggers(mode='run', experiment_id=experiment_id, date=formatted_datetime, browsers_info=use_case_info['browsers'])
        
        # this field (tests) is a dictionary containing information about which php files should be executed (once or for every deployment), which should define (or not) mechanism values, and which are just helpful resources e.g., .js files.
        use_case_info['tests'] = get_tests(tests_path=use_case_info['tests_path'])
        if not use_case_info['tests'] or not use_case_info['tests']['execute']:
            Constants.LOGGER.error(f"No tests detected in `{use_case_info['tests_path']}`! Continuing with the next use case...")
            continue

        # Copy our default helper files into servers (only once in the beginning), this contains images, scripts, media and many other resources to help the user run the tests
        copy_all_files(tests_path=Constants.DEFAULT_FILES_PATH, servers=environment_info['servers'])
        # Copy test files into servers (only once in the beginning)
        copy_all_files(tests_path=use_case_info['tests_path'], servers=environment_info['servers'])

        # get Selenium tests (1. Python, 2. JavaScript to run in driver.execute_script())
        use_case_info['automation_tests']['py'], use_case_info['automation_tests']['js'] = get_automation_tests(path=use_case_info['automation_tests_path'])
        if len(use_case_info['automation_tests']['py']) == 0 and len(use_case_info['automation_tests']['js']) == 0:
            Constants.LOGGER.warn(f"No automation tests detected in `{use_case_info['automation_tests_path']}`! Tester will just visit the test page in case the results are not retrieved through Selenium.")
        # print(f"Python Automation Test files: {use_case_info['automation_tests']['py']}")
        # print(f"JavaScript Automation Test files (for driver.execute_script()): {use_case_info['automation_tests']['js']}")
        
        # From Python test filenames find the Python test methods to run
        extract_user_methods(use_case_info=use_case_info)
        # From JavaScript test filenames, read their content, and execute it with driver.execute_script();
        extract_user_js_script(use_case_info=use_case_info)
        
        # processing run_on -- can contain only domain names, not IPs.
        use_case_info['run_on'] = [environment_info['containers_dict'][container_placeholder] if container_placeholder in environment_info['containers_dict'] else container_placeholder for container_placeholder in use_case_info['run_on']]

        # preprocessing sticky_headers
        sticky_headers = use_case_info['sticky_headers']
        for sticky_headers_dict in sticky_headers:
            # replace set_on
            sticky_headers_dict['set_on'] = [environment_info['containers_dict'][container_placeholder] if container_placeholder in environment_info['containers_dict'] else container_placeholder for container_placeholder in sticky_headers_dict['set_on']]
            # replace headers
            new_headers = []
            for header in sticky_headers_dict['headers']:
                new_header = _replace_placeholders(value=header, domains_dict=environment_info['containers_dict'], ports_dict=environment_info['ports_dict'], ip_dict=environment_info['ip_dict'])
                new_headers.append(new_header)
            sticky_headers_dict['headers'] = new_headers

        # preprocessing custom_headers
        custom_headers = use_case_info['custom_headers']
        for custom_headers_list in custom_headers:
            for custom_headers_dict in custom_headers_list:
                if type(custom_headers_dict) is dict:
                    # replace set_on
                    custom_headers_dict['set_on'] = [environment_info['containers_dict'][container_placeholder] if container_placeholder in environment_info['containers_dict'] else container_placeholder for container_placeholder in custom_headers_dict['set_on']]
                    # replace headers
                    new_headers = []
                    for header in custom_headers_dict['headers']:
                        new_header = _replace_placeholders(value=header, domains_dict=environment_info['containers_dict'], ports_dict=environment_info['ports_dict'], ip_dict=environment_info['ip_dict'])
                        new_headers.append(new_header)
                    custom_headers_dict['headers'] = new_headers

        # Find mechanism type
        for mechanism_entry in use_case_info['mechanisms']:
            mechanism = mechanism_entry['mechanism']
            # processing set_on -- can contain only domain names, not IPs.
            mechanism_entry['set_on'] = [environment_info['containers_dict'][container_placeholder] if container_placeholder in environment_info['containers_dict'] else container_placeholder for container_placeholder in mechanism_entry['set_on']]
            # Find from Constants.MECHANISMS_CONFIG if it is http header, html attribute or other mechanism!
            if mechanism in mechanisms_config['headers'].keys():
                mechanism_entry['mechanism_type'] = "http-header"
            elif mechanism in mechanisms_config['html'].keys():
                mechanism_entry['mechanism_type'] = "html-attribute"
            else:
                mechanism_entry['mechanism_type'] = "other"
        
        generator_time = 0
        # if user has given such a database (different than default) it means they have pre-built it, so no need to call generator
        if use_case_info['mechanisms'] and mech_values_db == default_mech_values_db:
            generator_start = time.time()
            # call generator to create the needed mechanism values and save in db
            call_generator(config_content=use_case_info['mechanisms'], db=mech_values_db) #json_file="tmp.json"
            generator_time = time.time() - generator_start
            Constants.LOGGER.info(f"Generator Execution Time: {generator_time}")

        retrieval_start = time.time()
        mechanism_values = []
        should_generate_hashes = {'script': False, 'style': False}
        try:
            # Retrieve mechanism values from db
            get_generated_mechanism_values(mechanism_values=mechanism_values, mechanisms=use_case_info['mechanisms'], should_generate_hashes=should_generate_hashes, environment_info=environment_info, database=mech_values_db)
        except Exception as e:
            Constants.LOGGER.critical("Could not retrieve the mechanism values from the database!")
            log_msg = extract_log_msg(exception=e)
            Constants.LOGGER.exception(log_msg)
            exit(1)
        retrieval_time = time.time() - retrieval_start
        Constants.LOGGER.info(f"Retrieval of Mechanism Values Execution Time: {retrieval_time}")

        # Install Browsers
        if Constants.AUTOMATED_BROWSER_INSTALLATION:
            installation_status = install_browsers(browsers=use_case_info['browsers'])
            if not installation_status:
                Constants.LOGGER.critical("Browsers installation failed!")
                exit(1)

        # NOTE: Before booting browsers we have to start mitmproxies
        # Start MiTM proxies
        enable_capture_requests = use_case_info['options']['capture_requests']
        if enable_capture_requests:
            allow_hosts = environment_info['domains'] + environment_info['ips']
            start_mitm_proxies(use_case_info=use_case_info, allow_hosts=allow_hosts)
        
        # Create Virtual Display
        disp = None
        if Constants.VIRTUAL_DISPLAY_ENABLED:
            disp = create_virtual_display()
        
        update_experiment_metrics(id=experiment_id, values_generation_time=generator_time, values_retrieval_time=retrieval_time, database=database)
        
        try:
            # Run tests
            run_deployments(use_case_info=use_case_info, mechanism_values=mechanism_values, should_generate_hashes=should_generate_hashes, php_environment_info=php_environment_info, environment_info=environment_info, experiment_id=experiment_id, database=database)
        except Exception as e:
            log_msg = extract_log_msg(exception=e)
            Constants.LOGGER.exception(log_msg)
        
        # Close browsers
        close_drivers(use_case_info=use_case_info)
        # Close Virtual Display
        if disp:
            close_virtual_display(disp=disp)
        # Close MiTM proxies
        if enable_capture_requests:
            stop_mitm_proxies(use_case_info=use_case_info)
        # Remove all test files from all servers
        remove_files_from_servers(servers=environment_info['servers'])

        experiment_time = time.time() - experiment_start
        update_experiment_time(id=experiment_id, exec_time=experiment_time, database=database)
        Constants.LOGGER.info(f"Experiment (#{experiment_id}) Execution Time: {experiment_time}")
    
    overall_time = time.time() - overall_start
    print("Overall Execution Time: ", overall_time)

def create_virtual_display():
    try: 
        disp = Display(visible=Constants.VIRTUAL_DISPLAY_VISIBLE)
        disp.start()
        Constants.DISPLAY_FOR_VIRTUAL_DISPLAY = os.environ['DISPLAY']
    except Exception as e:
        Constants.LOGGER.error(f"Failed to create and start Virtual Display.")
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)
    return disp

def close_virtual_display(disp):
    try: 
        disp.stop()
    except Exception as e:
        Constants.LOGGER.error(f"Failed to close Virtual Display.")
        log_msg = extract_log_msg(exception=e)
        Constants.LOGGER.exception(log_msg)

# Populate the apache configuration file
def prepare_servers(environment_info, disable_browser_cache=False):
    domain_ip_dict = environment_info['domain_to_ip_dict']
    for server in environment_info['servers']:
        if server != 'localhost':
            full_domain = server + '.com'
            websockets_dict = environment_info['ws_dict']
            default_path = environment_info['paths_dict']['other']
            ssl = environment_info['ssl_dict']
        else:
            full_domain = 'localhost'
            websockets_dict = environment_info['localhost_ws_dict']
            default_path = environment_info['paths_dict']['localhost']
            ssl = environment_info['localhost_ssl_dict']
        
        config = create_config(host=full_domain, ip=domain_ip_dict[server], ports_dict=environment_info['ports_dict'],
                    websockets_dict=websockets_dict, ssl_dict=ssl, path_to_serve_paths=default_path,
                    endpoints=environment_info['endpoints'], disable_browser_cache=disable_browser_cache)
        write_custom_config(server=server, content=config)
        restart_container(container=server) if server != 'localhost' else restart_localhost()

# Restart server for changes to take effect
def restart_container(container):
    subprocess.run(f"docker exec {container} apachectl -k graceful", shell=True)

# Restart localhost server for changes to take effect
def restart_localhost():
    subprocess.run(f"sudo systemctl restart apache2.service", shell=True)

def write_custom_config(server, content):
    file = (Constants.APACHE_HTTPD_CUSTOM_PATH % server) if server != 'localhost' else Constants.LOCALHOST_HTTPD_CUSTOM_PATH
    with open(file, "w") as fp:
        fp.write(content)

def create_config(host, ip, ports_dict, websockets_dict, ssl_dict, path_to_serve_paths, endpoints, disable_browser_cache=False):
    # Add ServerName
    conf = add_serverName(host=host)
    
    # Add Listeners
    for val in ports_dict.values():
        conf += set_listener(port=val, host=host)

    if disable_browser_cache is True:
        conf += disable_cache_set_Cache_Control()

    # Add VirtualHosts
    ports = ["80", ports_dict['{PORT}']]
    ssl_ports = ["443", ports_dict['{SSL_PORT}']]

    for port in ports:
        conf += create_vhost(host=host, ip=ip, port=port, ws_host=websockets_dict['host'], ws_port=websockets_dict['port'], server_path=path_to_serve_paths, endpoints=endpoints, ssl=False)
    for port in ssl_ports:
        conf += create_vhost(host=host, ip=ip, port=port, ws_host=websockets_dict['host'], ws_port=websockets_dict['ssl_port'], server_path=path_to_serve_paths, endpoints=endpoints, ssl=True, ssl_dict=ssl_dict)

    return conf

def create_vhost(host, ip, port, ws_host, ws_port, server_path, endpoints, ssl=False, ssl_dict = None):
    content = add_serverName(host=host, port=port)
    content += enable_rewrite()
    content += add_ws_proxy(host=ws_host, port=ws_port, ssl=ssl)
    content += add_directory(path=server_path)

    # Add endpoints
    endpoints_path = Constants.APACHE_ENDPOINTS_PATH if host != 'localhost' else Constants.LOCALHOST_ENDPOINTS_PATH
    content += generate_api_config(endpoints_path=endpoints_path, endpoints=endpoints)

    # server_path -> from where all urls with a path will be served
    content += serve_all_paths(server_path=server_path)
    if ssl is True and ssl_dict is not None:
        content += add_ssl_support(ca_path=ssl_dict['ca'], crt_path=ssl_dict['crt'], key_path=ssl_dict['key'])

    return add_vhost(host=ip, port=port, content=content)

def create_variables_php_code(placeholders_dict):
    php_code = ""
    for key, value in placeholders_dict.items():
        php_value = python_to_php(value=value)
        php_code += f"${key} = {php_value};\n"
    return php_code

def overwrite_php_file(path, php_code, logger=None):
    if not os.path.exists(path=path):
        msg = f"Path `{path}` does not exist."
        if logger:
            logger.critical(msg)
        raise Exception(msg)
    try:
        with open(path, "w") as fp:
            fp.write(php_code)
    except Exception as e:
        log_msg = extract_log_msg(exception=e)
        if logger:
            logger.exception(log_msg)
        raise Exception(log_msg)

def insert_variables_in_php_file(server, php_file, placeholders_dict):
    php_code = "<?php\n" + create_variables_php_code(placeholders_dict=placeholders_dict) + "?>"
    root_path = os.path.join(Constants.APACHE_PREPENDS_HOST_PATH, server) if server != 'localhost' else Constants.LOCALHOST_PREPENDS_HOST_PATH
    overwrite_php_file(path=os.path.join(root_path, php_file), php_code=php_code)

def set_header_php_code(header):
    escaped = header.replace("\\", "\\\\").replace('"', '\\"')
    return f'header("{escaped}", false);\n'

def set_status_code(status_code):
    return f"http_response_code({status_code});\n"

def insert_mechanisms_in_php_file(server, php_file, mechanisms_dict, status_code, testing_domain, results_id, logger):
    php_code = "<?php\n" # php open tag
    
    # set custom/sticky headers
    for header in mechanisms_dict.get('headers', []):
        php_code += set_header_php_code(header=header)
    
    # set and collect mechanism headers
    mechanism_variables_to_set = {}
    for mechanism, values in mechanisms_dict.get('mechanisms_headers', {}).items():
        mechanism_variables_to_set[mechanism] = []
        for value, metadata in values:
            mechanism_variables_to_set[mechanism].append(value)
            if value is None: continue
            header_to_set = f"{mechanism}: {value}" if metadata.get('mutation_in') != 'header_name' else value
            php_code += set_header_php_code(header=header_to_set)
        if len(mechanism_variables_to_set[mechanism]) == 1:
            mechanism_variables_to_set[mechanism] = mechanism_variables_to_set[mechanism][0]
    
    # collect other mechanisms (like html-attributes and other)
    for mechanism, values in mechanisms_dict.get('mechanisms_other', {}).items():
        mechanism_variables_to_set[mechanism] = []
        for value, metadata in values:
            mechanism_variables_to_set[mechanism].append(value)
        if len(mechanism_variables_to_set[mechanism]) == 1:
            mechanism_variables_to_set[mechanism] = mechanism_variables_to_set[mechanism][0]
    
    # Set PHP variables for all mechanisms' values!
    php_code += create_variables_php_code(placeholders_dict={'mechanisms': mechanism_variables_to_set, 'testing_domain': testing_domain, 'results_id': results_id})
    
    # set status code
    if status_code:
        php_code += set_status_code(status_code=status_code)
    
    php_code += "?>\n" # php closing tag
    root_path = os.path.join(Constants.APACHE_PREPENDS_HOST_PATH, server) if server != 'localhost' else Constants.LOCALHOST_PREPENDS_HOST_PATH
    overwrite_php_file(path=os.path.join(root_path, php_file), php_code=php_code, logger=logger)

# helper, because we need different format to store deployments in the database (for replay and analysis) and different to store in PHP prepend file!
def deployment_to_domain_format(deployment_mechanisms):
    result = {}

    def init_domain(d):
        if d not in result:
            result[d] = {
                "headers": [],
                "mechanisms_headers": {},
                "mechanisms_other": {}
            }

    for item in deployment_mechanisms:

        domains = item["set_on"]

        if item["type"] == "header":

            for d in domains:
                init_domain(d)
                result[d]["headers"].extend(item["headers"])

        elif item["type"] == "mechanism":

            mech = item["mechanism"]
            mech_type = item["mechanism_type"]
            values = item["values"]

            target = "mechanisms_headers" if mech_type == "http-header" else "mechanisms_other"

            for d in domains:

                init_domain(d)

                if mech not in result[d][target]:
                    result[d][target][mech] = []

                result[d][target][mech].extend(values)

    return result

def _replace_placeholders(value, domains_dict, ports_dict, ip_dict):
    for key, val in domains_dict.items():
        value = value.replace(key, f"{val}.com")
    for key, val in ports_dict.items():
        value = value.replace(key, val)
    for key, val in ip_dict.items():
        value = value.replace(key, val)
    return value

def replace_placeholders(value, should_generate_hashes, environment_info):
    if value is None:
        return value
    if '{CORRECT_SCRIPT_HASH}' in value:
        should_generate_hashes['script'] = True
    if '{CORRECT_STYLE_HASH}' in value:
        should_generate_hashes['style'] = True
    
    new_value = _replace_placeholders(value=value, domains_dict=environment_info['containers_dict'], ports_dict=environment_info['ports_dict'], ip_dict=environment_info['ip_dict'])
    if value != new_value:
        return new_value
    return value
