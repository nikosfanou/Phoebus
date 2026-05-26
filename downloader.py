import requests
import subprocess
from bs4 import BeautifulSoup
import json
import os
import re
from argparse import ArgumentParser

class Constants:
    # ANSI escape codes for text color
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    ENDC = '\033[0m'  # Reset color
    CONFIG_FILE = './configs/browsers-info.json'
    OK = 200 # OK Status Code
    CHAR_TO_REPLACE = {
        "<td>": "",
        "<tr>": "",
        "</td>": "",
        "</tr>": "",
        "≥": "",
        "ESR" : "",
        ",": "",
        "[" : "",
        "]" : "",
        " ": "", # space must be before new lines and tabs
        #"\n": " ",
        #"\t": ""
    }
    FILETYPES = {
        ".tar.gz",
        ".tar.bz2",
        ".tar.xz",
        ".zip",
        ".deb"
    }


def get_args():
    parser = ArgumentParser()
    parser.add_argument("-C", "--chrome", default = None, const = '', dest = "chrome_version", nargs = '?', help = "Download specific or latest Chrome version")
    parser.add_argument("-F", "--firefox", default = None, const = '', dest = "firefox_version", nargs = '?',  help = "Download specific or latest Firefox version")
    parser.add_argument("-O", "--opera", default = None, const = '', dest = "opera_version", nargs = '?',  help = "Download specific or latest Opera version")
    parser.add_argument("-E", "--edge", default = None, const = '', dest = "edge_version", nargs = '?', help = "Download specific or latest Microsoft Edge version")
    parser.add_argument("-B", "--brave", default = None, const = '', dest = "brave_version", nargs = '?', help = "Download specific or latest Brave version")
    parser.add_argument("-T", "--tor", default = None, const = '', dest = "tor_version", nargs = '?', help = "Download specific or latest Tor version")
    parser.add_argument("-W", "--webkit", default = None, const = '', dest = "webkit_version", nargs = '?', help = "Download specific or latest WebKit version")
    parser.add_argument("-S", "--safari", default = None, const = '', dest = "safari_version", nargs = '?', help = "Download specific or latest WebKit version, which corresponds to the given Safari version")
    return parser.parse_args()

def load_browsers_config():
    with open(Constants.CONFIG_FILE, "r") as fp:
        return json.load(fp)

def write_file(filename, contents):
    with open(filename, 'w') as fp:
        fp.write(contents)

def write_config(config):
    with open(Constants.CONFIG_FILE, "w") as wfp:
        json.dump(config, wfp, indent = 2)

def print_error(error_msg):
    print(Constants.RED + '[ERROR] ' + error_msg + Constants.ENDC)

def print_warning(warn_msg):
    print(Constants.YELLOW + '[WARN] ' + warn_msg + Constants.ENDC)

def print_info(info_msg):
    print(Constants.BLUE + '[INFO] ' + info_msg + Constants.ENDC)

def print_msg(msg):
    print(Constants.GREEN + msg + Constants.ENDC)

def download(download_link, download_path, filename, filetype, version):
    remote_link = download_link + filetype
    download_file = filename + filetype
    local_path = os.path.join(download_path, download_file % version)
    retcode = subprocess.call(["wget","-c", remote_link, "-O", local_path])
    if retcode != 0:
        print_error(f"Wget returned non-zero exit code: {retcode}")
        subprocess.run(f"rm {local_path}", shell=True)
        return False
    return True

def download_other_filetype(download_link, download_path, filename, failed_filetype, version):
    filetypes = Constants.FILETYPES.copy()
    filetypes.remove(failed_filetype)
    for filetype in filetypes:
        print_info(f"Will try to download {filetype} file...")
        if (download(download_link=download_link, download_path=download_path, filename=filename, filetype=filetype, version=version)):
            print_info(f"Successfully downloaded {filetype} file")
            return True
    return False

'''
Google Chrome
'''
def get_chromedriver_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error(f"URL to check chromedriver latest version responded with HTTP {r.status_code}")
        return ""
    latest_version = r.text
    return latest_version

def get_chrome_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error(f"URL to check Google Chrome latest version responded with HTTP {r.status_code}")
        return ""
    all_versions = json.loads(r.text)
    if not all_versions['versions']:
        print_error('None google chrome versions were returned by the API.')
        return ""
    latest_version = all_versions['versions'][0]['version']
    return latest_version

def download_chrome_latest_version():
    config = load_browsers_config() # Keep whole config, so we can dump it again later
    chrome_data = config["chrome"]

    latest_version = get_chrome_latest_version(chrome_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Google Chrome latest version!")
        return False
    if latest_version == chrome_data["latest-version"]:
        print_msg(f"Latest Chrome version ({latest_version}) should already be stored")
        return True

    filetype = ".deb"
    filename = "chrome-browser-%s"
    print_info(f"Detected new Chrome version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(chrome_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Chrome version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = chrome_data["download_latest_version_url"]
    if not download(download_link=version_url,download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url,download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False
    
    res = download_chromedriver(latest_version)
    if res == False: #could not download driver
        return False
    chrome_data["latest-version"] = latest_version
    write_config(config)
    print_msg("Chrome download complete")
    return True

def download_chrome_version(version):
    config = load_browsers_config()
    chrome_data = config["chrome"]
    filetype = ".deb"
    filename = "chrome-browser-%s"

    print_info(f"Download Chrome version {version}. Will download {filetype} file")
    version_path = os.path.join(chrome_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Chrome version {version} download directory: {version_path}")
        os.makedirs(version_path)
    
    version_url = chrome_data["download_version_url"].replace("{CHROME_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    res = download_chromedriver(version)
    if res == False:
        return False
    print_msg("Chrome download complete")
    return True

def download_chromedriver_old(version, chromium_version=None, browser="chrome"):
    config = load_browsers_config()
    browser_data = config[browser]
    version_path = os.path.join(browser_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating {browser} version {version} download directory: {version_path}")
        os.makedirs(version_path)
    #Try exact match
    version_url = browser_data["old_download_webdriver_url"].replace("{CHROMIUM_VERSION}", chromium_version)
    retcode = subprocess.call(["wget","-c", version_url, "-O", os.path.join(version_path, "%s-%s.zip" % (browser, version))])
    if retcode != 0:
        print_warning(f"Couldn't match exactly this version ({version}) to the chromedriver {chromium_version}. Wget returned non-zero exit code: {retcode}")
    else:
        print_info(f"Download chromedriver {chromium_version} for {browser} version {version}. Downloaded .zip file")
        return True
    #For example from version 99.0.4844.51 keep 99.0.4844 and search for its latest release.
    subversions = chromium_version.split(".")
    major_version = ".".join(subversions[0:3])
    r = requests.get(browser_data["check_webdriver_release_url"].replace("{MAJOR_VERSION}", major_version))
    if r.status_code != Constants.OK: # Make sure we got a valid response, i.e. the website is responsive, there are no network issues etc.
        print_warning(f"URL to check Chromedriver {major_version} latest release responded with HTTP {r.status_code}. Will try to find the latest release for major version {subversions[0]}!")
        #For example from version 99.0.4844.51 keep 99 and search for its latest release.
        major_version = subversions[0]
        r = requests.get(browser_data["check_webdriver_release_url"].replace("{MAJOR_VERSION}", major_version))
        if r.status_code != Constants.OK:
            print_error(f"URL to check Chromedriver {major_version} latest release responded with HTTP {r.status_code}.")
            return False
    chromedriver_release = r.text
    print_info(f"Download chromedriver {chromedriver_release} for {browser} version {version}. Will download .zip file")
    version_url = browser_data["old_download_webdriver_url"].replace("{CHROMIUM_VERSION}", chromedriver_release)
    retcode = subprocess.call(["wget","-c", version_url, "-O", os.path.join(version_path, "%s-driver-%s.zip" % (browser, version))])
    if retcode != 0:
        print_error(f"Wget returned non-zero exit code: {retcode}")
        return False
    return True

def download_chromedriver_new(version, chromium_version=None, browser="chrome"):
    config = load_browsers_config()
    browser_data = config[browser]
    filename = f"{browser}-driver-%s"
    filetype = ".zip"
    version_path = os.path.join(browser_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating {browser} version {version} download directory: {version_path}")
        os.makedirs(version_path)
    #Try only exact match
    version_url = browser_data["download_webdriver_url"].replace("{CHROMIUM_VERSION}", chromium_version)
    print_info(f"Download chromedriver {chromium_version} for {browser} version {version}. Will download {filetype} file")
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            print_error(f"Couldn't match exactly this version ({version}) to the chromedriver {chromium_version}")
            return False
    return True

# > 114v See: https://googlechromelabs.github.io/chrome-for-testing/
def download_chromedriver(version, chromium_version=None, browser="chrome"):
    if chromium_version is None:
        chromium_version = version
    main_version = chromium_version.split('.')[0]
    if int(main_version) > 114:
        return download_chromedriver_new(version=version, chromium_version=chromium_version, browser=browser)
    else:
        return download_chromedriver_old(version=version, chromium_version=chromium_version, browser=browser)

'''Mozilla Firefox'''
def get_firefox_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error(f"URL to check the latest firefox version responded with HTTP {r.status_code}")
        return False

    soup = BeautifulSoup(r.text, 'html.parser')
    release_list = soup.find(class_='c-release-list').find('li') # the first list is the latest releases
    li = release_list.find_all('li')
    #print(li)
    
    latest_version = ""
    if(li is None or li == []):
        latest_version = release_list.find('strong').string.strip()
    else:
        #print(type(li))
        #print(len(li))
        last_elem = li[len(li) - 1]
        latest_version = last_elem.string.strip()
    return latest_version

def download_firefox_latest_version():
    config = load_browsers_config()
    firefox_data = config["firefox"]
    
    latest_version = get_firefox_latest_version(firefox_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Firefox latest version!")
        return False
    if latest_version == firefox_data["latest-version"]:
        print_msg(f"Latest Firefox version ({latest_version}) should already be stored")
        return True

    filetype = ".tar.xz"
    filename = "firefox-browser-%s"
    print_info(f"Detected new Firefox version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(firefox_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Firefox version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = firefox_data["download_version_url"].replace("{FIREFOX_VERSION}", latest_version)
    if not download(download_link=version_url,download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url,download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False
    
    print_info(f"Will try to download .deb file in additional folder just to keep track of deb files too!")
    additional_folder = os.path.join(firefox_data["save_to_directory"], latest_version, "additional")
    if not os.path.isdir(additional_folder):
        os.makedirs(additional_folder)
    version_url = version_url.replace(filetype, '.deb')
    download(download_link=version_url, download_path=additional_folder, filename=filename, filetype='.deb', version=latest_version)

    res = download_geckodriver(latest_version)
    if res == False:
        return False

    firefox_data["latest-version"] = latest_version
    write_config(config)
    
    print_msg("Firefox download complete")
    return True

def download_firefox_version(version):
    config = load_browsers_config()
    firefox_data = config["firefox"]
    filetype = ".tar.xz"
    filename = "firefox-browser-%s"

    print_info(f"Download Firefox version {version}. Will download {filetype} file")
    version_path = os.path.join(firefox_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Firefox version {version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = firefox_data["download_version_url"].replace("{FIREFOX_VERSION}", version)
    if not download(download_link=version_url,download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url,download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    print_info(f"Will try to download .deb file too!")
    additional_folder = os.path.join(firefox_data["save_to_directory"], version, "additional")
    if not os.path.isdir(additional_folder):
        os.makedirs(additional_folder)
    version_url = version_url.replace(filetype, '.deb')
    download(download_link=version_url, download_path=additional_folder, filename=filename, filetype='.deb', version=version)

    res = download_geckodriver(version)
    if res == False:
        return False
    
    print_msg("Firefox download complete")
    return True

def download_geckodriver(version):
    config = load_browsers_config()
    firefox_data = config["firefox"]

    r = requests.get(firefox_data["version_driver_mapping_url"])
    if r.status_code != Constants.OK:
        print_error(f"URL to check geckodrivers compatibility with Firefox versions responded with HTTP {r.status_code}")
        return False

    major_version = int(version.split('.')[0])
    soup = BeautifulSoup(r.text, 'html.parser')
    table = str(soup.find_all('td'))
    
    geckodriver_release = ""
    for key, val in Constants.CHAR_TO_REPLACE.items():
        table = table.replace(key, val)

    table = table.split()
    
    for i in range(0, len(table), 4): # iterate line by line in the table
        if(int(table[i+2]) <= major_version and (table[i+3] == "n/a" or int(table[i+3]) >= major_version)): # Then it is compatible
            geckodriver_release = table[i]
            break

    if(geckodriver_release == ""):
        print_error(f"Could not find compatible geckodriver for Firefox version {version}")
        return False

    filename = "firefox-driver-%s"
    filetype = ".tar.gz"
    print_info(f"Download geckodriver {geckodriver_release} for Firefox version {version}. Will download {filetype} file")
    version_path = os.path.join(firefox_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Firefox version {version} download directory: {version_path}")
        os.makedirs(version_path)
    version_url = firefox_data["download_webdriver_url"].replace("{GECKODRIVER_VERSION}", geckodriver_release)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    return True

'''Opera'''
def get_opera_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error(f"URL to check Opera latest version responded with HTTP {r.status_code}")
        return ""

    soup = BeautifulSoup(r.text, 'html.parser')
    # soup.prettify()
    tr = soup.find_all('tr')
    td = tr[2].find_all('td')
    latest_version = td[1].string
    return latest_version

def download_opera_latest_version():
    config = load_browsers_config()
    opera_data = config["opera"]

    latest_version = get_opera_latest_version(opera_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Opera latest version!")
        return False
    
    if latest_version == opera_data["latest-version"]:
        print_msg(f"Latest Opera version ({latest_version}) should already be stored")
        return True

    filetype = ".deb"
    filename = "opera-browser-%s"
    print_info(f"Detected new Opera version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(opera_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Opera version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)
    
    version_url = opera_data["download_latest_version_url"].replace("{OPERA_LATEST_VERSION}", latest_version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False
    
    res = download_operadriver(latest_version)
    if res == False: #could not download driver
        return False

    opera_data["latest-version"] = latest_version
    write_config(config)
    
    print_msg("Opera download complete")
    return True

def download_opera_version(version):
    config = load_browsers_config()
    opera_data = config["opera"]
    filetype = ".deb"
    filename = "opera-browser-%s"

    print_info(f"Download Opera version {version}. Will download {filetype} file")
    version_path = os.path.join(opera_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Opera version {version} download directory: {version_path}")
        os.makedirs(version_path)
    
    version_url = opera_data["download_version_url"].replace("{OPERA_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    res = download_operadriver(version)
    if(res == False):
        return False

    print_msg("Opera download complete")
    return True

def download_operadriver(version):
    '''
        The oldest operadriver version we will search for is 2.29 (Opera version 46)
    '''
    config = load_browsers_config()
    opera_data = config["opera"]

    #For example from version 86.0.4363.32 keep 86 and search for its compatible driver.
    major_version = version.split(".")[0]
    if int(major_version) < 46 :
        print_error("Cannot download operadriver for Opera major version older than 46")
        return False

    operadriver_release = ""

    page = 1
    while(page < 100): # only to be sure that it won't run forever
        r = requests.get(opera_data["check_webdriver_release_url"] + "?page=" + str(page))
        if r.status_code != Constants.OK:
            print_error("URL to find compatible operadriver responded with HTTP %s" % r.status_code)
            return False

        soup = BeautifulSoup(r.text, 'html.parser')
        divs = soup.find_all('div', class_="markdown-body my-3") # get opera versions
        a = soup.select("a[href*='/operasoftware/operachromiumdriver/releases/tag/']") # get operadriver versions

        for i in range(len(divs)):
            opera_stable = divs[i].find('p').find('a').string
            if((opera_stable == "Opera Stable " + major_version) or (opera_stable == "Opera " + major_version)):
                operadriver_release = a[i].string.strip() # remove whitespaces
                break

            if(opera_stable == "Opera 46"): # We dont search operadrivers for versions older than Opera 46
                print_error("Could not find compatible operadriver for Opera version %s" % version)
                return False

        if operadriver_release != "" : # we found it
            break

        page = page + 1

    filename = f"opera-driver-%s"
    filetype = ".zip"
    print_info(f"Download operadriver {operadriver_release} for Opera version {version}. Will download {filetype} file")
    version_path = os.path.join(opera_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Opera version {version} download directory: {version_path}")
        os.makedirs(version_path)
    version_url = opera_data["download_webdriver_url"].replace("{OPERA_DRIVER_VERSION}", operadriver_release)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    return True

'''Microsoft Edge'''
def get_edge_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error("URL to check Edge latest version responded with HTTP %s" % r.status_code)
        return ""
    
    latest_version = ""
    soup = BeautifulSoup(r.text, 'html.parser')
    table = soup.find(class_="table table-striped table-hover")
    tr = table.find_all('tr')
    for line in tr:
        td = line.find_all('td')
        if not td:
            continue
        strong = td[0].find('strong')
        if strong and strong.string.lower() == 'linux':
            latest_version = td[1].string
            break
            
    return latest_version

def download_edge_latest_version():
    config = load_browsers_config()
    edge_data = config["edge"]

    latest_version = get_edge_latest_version(edge_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Microsoft Edge latest version!")
        return False
    
    if latest_version == edge_data["latest-version"]:
        print_msg("Latest Edge version (%s) should already be stored" % latest_version)
        return True

    filetype = ".deb"
    filename = "edge-browser-%s"
    print_info(f"Detected new Edge version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(edge_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Edge version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = edge_data["download_version_url"].replace("{EDGE_VERSION}", latest_version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False

    res = download_edgedriver(latest_version)
    if res == False: #could not download driver
        return False

    edge_data["latest-version"] = latest_version
    write_config(config)
    
    print_msg("Edge download complete")
    return True

def download_edge_version(version):
    config = load_browsers_config()
    edge_data = config["edge"]
    filetype = ".deb"
    filename = "edge-browser-%s"

    print_info(f"Download Edge version {version}. Will download {filetype} file")
    version_path = os.path.join(edge_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Edge version {version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = edge_data["download_version_url"].replace("{EDGE_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    res = download_edgedriver(version)
    if(res == False):
        return False

    print_msg("Microsoft Edge download complete")
    return True

def download_edgedriver(version):
    config = load_browsers_config()
    edge_data = config['edge']
    filename = f"edge-driver-%s"
    filetype = ".zip"

    print_info(f"Download msedgedriver version {version}. Will download {filetype} file")
    version_path = os.path.join(edge_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Edge version {version} download directory: {version_path}")
        os.makedirs(version_path)

    webdriver_url = edge_data["download_webdriver_url"].replace("{EDGE_VERSION}", version)
    if not download(download_link=webdriver_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=webdriver_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    return True

'''Brave'''
def match_brave_version(version_string):
    pattern = r'Release v([\d.]+) \(Chromium ([\d.]+)\)'
    match = re.search(pattern, version_string)
    if match:
        # Extract Brave version and Chromium version
        brave_version = match.group(1)
        chromium_version = match.group(2)
        return brave_version, chromium_version
    else:
        print_error("Couldn't match Brave or/and Chromium version.")
        return "", ""

def get_brave_chromium_version(version_url):
    r = requests.get(version_url)
    if r.status_code != Constants.OK:
        print_error("URL to check Brave latest version responded with HTTP %s" % r.status_code)
        return ""
    
    soup = BeautifulSoup(r.text, 'html.parser')
    box = soup.find(class_="Box-body")
    line = box.find(class_='d-inline mr-3')
    brave_version, chromium_version = match_brave_version(line.text)
            
    return brave_version, chromium_version

def download_brave_latest_version():
    config = load_browsers_config()
    brave_data = config["brave"]

    latest_version, chromium_version = get_brave_chromium_version(brave_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Brave latest version!")
        return False
    
    if latest_version == brave_data["latest-version"]:
        print_msg("Latest Brave version (%s) should already be stored" % latest_version)
        return True

    filetype = ".deb"
    filename = "brave-browser-%s"
    print_info(f"Detected new Brave version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(brave_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Brave version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = brave_data["download_version_url"].replace("{BRAVE_VERSION}", latest_version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False

    if not chromium_version:
        print_error("Couldn't extract the Chromium version in order to download the correct chromedriver!")
        return False
    
    res = download_chromedriver(version=latest_version, chromium_version=chromium_version, browser="brave")
    if res == False: #could not download driver
        return False

    brave_data["latest-version"] = latest_version
    write_config(config)
    
    print_msg("Brave download complete")
    write_file(filename=os.path.join(version_path, "chromium_version.txt"), contents=chromium_version)
    return True

def download_brave_version(version):
    config = load_browsers_config()
    brave_data = config["brave"]
    filetype = ".deb"
    filename = "brave-browser-%s"

    print_info(f"Download Brave version {version}. Will download {filetype} file")
    version_path = os.path.join(brave_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Brave version {version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = brave_data["download_version_url"].replace("{BRAVE_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    get_chromium_version_url = brave_data['check_corresponding_chromium_version'].replace('{BRAVE_VERSION}', version)
    extracted_version, chromium_version = get_brave_chromium_version(get_chromium_version_url)
    # extracted_version == version can be used to be sure we have the correct version
    if extracted_version != version:
        print_error("[ASSERTION] Extracted different Brave version than the one given. Exiting...")
        return False
    
    res = download_chromedriver(version=version, chromium_version=chromium_version, browser="brave")
    if res == False:
        return False

    print_msg("Brave download complete")
    write_file(filename=os.path.join(version_path, "chromium_version.txt"), contents=chromium_version)
    return True

'''Tor'''
def match_tor_version(file_version_string):
    pattern = r'tor-browser-linux-x86_64-([\d.]+)(\.\w+(?:\.\w+)*)$'
    match = re.search(pattern, file_version_string)
    if match:
        # Extract Tor version
        version = match.group(1)
        extension = match.group(2)
        return version, extension
    print_error(f"Couldn't match Tor latest version. Extracted file was: {file_version_string}")
    return "", ""

def get_tor_latest_version(latest_version_url):
    r = requests.get(latest_version_url)
    if r.status_code != Constants.OK:
        print_error("URL to check Tor latest version responded with HTTP %s" % r.status_code)
        return ""
    
    latest_version = ""
    soup = BeautifulSoup(r.text, 'html.parser')
    buttons = soup.find_all(class_="btn btn-primary mt-4 downloadLink")
    extracted_file = ""
    for button in buttons:
        if 'Linux' in button.text:
            extracted_file = button.get('href').split('/')[-1]
            break
    
    latest_version, filetype = match_tor_version(extracted_file)
    return latest_version, filetype

def download_tor_latest_version():
    config = load_browsers_config()
    tor_data = config["tor"]

    latest_version, filetype = get_tor_latest_version(tor_data["check_latest_version_url"])
    if not latest_version:
        print_error("Couldn't find Tor latest version!")
        return False
    
    if latest_version == tor_data["latest-version"]:
        print_msg(f"Latest Tor version ({latest_version}) should already be stored")
        return True

    filename = "tor-browser-%s"
    print_info(f"Detected new Tor version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(tor_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest Tor version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = tor_data["download_version_url"].replace("{TOR_VERSION}", latest_version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        # NOTE: Here we capture the extension as well so we don't need to try other extensions!
        return False

    res = download_tor_geckodriver(latest_version)
    if res == False: #could not download driver
        return False

    tor_data["latest-version"] = latest_version
    write_config(config)
    
    print_msg("Tor download complete")
    return True

def download_tor_version(version):
    config = load_browsers_config()
    tor_data = config["tor"]
    filename = "tor-browser-%s"
    filetype = ".tar.xz"

    print_info(f"Download Tor version {version}. Will download {filetype} file")
    version_path = os.path.join(tor_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Tor version {version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = tor_data["download_version_url"].replace("{TOR_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    
    res = download_tor_geckodriver(version=version)
    if res == False:
        return False

    print_msg("Tor download complete")
    return True

def download_tor_geckodriver(version):
    config = load_browsers_config()
    tor_data = config['tor']
    filename = "tor-driver-%s"
    filetype = ".tar.xz"
    print_info(f"Download Tor geckodriver version {version}. Will download {filetype} file")
    version_path = os.path.join(tor_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating Tor version {version} download directory: {version_path}")
        os.makedirs(version_path)

    webdriver_url = tor_data["download_webdriver_url"].replace("{TOR_VERSION}", version)
    if not download(download_link=webdriver_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=webdriver_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
    return True

def get_safari_webkit_latest_version(version_url):
    data = None
    response = requests.get(version_url)
    if response.ok:
        data = json.loads(response.text)
    if data is not None:
        releases = data['browsers']['safari']['releases']
        for safari_version, info in releases.items():
            if info["status"] == "current" and info["engine"].lower() == "webkit":
                webkit_version = info["engine_version"]
                print_info(f"Found Safari: {safari_version}, WebKit: {webkit_version}")
                return safari_version, webkit_version
    print_error("Couldn't extract Safari/WebKit latest versions")
    return None, None

def get_webkit_version(version_url, safari_version):
    data = None
    response = requests.get(version_url)
    if response.ok:
        data = json.loads(response.text)
    if data is not None:
        releases = data['browsers']['safari']['releases']
        if safari_version in releases and releases[safari_version]['engine'].lower() == 'webkit':
            webkit_version = releases[safari_version]['engine_version']
            print_info(f"Found Safari: {safari_version}, WebKit: {webkit_version}")
            return webkit_version
    print_error(f"Couldn't extract WebKit version matching Safari version: {safari_version}")
    return None

def download_webkit_latest_version():
    config = load_browsers_config()
    webkit_data = config['webkit']
    safari_latest_version, latest_version = get_safari_webkit_latest_version(version_url=webkit_data["check_latest_version_url"])
    if latest_version == webkit_data["latest-version"]:
        print_msg(f"Latest WebKit version ({latest_version}) should already be stored")
        return True
    
    filename = "webkit-%s"
    filetype = ".zip"
    print_info(f"Detected new WebKit version {latest_version}. Will download {filetype} file")
    version_path = os.path.join(webkit_data["save_to_directory"], latest_version)
    if not os.path.exists(version_path):
        print_info(f"Creating latest WebKit version {latest_version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = webkit_data["download_version_url"].replace("{WEBKIT_VERSION}", latest_version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=latest_version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=latest_version):
            return False
        
    webkit_data["latest-version"] = latest_version
    webkit_data["safari-latest-version"] = safari_latest_version
    write_config(config)
    
    print_msg("WebKit download complete")
    return True

def download_webkit_version(version):
    config = load_browsers_config()
    webkit_data = config['webkit']
    filename = "webkit-%s"
    filetype = ".zip"

    version_path = os.path.join(webkit_data["save_to_directory"], version)
    if not os.path.exists(version_path):
        print_info(f"Creating WebKit version {version} download directory: {version_path}")
        os.makedirs(version_path)

    version_url = webkit_data["download_version_url"].replace("{WEBKIT_VERSION}", version)
    if not download(download_link=version_url, download_path=version_path, filename=filename, filetype=filetype, version=version):
        if not download_other_filetype(download_link=version_url, download_path=version_path, filename=filename, failed_filetype=filetype, version=version):
            return False
       
    print_msg("WebKit download complete")
    return True

def download_webkit_safari_version(safari_version):
    config = load_browsers_config()
    webkit_data = config['webkit']
    version = get_webkit_version(version_url=webkit_data["check_latest_version_url"], safari_version=safari_version)
    return download_webkit_version(version=version)

if __name__ == "__main__":
    args = get_args()
    # Google Chrome
    if args.chrome_version is not None:
        if args.chrome_version == '':
            download_chrome_latest_version()
        else:
            download_chrome_version(args.chrome_version)
    # Mozilla Firefox
    if args.firefox_version is not None:
        if args.firefox_version == '':
            download_firefox_latest_version()
        else:
            download_firefox_version(args.firefox_version)
    # Opera
    if args.opera_version is not None:
        if args.opera_version == '':
            download_opera_latest_version()
        else:
            download_opera_version(args.opera_version)
    # Microsoft Edge
    if args.edge_version is not None:
        if args.edge_version == '':
            download_edge_latest_version()
        else:
            download_edge_version(args.edge_version)
    # Brave
    if args.brave_version is not None:
        if args.brave_version == '':
            download_brave_latest_version()
        else:
            download_brave_version(args.brave_version)
    # Tor
    if args.tor_version is not None:
        if args.tor_version == '':
            download_tor_latest_version()
        else:
            download_tor_version(args.tor_version)
    # NOTE: WebKit tarball includes both browser and webdriver
    if args.webkit_version is not None:
        if args.webkit_version  == '':
            download_webkit_latest_version()
        else:
            download_webkit_version(args.webkit_version)
    # WebKit that corresponds to this Safari version
    if args.safari_version is not None:
        if args.safari_version  == '':
            download_webkit_latest_version()
        else:
            download_webkit_safari_version(args.safari_version)
