#!/bin/bash

# NOTE: Run this script like this:
# ./scripts/run.sh --config configs/x-frame-options.json

# default values
config=""
env="configs/env-setup.json"
database="central.db"

OPTIONS=$(getopt -o c:e:db: --long config:,env:,database: -- "$@")

if [ $? -ne 0 ]; then
    echo "Couldn't parse arguments."
    exit 1
fi

eval set -- "$OPTIONS"

while true; do
  case "$1" in
    -c|--config)
      config="$2"
      shift 2
      ;;
    -e|--env)
      env="$2"
      shift 2
      ;;
    --database)
      database="$2"
      shift 2
      ;;
    --)
      shift
      break
      ;;
    *)
      echo "Invalid option: $1"
      exit 1
      ;;
  esac
done

echo "Argument config: $config"
echo "Argument env: $env"
echo "Database: $database"

if [ -z "$config" ]; then
  echo "Error: Argument 'config' should be given"
  exit 1
fi

# Initialize database
python3 central_db.py --database $database
# Create Docker Network
python3 env-setup.py --createNetwork --config $env
# Add containers and IPs
python3 orchestrator.py --addContainers --config $config --envConfig $env --database $database
# Add the domain names
sudo python3 env-setup.py --addHosts --config $env
# Run Orchestrator and Tester
python3 orchestrator.py --run --config $config --envConfig $env --database $database
# Delete domain names
sudo python3 env-setup.py --deleteHosts --config $env
# Delete Containers and IPs
python3 orchestrator.py --restore --config $config --envConfig $env --database $database