##################################################################################################
# Methods to generate Apache Configurations
##################################################################################################
import os


def set_listener(port, host = None):
    hostname = host + ':' if host is not None else ""
    return f"Listen {hostname}{port}\n"

def set_header(header, value, always=False):
    set_value = value.replace("\"", "\\\"")
    is_always = "always" if always else ""
    return f"Header {is_always} set {header} \"{set_value}\"\n"

def merge_header(header, value, always=False):
    set_value = value.replace("\"", "\\\"")
    is_always = "always" if always else ""
    return f"Header {is_always} merge {header} \"{set_value}\"\n"

def add_header(header, value, always=False):
    set_value = value.replace("\"", "\\\"")
    is_always = "always" if always else ""
    return f"Header {is_always} add {header} \"{set_value}\"\n"

def add_directory(path):
    return f"\n\
    <Directory \"{path}\">\n\
    Options Indexes FollowSymLinks\n\
    AllowOverride None\n\
    Require all granted\n\
    </Directory>\n"

def enable_rewrite(): # always call that before calling add_ws_proxy() or serve_specific_file()
    return "RewriteEngine On\n"

def add_ws_proxy(host, port, ssl=False):
    ws = "wss" if ssl else "ws"
    return f"\n\
    RewriteCond %{{HTTP:Upgrade}} websocket [NC]\n\
    RewriteCond %{{HTTP:Connection}} Upgrade [NC]\n\
    RewriteRule \"^/?(.*)\" \"{ws}://{host}:{port}\" [P,L]\n"

def add_LocationMatch(location, content):
    return f"<LocationMatch \"^/{location}\">\n\
            {content}\n\
            </LocationMatch>\n"

def add_if_query_string(arg_key, arg_value, content):
    return f"<If \"%{{QUERY_STRING}} =~ /.*{arg_key}={arg_value}.*/\" >\n\
            {content}\n\
            </If>\n"

# serves specific file to all the files ending in the given extension
def serve_specific_file(extension, path_to_file):
    return f"\n\
    RewriteCond %{{REQUEST_URI}} \.{extension}$\n\
    RewriteRule ^(.*)\.{extension}$ {path_to_file}.{extension} [L]\n"

def add_alias(url_path, server_path):
    return f"Alias \"{url_path}\" \"{server_path}\"\n"

def add_alias_match(url_path_regex, server_path_regex):
    return f"AliasMatch \"{url_path_regex}\" \"{server_path_regex}\"\n"

def generate_api_config(endpoints_path, endpoints):
    config = ""

    # Alias
    config += f'Alias "/api/" "{endpoints_path}/"\n\n'

    # Directory block
    config += f'<Directory "{endpoints_path}/">\n'
    config += "    Require all granted\n"
    config += "    Options +FollowSymLinks\n"
    config += "    AllowOverride None\n\n"
    config += "    RewriteEngine On\n"

    # Rewrite rules, convert e.g., dummy.php to /dummy endpoint
    for endpoint in endpoints:
        name = os.path.splitext(endpoint)[0]
        config += f'    RewriteRule ^{name}$ {endpoint} [L]\n'

    config += "</Directory>\n\n"

    return config

def serve_all_paths(server_path):
    # at least 1 front-path (specified by .+ character) is needed to connect the url path to the server path/directory.
    # E.g. AliasMatch "^/.+/(.+)$" "/usr/local/apache2/htdocs/resources/$1"
    url_path_regex = "^/.+/(.+)$"
    server_path_regex = os.path.join(server_path, "$1")
    return add_alias_match(url_path_regex=url_path_regex, server_path_regex=server_path_regex)


def add_serverName(host, port=None):
    s_port = f":{port}" if port else ""
    return f"ServerName {host}{s_port}\n"

def add_ssl_support(ca_path, crt_path, key_path):
    return f"\n\
    SSLEngine on\n\
    SSLProxyEngine on\n\
    SSLProxyVerify on\n\
    SSLProxyCACertificateFile \"{ca_path}\"\n\
    SSLCertificateFile \"{crt_path}\"\n\
    SSLCertificateKeyFile \"{key_path}\"\n\
    <FilesMatch \"\.(cgi|shtml|phtml|php)$\">\n\
        SSLOptions +StdEnvVars\n\
    </FilesMatch>\n\
    <Directory \"/usr/local/apache2/cgi-bin\">\n\
        SSLOptions +StdEnvVars\n\
    </Directory>\n\
    <Directory \"/usr/lib/cgi-bin\">\n\
        SSLOptions +StdEnvVars\n\
    </Directory>\n\
    BrowserMatch \"MSIE [2-5]\" nokeepalive ssl-unclean-shutdown downgrade-1.0 force-response-1.0\n"


def add_customLog(value):
    return f"CustomLog {value}\n"

def add_errorLog(value):
    return f"ErrorLog {value}\n"

def add_transferLog(value):
    return f"TransferLog {value}\n"

def add_serverAdmin(email):
    return f"ServerAdmin {email}\n"

def add_documentRoot(path):
    return f"DocumentRoot {path}\n"

def add_vhost(host, port, content):
    return f"\n\
    <VirtualHost {host}:{port}>\n\
    {content}\n\
    </VirtualHost>\n"

def disable_cache_set_Cache_Control():
    return 'Header set Cache-Control "max-age=0, no-store, no-cache, must-revalidate"\nHeader set Pragma "no-cache"\nHeader set Expires "Wed, 21 Oct 2015 07:28:00 GMT"\n'
