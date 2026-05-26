from argparse import ArgumentParser
import json
import os
import subprocess
import math
import docker
import ipaddress

class Constants:
    DEFAULT_CONTAINERS = ["example", "sub.example", "sub2.example", "crossexample", "sub.crossexample"]
    DEFAULT_CONFIG = './configs/orchestrator-conf.json'
    DEFAULT_ENV_CONFIG = './configs/env-setup.json'
    CENTRAL_DB = "central.db"

def list_to_str_repr(values):
    output = "["
    add_comma = False
    for value in values:
        output += ("," if add_comma is True else "") + value
        add_comma = True
    output += "]"
    return output

def create_containers(default_containers, threads):
    containers = default_containers.copy()
    for thread in range(1, threads):
        example = 'example' + str(thread + 1)
        crossexample = 'crossexample' + str(thread + 1)
        containers.append(example)
        containers.append('sub.' + example)
        containers.append('sub2.' + example)
        containers.append(crossexample)
        containers.append('sub.' + crossexample)
    return containers

def get_unavailable_ips(docker_client, network_name):
    allocated_ips = []
    # Collect the allocated IP addresses in the network
    for container in docker_client.containers.list(all=True):
        if network_name in container.attrs['NetworkSettings']['Networks']:
            # for all containers IPs ['IPAMConfig']['IPv4Address']
            # for active containers IPs ['IPAddress']
            allocated_ips.append(container.attrs['NetworkSettings']['Networks'][network_name]['IPAMConfig']['IPv4Address'])
    return allocated_ips

def get_unavailable_containers(docker_client, network_name):
    allocated_containers = []
    # Collect the allocated container names in the network
    for container in docker_client.containers.list(all=True):
        if network_name in container.attrs['NetworkSettings']['Networks']:
            # for all containers IPs ['IPAMConfig']['IPv4Address']
            # for active containers IPs ['IPAddress']
            allocated_containers.append(container.name)
    return allocated_containers

def get_available_ips(network_name, max):
    count = 0
    if count >= max: return []

    client = docker.from_env()
    network = client.networks.get(network_name)
    subnet = network.attrs['IPAM']['Config'][0]['Subnet']

    allocated_ips = get_unavailable_ips(docker_client=client, network_name=network_name)
    available_ips = []

    # Iterate over all possible IP addresses in the subnet
    for ip in ipaddress.IPv4Network(subnet):
        if str(ip) not in allocated_ips:
            available_ips.append(str(ip))
            count += 1
            if count == max:
                break

    return available_ips

def check_IPs_availability(network_name, ips):
    availability_flag = True
    client = docker.from_env()
    allocated_ips = get_unavailable_ips(docker_client=client, network_name=network_name)
    for ip in ips:
        if ip in allocated_ips:
            print(f"IP address: {ip} is not available!")
            availability_flag = False
    return availability_flag

def check_containers_availability(network_name, containers):
    availability_flag = True
    client = docker.from_env()
    allocated_containers = get_unavailable_containers(docker_client=client, network_name=network_name)
    for container in containers:
        if container in allocated_containers:
            print(f"Container name: {container} is not available!")
            availability_flag = False
    return availability_flag

def check_availability(filename):
    configuration = None
    with open(filename, "r") as fp:
        configuration = json.load(fp)
    if configuration is None:
        print(f"Could not open file: {filename}")
        exit(1)
    network_name = configuration['docker']['network']
    containers = list(configuration['docker']['containers'].keys())
    ips = list(configuration['docker']['containers'].values())
    ws_server = configuration['docker']['websocket-server']
    containers.append(ws_server['name'])
    ips.append(ws_server['ip'])
    return check_IPs_availability(network_name=network_name, ips=ips) and check_containers_availability(network_name=network_name, containers=containers)

def write_containers_to_conf(filename, threads, default_containers):
    containers_dict = {}
    configuration = None
    with open(filename, "r") as fp:
        configuration = json.load(fp)
    
    if configuration is None:
        print(f"Could not open file: {filename}")
        exit(1)
    
    # e.g. for 2 containers create example2 too
    containers = create_containers(default_containers=default_containers, threads=threads)
    # search docker network available ips
    ip_addresses = get_available_ips(network_name=configuration['docker']['network'], max = threads * len(default_containers) + 3)
    # assign ip address on websocket server of the containers
    configuration['docker']['websocket-server']['ip'] = ip_addresses[-1]
    
    ip_addresses = ip_addresses[2:len(ip_addresses)-1] # omit the first 2 ips as they are already used (gateway & stuff)
    if len(ip_addresses) < len(containers):
        print(f"Couldn't assign {len(containers)} ip addresses in this Docker network ({configuration['docker']['network']}). Could only assign {len(ip_addresses)}!")

    # create the containers dictionary on env-setup
    for index in range(0, len(containers)):
        containers_dict[containers[index]] = ip_addresses[index]
    
    configuration['docker']['containers'] = containers_dict

    # update the containers lists on mount and copy fields based on given threads
    mount_list = configuration['docker']['mount']
    copy_list = configuration['docker']['copy']
    for copy_obj in copy_list:
        if copy_obj['containers'] == "all" or type(copy_obj['containers']) is not list: continue
        for container in copy_obj['containers'].copy():
            for thread in range(1, threads):
                copy_obj['containers'].append(container + str(thread + 1))

    for mount_obj in mount_list:
        if mount_obj['containers'] == "all" or type(mount_obj['containers']) is not list: continue
        for container in mount_obj['containers'].copy():
            for thread in range(1, threads):
                mount_obj['containers'].append(container + str(thread + 1))
    
    with open(filename, "w") as fp:
        json.dump(configuration, fp, indent=4)

    return

def restore_config(filename, default_containers):
    print(f"Restoring {filename}...")
    data = None
    with open(filename, "r") as fp:
        data = json.load(fp)
    
    data['docker'].pop('containers')
    data['docker']['websocket-server'].pop('ip')
    mount_list = data['docker']['mount'].copy()
    copy_list = data['docker']['copy'].copy()
    copy_set = set()
    mount_set = set()

    for copy_index, copy_obj in enumerate(copy_list):
        if copy_obj['containers'] == "all" or type(copy_obj['containers']) is not list: continue
        for container in copy_obj['containers']:
            for default_container in default_containers:
                if container.startswith(default_container):
                    copy_set.add(default_container)
        data['docker']['copy'][copy_index]['containers'] = list(copy_set)
        copy_set = set()
    
    for mount_index, mount_obj in enumerate(mount_list):
        if mount_obj['containers'] == "all" or type(mount_obj['containers']) is not list: continue
        for container in mount_obj['containers']:
            for default_container in default_containers:
                if container.startswith(default_container):
                    mount_set.add(default_container)
        data['docker']['mount'][mount_index]['containers'] = list(mount_set)
        mount_set = set()

    with open(filename, "w") as fp:
        json.dump(data, fp, indent=4)

def orchestrate(threads, tests, envConfig, database):
    remaining_tests = len(tests)
    remaining_threads = threads
    tests_per_tester = remaining_tests / remaining_threads
    tester_configs = []

    start = 0
    end = math.ceil(tests_per_tester)
    if start >= end: return

    processes = []
    # orchestrate the tests in the different threads
    # ! won't support multiple use-cases in parallel finally, use threads=1 always
    for thread in range(1, threads+1):
        test_list = []
        for index in range(start, end, 1):
            test_list.append(tests[index])
        
        test_list_str = json.dumps(test_list, indent=4)
        tester_config_name = f"tester_config{str(thread)}.json"
        with open(tester_config_name, "w+") as fp:
            fp.write(test_list_str)
        tester_configs.append(tester_config_name)

        example = 'example' + (str(thread) if thread > 1 else "")
        crossexample = 'crossexample' + (str(thread) if thread > 1 else "")
        tester_command = f"python3 tester.py --example {example} --crossexample {crossexample} --mainConfig {tester_config_name} --config {envConfig} --database {database}"
        print(tester_command)
        process = subprocess.Popen(['gnome-terminal', '--wait', '-e', f'{tester_command}'])
        processes.append(process)

        remaining_threads += -1
        if remaining_threads <= 0: break
        remaining_tests += start - end
        start = end
        tests_per_tester = remaining_tests / remaining_threads
        end += math.ceil(tests_per_tester)

    # wait for tester instances to finish
    for process in processes:
        process.wait()
    
    # clean the tester intermediate configurations
    for tester_config in tester_configs:
        subprocess.run(f"rm {tester_config}", shell=True)


def create_network(envConfig):
    subprocess.run(f"python3 env-setup.py --createNetwork --config {envConfig}", shell=True)

def generate_certificates(envConfig):
    subprocess.run(f"python3 env-setup.py --generate --config {envConfig}", shell=True)

def setup_environment(envConfig):
    subprocess.run(f"python3 env-setup.py --createEnv --config {envConfig}", shell=True)
    subprocess.run(f"python3 env-setup.py --start --config {envConfig}", shell=True)

def delete_environment(envConfig):
    subprocess.run(f"python3 env-setup.py --stop --config {envConfig}", shell=True)
    subprocess.run(f"python3 env-setup.py --deleteEnv --config {envConfig}", shell=True)
    subprocess.run(f"python3 env-setup.py --deleteNetwork --config {envConfig}", shell=True)

def get_args():
    parser = ArgumentParser()
    # Configs
    parser.add_argument("-c", "--config", default = Constants.DEFAULT_CONFIG, dest = "config", help = f"The configuration file. Default value is {Constants.DEFAULT_CONFIG}")
    parser.add_argument("-e", "--envConfig", default = Constants.DEFAULT_ENV_CONFIG, dest = "envConfig", help = f"The environment setup configuration file. Default value is {Constants.DEFAULT_ENV_CONFIG}")
    parser.add_argument("-db", "--database", default = Constants.CENTRAL_DB, dest = "database", type=str, help = f"The database file where we store the execution results. Default value is {Constants.CENTRAL_DB}")
    # Modes
    parser.add_argument("-r", "--run", action = 'store_const', default = False, const = True, dest = "run", help = "Split and run tests on tester!")
    parser.add_argument("-a", "--addContainers", action = 'store_const', default = False, const = True, dest = "addContainers", help = "Based on threads, create a dict with the necessary containers and available IPs.")
    parser.add_argument("-re", "--restore", action = 'store_const', default = False, const = True, dest = "restore", help = "Restore the environment setup configuration.")
    parser.add_argument("-chips", "--checkIPs", action = 'store_const', default = False, const = True, dest = "checkIPs", help = "Checks if the IPs provided from the env-setup configuration are available to use.")
    args = parser.parse_args()
    if not args.run and not args.addContainers and not args.restore and not args.checkIPs:
        parser.error("No mode was selected. Supported modes: run, addContainers, restore, checkIPs.")
    return args

if __name__ == "__main__":
    args = get_args()
    print(args)

    if args.checkIPs:
        if not check_availability(filename=args.envConfig):
            print("Unavailable") # for replay.sh to perform check
            exit(1)
        exit(0)
    
    if not os.path.exists(args.config):
        print("[ERROR] Couldn't locate file: ", args.config)
        print("Exiting...")
        exit(1)
    
    with open(args.config, "r") as fp:
        tests = json.load(fp)
    
    threads = 1

    if not tests or (type(tests) != list and type(tests) != dict):
        print("[ERROR] No tests are given!")
        print("Exiting...")
        exit(1)

    if type(tests) is dict:
        tests = [tests]

    # network should already been created in order to assign available ips on this subnet
    if args.addContainers:
        write_containers_to_conf(filename=args.envConfig, threads=threads, default_containers=Constants.DEFAULT_CONTAINERS)
    if args.run:
        generate_certificates(envConfig=args.envConfig)
        setup_environment(envConfig=args.envConfig)
        orchestrate(threads=threads, tests=tests, envConfig=args.envConfig, database=args.database)
        delete_environment(envConfig=args.envConfig)
    if args.restore:
        restore_config(filename=args.envConfig, default_containers=Constants.DEFAULT_CONTAINERS)