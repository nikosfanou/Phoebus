from argparse import ArgumentParser
import subprocess
import os
import json

'''
An initial, short, non-comprehensive check of the env config.
Returns False if configuration is wrong, else True.
'''
def check_config(configuration):
    print("Checking Docker Configuration...")
    config = configuration['docker']
    result = True
    if not config['network'] or type(config['network']) != str:
        print("[ERROR] Please specify a valid Network Name on the field `name`.")
        result = False
    if not config['subnet'] or type(config['subnet']) != str:
        print("[ERROR] Please specify a valid Network Subnet on the field `subnet`.")
        result = False
    if not config['image'] or type(config['image']) != str:
        print("[ERROR] Please specify a valid Docker Image on the field `image`.")
        result = False
    if config['mount'] != [] and (not config["mount"] or type(config["mount"]) != list):
        print("[ERROR] Please specify a valid list of dictionaries on the field `mount`. Format: [{\"source-path\" : \"from-host-folder\",\"target-path\" : \"to-container-folder\",\"source-file\" : \"from-host-file\",\"dest-file\" : \"to-container-file\"}]")
        result = False
    if result:
        print("Your configuration is fine!")
    else:
        print("Please adjust your configuration and try again!")
    return result

'''
Returns a list of the docker networks in a json format.
[NOTE] --filter option also finds substrings, e.g. name='my-ne' will find network named my-net.
Although it helps on optimization as not all networks are checked.
'''
def get_networks(name, verbose):
    arg = 'name=%s' % name.strip()
    template = '''{{json .}}'''
    networks = subprocess.run(f'docker network ls --format "{template}" --filter {arg}', shell=True, capture_output=True, text=True)
    if verbose:
        print("Your Docker Networks:")
        print(subprocess.run('docker network ls', shell=True, capture_output=True, text=True).stdout)
    output = networks.stdout.strip().split('\n')
    if '' in output:
        output.remove('')
    return [json.loads(json_str) for json_str in output]

'''
Returns a list of the docker containers in a json format.
Containers in different Docker Networks cannot have the same name so we don't use --filter here.
'''
def get_containers(verbose):
    template = '''{{json .}}'''
    containers = subprocess.run(f'docker ps -a --format "{template}"', shell=True, capture_output=True, text=True)
    if verbose:
        print("Your Docker Containers:")
        print(subprocess.run('docker ps a', shell=True, capture_output=True, text=True).stdout)
    output = containers.stdout.strip().split('\n')
    if '' in output:
        output.remove('')
    return [json.loads(json_str) for json_str in output]

'''
Asks user if he wants to proceed. If user types 'y' we continue, if he types 'n' we exit, else we ask again!
'''
def ask_user():
    while(True):
        answer = input('Do you want to proceed? [y/n]')
        if answer == 'y': break
        if answer == 'n':
            print('Exiting...')
            exit(0)

def create_docker_network(configuration, verbose, force):
    print("Some checks for Docker Network...")
    config = configuration['docker']
    create_net = True

    # Check if specified network is already in use
    in_use_networks = get_networks(config['network'], verbose)
    in_use_network_names = [network['Name'] for network in in_use_networks]
    if config['network'] in in_use_network_names:
        print("[WARNING] A network named '%s' already exists. Won't try to create a new one!" % config['network'])
        create_net = False
        if not force:
            ask_user()
    
    # If we reach here we are probably okay!
    if create_net is True:
        print('Creating Docker Network "%s" with subnet "%s"...' % (config['network'], config['subnet']))
        net_process = subprocess.run(['docker', 'network', 'create', config['network'], '--subnet', config['subnet'] ], capture_output=True, text=True)
    
    print("Docker Network is set!")
    return


'''
Creates the specified docker network and its containers if they are not already in use
'''
def setup_docker_environment(configuration, verbose, force):
    print("Some checks for Docker Containers...")
    config = configuration['docker']
    create_containers = []
    
    # Check if specified containers are already in use
    container_names = list(config['containers'].keys())
    in_use_containers = get_containers(verbose)
    in_use_container_names = [container['Names'] for container in in_use_containers]
    for name in container_names:
        if name in in_use_container_names:
            print("[WARNING] A container named '%s' already exists. Won't try to create a new one!" % name)
            if not force:
                ask_user()
        else:
            create_containers.append(name)

    # If we reach here we are probably okay!
    for container in create_containers:
        print('Creating Docker Container "%s" with IP address "%s"...' % (container, config['containers'][container]))

        args = ['docker', 'run', '-itd', '--name', container, '--network', config['network'],
                '--ip', config['containers'][container]]
        
        for path_dict in config['mount']:
            if path_dict['containers'] != "all" and container not in path_dict['containers']:
                continue
            
            abs_source_path = os.path.abspath(path_dict['source-path'])
            source_path = os.path.join(abs_source_path, container)
            if not os.path.exists(source_path):
                os.makedirs(source_path)
            
            for default_file in path_dict.get('default-files', []):
                abs_default_file = os.path.abspath(default_file)
                subprocess.run(f"cp -r {abs_default_file} {source_path}", shell=True)
                        
            if path_dict['source-file']:
                source_path = os.path.join(source_path, path_dict['source-file'])
                if not os.path.exists(source_path):
                    fd = os.open(path = source_path, mode = 775, flags = os.O_CREAT)
                    os.close(fd)
            
            container_path = path_dict['target-path'] if not path_dict['target-file'] else os.path.join(path_dict['target-path'], path_dict['target-file'])
            args.append('--mount')
            args.append('type=bind,source=%s,target=%s' % (source_path, container_path))
        args.append(config['image'])
        # create the container
        con_process = subprocess.run(args, capture_output=True, text=True)
        
        # copy any other needed files
        for path_dict in config['copy']:
            if path_dict['containers'] != "all" and container not in path_dict['containers']:
                continue
            abs_source_path = os.path.abspath(path_dict['source-path'])
            con_process = subprocess.run(f"docker cp {abs_source_path} {container}:{path_dict['target-path']}", shell=True)
    
    print("Docker Containers are set!")
    return

'''
Copies to the correct folders all the files that the localhost server needs to run
'''
def setup_local_environment(configuration):
    for files_dict in configuration['localhost']['copy']:
        src = os.path.abspath(files_dict['source-path'])
        target = os.path.normpath(files_dict['target-path'])
        if files_dict.get('folder', False):
            subprocess.run(f'cp -r {src} {target}', shell=True)
        else:
            subprocess.run(f'cp {src} {target}', shell=True)
    print("Copied needed files for localhost server")

'''
Restart server for changes to take effect
'''
def restart_container(container):
    subprocess.run(f"docker exec {container} apachectl -k restart", shell=True)

'''
Restart all apache servers
'''
def restart_all_containers(configuration):
    container_names = list(configuration['docker']['containers'].keys())
    for container in container_names:
        restart_container(container)

def copy_certs(configuration):
    ssl_info = configuration['ssl']
    certs_path = os.path.abspath(ssl_info['certs-path'])
    ca_crt = os.path.join(certs_path, ssl_info['CA'] + '.pem')
    for container in configuration['docker']['containers'].keys():
        folder = os.path.join(certs_path, container)
        key = os.path.join(folder, 'server.key')
        crt = os.path.join(folder, 'server.crt')
        # Copy CA certificate in all containers
        subprocess.run(f"docker cp {ca_crt} {container}:{ssl_info['target-path']['docker']}", shell=True)
        # Copy Certificates and keys of every container
        subprocess.run(f"docker cp {crt} {container}:{ssl_info['target-path']['docker']}", shell=True)
        subprocess.run(f"docker cp {key} {container}:{ssl_info['target-path']['docker']}", shell=True)
    
    # now copy also on localhost
    localhost_folder = os.path.join(certs_path, 'localhost')
    localhost_key = os.path.join(localhost_folder, 'server.key')
    localhost_crt = os.path.join(localhost_folder, 'server.crt')
    target_path = ssl_info['target-path']['localhost']
    if not os.path.exists(target_path):
        os.makedirs(target_path)
    subprocess.run(f"cp {ca_crt} {target_path}", shell=True)
    subprocess.run(f"cp {localhost_key} {target_path}", shell=True)
    subprocess.run(f"cp {localhost_crt} {target_path}", shell=True)
    print("Certificates and keys are copied for docker containers and localhost server")

'''
Generate a CA and certificates/keys for each container
'''
def generate_certs(configuration):
    print("Generating certificates and keys ...")
    create_container_certs(configuration)
    create_ws_cert(configuration)
    create_localhost_cert(configuration)
    print("Certificates and keys are generated!")

'''
Creates a self-signed CA
'''
def create_CA(configuration):
    print("Generating a self-signed Certificate Authority...")
    ssl_info = configuration['ssl']
    certs_path = os.path.abspath(ssl_info['certs-path'])
    if not os.path.exists(certs_path):
        os.makedirs(certs_path)
    key = os.path.join(certs_path, ssl_info['CA'] + '.key')
    crt = os.path.join(certs_path, ssl_info['CA'] + '.pem')
    passphrase = ssl_info['CA-passphrase']
    info = ssl_info["CA-info"]
    # Generate a private key
    subprocess.run(f"openssl genrsa -des3 -passout pass:'{passphrase}' -out {key} 2048", shell=True)
    # Generate root certificate
    command = f"openssl req -x509 -new -nodes -key {key} -sha256 -days 825 -out {crt} -passin pass:'{passphrase}' -subj \"{info}\""
    subprocess.run(command, shell=True)

'''
Creates certificates and keys for the servers and signs them with the previously generated CA
'''
def create_container_certs(configuration):
    ssl_info = configuration['ssl']
    certs_path = os.path.abspath(ssl_info['certs-path'])
    ca_key = os.path.join(certs_path, ssl_info['CA'] + '.key')
    ca_crt = os.path.join(certs_path, ssl_info['CA'] + '.pem')
    ca_pass = ssl_info['CA-passphrase']
    for container in configuration['docker']['containers'].items():
        name, ip = container
        folder = os.path.join(certs_path, name)
        if not os.path.exists(folder):
            os.makedirs(folder)
        key = os.path.join(folder, 'server.key')
        crt = os.path.join(folder, 'server.crt')
        csr = os.path.join(folder, 'server.csr')
        ext = os.path.join(folder, 'server.ext')
        domain = name + '.com'
        info = ssl_info['servers-info'].replace('{DOMAIN}', domain)
        # Generate a private key
        subprocess.run(f"openssl genrsa -out {key} 2048", shell=True)
        # Create a certificate-signing request
        subprocess.run(f"openssl req -new -key {key} -out {csr} -subj \"{info}\"", shell=True)
        # Create a config file for the extensions
        lcommand = f">{ext} cat <<-EOF\nauthorityKeyIdentifier=keyid,issuer\nbasicConstraints=CA:FALSE\nkeyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment\nsubjectAltName = @alt_names\n[alt_names]\nDNS.1 = {domain}\nIP.1 = {ip}\nEOF"
        subprocess.run(lcommand, shell=True) # capture_output=True, text=True
        # Create the signed certificate
        command = f"openssl x509 -req -in {csr} -CA {ca_crt} -CAkey {ca_key} -CAcreateserial -out {crt} -days 825 -sha256 -extfile {ext} -passin pass:'{ca_pass}'"
        subprocess.run(command, shell=True)

'''
Creates certificates and keys for the localhost apache and websocket servers and signs them with the previously generated CA
'''
def create_localhost_cert(configuration):
    ssl_info = configuration['ssl']
    certs_path = os.path.abspath(ssl_info['certs-path'])
    ca_key = os.path.join(certs_path, ssl_info['CA'] + '.key')
    ca_crt = os.path.join(certs_path, ssl_info['CA'] + '.pem')
    ca_pass = ssl_info['CA-passphrase']
    name = "localhost"
    ip = "127.0.0.1"
    folder = os.path.join(certs_path, name)
    if not os.path.exists(folder):
        os.makedirs(folder)
    key = os.path.join(folder, 'server.key')
    crt = os.path.join(folder, 'server.crt')
    csr = os.path.join(folder, 'server.csr')
    ext = os.path.join(folder, 'server.ext')
    info = ssl_info['servers-info'].replace('{DOMAIN}', name)
    # Generate a private key
    subprocess.run(f"openssl genrsa -out {key} 2048", shell=True)
    # Create a certificate-signing request
    subprocess.run(f"openssl req -new -key {key} -out {csr} -subj \"{info}\"", shell=True)
    # Create a config file for the extensions
    lcommand = f">{ext} cat <<-EOF\nauthorityKeyIdentifier=keyid,issuer\nbasicConstraints=CA:FALSE\nkeyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment\nsubjectAltName = @alt_names\n[alt_names]\nDNS.1 = {name}\nIP.1 = {ip}\nEOF"
    subprocess.run(lcommand, shell=True)
    command = f"openssl x509 -req -in {csr} -CA {ca_crt} -CAkey {ca_key} -CAcreateserial -out {crt} -days 825 -sha256 -extfile {ext} -passin pass:'{ca_pass}'"
    subprocess.run(command, shell=True)

'''
Creates certificates and keys for the dockerized websocket server and signs them with the previously generated CA
'''
def create_ws_cert(configuration):
    ssl_info = configuration['ssl']
    certs_path = os.path.abspath(ssl_info['certs-path'])
    ca_key = os.path.join(certs_path, ssl_info['CA'] + '.key')
    ca_crt = os.path.join(certs_path, ssl_info['CA'] + '.pem')
    ca_pass = ssl_info['CA-passphrase']
    name = configuration['docker']['websocket-server']['name']
    ip = configuration['docker']['websocket-server']['ip']
    folder = os.path.join(certs_path, name)
    if not os.path.exists(folder):
        os.makedirs(folder)
    key = os.path.join(folder, 'server.key')
    crt = os.path.join(folder, 'server.crt')
    csr = os.path.join(folder, 'server.csr')
    ext = os.path.join(folder, 'server.ext')
    info = ssl_info['servers-info'].replace('{DOMAIN}', ip) # Note here we dont create domain = name + ".com", but we use only the IP address
    # Generate a private key
    subprocess.run(f"openssl genrsa -out {key} 2048", shell=True)
    # Create a certificate-signing request
    subprocess.run(f"openssl req -new -key {key} -out {csr} -subj \"{info}\"", shell=True)
    # Create a config file for the extensions
    # NOTE: here we dont give DNS alternative name for websocket server. We use only its IP to communicate with this server. To be able to serve requests to localhost however we need to also add the localhost domain name and its IP here, and also to expose the ports on localhost, so that the requests can be redirected to the websocket server!
    lcommand = f">{ext} cat <<-EOF\nauthorityKeyIdentifier=keyid,issuer\nbasicConstraints=CA:FALSE\nkeyUsage = digitalSignature, nonRepudiation, keyEncipherment, dataEncipherment\nsubjectAltName = @alt_names\n[alt_names]\nIP.1 = {ip}\nIP.2 = 127.0.0.1\nDNS.1 = localhost\nEOF"
    subprocess.run(lcommand, shell=True)
    command = f"openssl x509 -req -in {csr} -CA {ca_crt} -CAkey {ca_key} -CAcreateserial -out {crt} -days 825 -sha256 -extfile {ext} -passin pass:'{ca_pass}'"
    subprocess.run(command, shell=True)

def build_and_start_ws_server(configuration):
    network = configuration['docker']["network"]
    ws_info = configuration['docker']['websocket-server']
    name = ws_info['name']
    ip = ws_info['ip']
    port = ws_info['port']
    ssl_port = ws_info['ssl_port']
    dockerfile_path = os.path.abspath(ws_info['dockerfile'])
    dockerfile = os.path.join(dockerfile_path, 'Dockerfile')
    ca = configuration['ssl']['CA']
    certs_path = os.path.abspath(configuration['ssl']['certs-path'])
    ws_certs_path = os.path.join(certs_path, name)
    ca_filename = ca + '.pem'
    ca_path = os.path.join(certs_path, ca_filename)

    print(f"Building {name} docker image...")
    build_command = f"docker build -f {dockerfile} -t {name} {dockerfile_path}"
    subprocess.run(build_command, shell=True)
    
    print(f"Running {name} docker container...")
    start_command = f"docker run -e HOST={ip} -e CA_NAME={ca} -e PORT={port} -e SSL_PORT={ssl_port} -p {port}:{port} -p {ssl_port}:{ssl_port} -v {ws_certs_path}:/certs -v {ca_path}:/{ca_filename} -itd --network {network} --ip {ip} --name {name} {name}"
    subprocess.run(start_command, shell=True)
    print(f"{name} is set!")

def delete_ws_server_image(configuration):
    image = configuration['docker']['websocket-server']['name']
    subprocess.run(f'docker rmi {image}', shell=True)


'''
Starts the Docker containers specified in configuration
'''
def start_containers(configuration):
    containers = list(configuration['docker']['containers'].keys())
    ws_server = configuration['docker']['websocket-server']['name']
    containers.append(ws_server)

    print("Starting Docker containers...")
    for container in containers:
        output = subprocess.run(f'docker start {container}', shell=True)
        if container != ws_server:
            output = subprocess.run(f'docker exec {container} chown -R :www-data /usr/local/apache2/api', shell=True)
            # output = subprocess.run(f'docker exec {container} chmod -R 755 /usr/local/apache2/api', shell=True)
    print('Docker containers are started!')

'''
Stops the Docker containers specified in configuration
'''
def stop_containers(configuration):
    containers = list(configuration['docker']['containers'].keys())
    containers.append(configuration['docker']['websocket-server']['name'])

    print('Stopping Docker containers...')
    for container in containers:
        output = subprocess.run(f'docker stop {container}', shell=True)
    print('Docker containers are stopped!')

'''
Delete the Docker containers specified in configuration
'''
def delete_containers(configuration):
    containers = list(configuration['docker']['containers'].keys())
    containers.append(configuration['docker']['websocket-server']['name'])

    print('Deleting Docker containers...')
    for container in containers:
        output = subprocess.run(f'docker rm {container}', shell=True)
    print('Finished Docker containers deletion!')

'''
Delete the Docker network specified in configuration
'''
def delete_network(configuration):
    print('Deleting Docker Network...')
    network = configuration['docker']['network']
    output = subprocess.run(f'docker network rm {network}', shell=True)
    print('Finished Docker network deletion!')

'''
Enable localhost server
'''
def start_local_server(configuration):
    print("Starting localhost server...")
    file = configuration['localhost']['conf-file']
    subprocess.run('a2dismod mpm_event', shell=True)
    subprocess.run(f'a2ensite {file}', shell=True)
    subprocess.run('sudo systemctl restart apache2.service', shell=True)

'''
Disable localhost site
'''
def stop_local_server(configuration):
    print("Stopping localhost server...")
    file = configuration['localhost']['conf-file']
    subprocess.run(f'a2dissite {file}', shell=True)
    subprocess.run('a2enmod mpm_event', shell=True)
    subprocess.run('sudo systemctl restart apache2.service', shell=True)

'''
Delete every file we copied for localhost server
'''
def delete_local_server(configuration):
    print('Deleting localhost server needed files...')
    for files_dict in configuration['localhost']['copy']:
        if files_dict.get('skip-delete'): continue
        target = os.path.normpath(files_dict['target-path'])
        subprocess.run(f'rm -rf {target}', shell=True)
    print('Finished localhost server files deletion!')

def delete_apache_running_folders():
    print("Deleting every file in paths `./apache-files`, `./apache-configs` and `./apache-prepends`")
    subprocess.run(f"rm -r ./apache-files/*", shell=True)
    subprocess.run(f"rm -r ./apache-configs/*", shell=True)
    subprocess.run(f"rm -r ./apache-prepends/*", shell=True)

'''
Appends the domain names and their ip addresses if they do not exist, else it uncomments the corresponding lines.
NOTE: For the websocket server we do not have a domain name so we don't add it here.
'''
def add_on_hosts(configuration):
    filename = "/etc/hosts"
    for container in configuration['docker']['containers'].items():
        name, ip = container 
        pattern = ip + "\t" + name + ".com"

        # Check if pattern exists in the file
        command_check = f"grep -q '{pattern}' {filename}"
        result = subprocess.run(command_check, shell=True)

        if result.returncode == 0:
            # Pattern exists, uncomment or perform necessary operations
            command_uncomment = f"sed -i '/{pattern}/s/^#//' {filename}"
            subprocess.run(command_uncomment, shell=True)
        else:
            # Pattern doesn't exist, append it or perform necessary operations
            with open(filename, "a") as file:
                file.write(f"\n{pattern}")

'''
Does not delete the lines. Just comments or uncomments them.
'''
def delete_from_hosts(configuration):
    filename = "/etc/hosts"
    for container in configuration['docker']['containers'].items():
        name, ip = container 
        pattern = ip + "\t" + name
        command_comment = f"sed -i '/{pattern}/s/^/#/' {filename}"
        subprocess.run(command_comment, shell=True)

def set_php_config_on_containers(configuration):
    for host in configuration['docker']['containers']:
        set_php_config(host=host)

def set_php_config_on_localhost():
    set_php_config(host='localhost')

# Set configuration for the PHP running in the server (e.g., prepend prepend.php in the beginning of each php file to set deployments)
def set_php_config(host):
    if host != 'localhost':
        arg = f'--container {host}'
    else:
        arg = ''
    res = subprocess.run(f'./scripts/get_php_apache_conf_dir.sh {arg}', shell=True, capture_output=True)
    if res.returncode != 0:
        print("[ERROR] Message from: ./scripts/get_php_apache_conf_dir.sh")
        print(res.stderr.decode())
        print(f'[WARN] PHP config is not set for {host}')
        return False
    
    path = res.stdout.decode()
    if host != 'localhost':
        res2 = subprocess.run(f'docker cp ./default-files/configs/99-php-custom.ini {host}:{path}', shell=True)
    else:
        res2 = subprocess.run(f'cp ./default-files/configs/99-php-custom-localhost.ini {path}', shell=True)
    return True if res2.returncode == 0 else False

def unset_localhost_php_config():
    res = subprocess.run(f'./scripts/get_php_apache_conf_dir.sh', shell=True, capture_output=True)
    if res.returncode != 0:
        print("[ERROR] Message from: ./scripts/get_php_apache_conf_dir.sh")
        print(res.stderr.decode())
        print(f'[WARN] PHP config is not unset for localhost')
        return False
    path = res.stdout.decode().strip()
    full_path = os.path.join(path, '99-php-custom-localhost.ini') # php config location on host
    res2 = subprocess.run(f'rm {full_path}', shell=True)
    return True if res2.returncode == 0 else False

'''
Get the command line arguments
'''
def get_args():
    parser = ArgumentParser()
    # Modes
    parser.add_argument("-ce", "--createEnv", action = 'store_const', default = False, const=True, dest = "createEnv", help = "Create both the Docker and Local environment needed to run the tests based on a configuration file. Default value is False.")
    parser.add_argument("-cn", "--createNetwork", action = 'store_const', default = False, const=True, dest = "createNet", help = "Create both the Docker and Local environment needed to run the tests based on a configuration file. Default value is False.")
    parser.add_argument("-ah", "--addHosts", action = 'store_const', default = False, const=True, dest = "addHosts", help = "Opens /etc/hosts and adds containers and their IPs.")
    parser.add_argument("-g", "--generate", action = 'store_const', default = False, const=True, dest = "generate", help = "Create the needed certificates and keys. Default value is False.")
    parser.add_argument("-ca", "--create_ca", action = 'store_const', default = False, const=True, dest = "create_ca", help = "Create a self-signed Certificate Authority. Default value is False.")
    parser.add_argument("-s", "--start", action = 'store_const', default = False, const = True, dest = "start", help = "Start Docker containers and localhost server. Default value is False.")
    parser.add_argument("-S", "--stop", action = 'store_const', default = False, const = True, dest = "stop", help = "Stop Docker containers and localhost server. Default value is False.")
    parser.add_argument("-de", "--deleteEnv", action = 'store_const', default = False, const = True, dest = "deleteEnv", help = "Delete the Docker containers and the files of the localhost server. Default value is False.")
    parser.add_argument("-dh", "--deleteHosts", action = 'store_const', default = False, const = True, dest = "deleteHosts", help = "Delete host info from /etc/hosts.")
    parser.add_argument("-dn", "--deleteNetwork", action = 'store_const', default = False, const = True, dest = "deleteNet", help = "Delete Docker network. Default value is False.")
    # Config
    parser.add_argument("-C", "--config", default = './configs/env-setup.json', const = './configs/env-setup.json', dest = "config", nargs = '?',  help = "The configuration file. Default value is ./configs/env-setup.json")
    # Options
    parser.add_argument("-v", "--verbose", action = 'store_const', default = False, const=True, dest = "verbose", help = "Print the output of the commands. Default value is False.")
    parser.add_argument("-f", "--force", action = 'store_const', default = False, const=True, dest = "force", help = "Force to always proceed when a container or network already exists. Default value is False.")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    # print(args)
    
    if not os.path.exists(args.config):
        print("Couldn't locate file: ", args.config)
        print("Exiting...")
        exit(0)

    configuration = None
    with open(args.config, "r") as fp:
        configuration = json.load(fp)

    if check_config(configuration) is False:
        print("Exiting...")
        exit(0)

    if args.create_ca:
        create_CA(configuration)
    if args.generate:
        # create certificates/keys for every server we will use
        generate_certs(configuration)
    if args.createNet:
        create_docker_network(configuration, args.verbose, args.force)
    if args.createEnv:
        # create network and the main containers
        setup_docker_environment(configuration, args.verbose, args.force)
        # copy certificates/keys to the main containers, also copy certificates/keys for localhost deployment
        copy_certs(configuration)
        # setup the localhost environment
        setup_local_environment(configuration)
        # create an auxiliary websocket server inside a docker container
        build_and_start_ws_server(configuration)
    if args.addHosts:
        # NOTE: These needs to be run with sudo as they add/modify/remove files to paths we don't have priviledges to do so!
        add_on_hosts(configuration)
        set_php_config_on_localhost()
    if args.start:
        start_containers(configuration)
        start_local_server(configuration)
        set_php_config_on_containers(configuration)
    if args.stop:
        stop_containers(configuration)
        stop_local_server(configuration)
    if args.deleteEnv:
        delete_containers(configuration)
        delete_ws_server_image(configuration)
        delete_local_server(configuration)
        delete_apache_running_folders()
    if args.deleteHosts:
        # NOTE: These needs to be run with sudo as they add/modify/remove files to paths we don't have priviledges to do so!
        delete_from_hosts(configuration)
        unset_localhost_php_config()
    if args.deleteNet:
        delete_network(configuration)
