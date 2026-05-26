#!/bin/bash

# NOTE: Run this script like this:
# ./scripts/replay.sh --experiment 1 --deployments 1,2,5,7

# default values
experiment_id=""
database="central.db"
deployments=()

OPTIONS=$(getopt -o e: --long experiment:,database:,deployments: -- "$@")

if [ $? -ne 0 ]; then
    echo "Couldn't parse arguments."
    exit 1
fi

eval set -- "$OPTIONS"

while true; do
  case "$1" in
    -e|--experiment)
      experiment_id="$2"
      shift 2
      ;;
    --database)
      database="$2"
      shift 2
      ;;
    --deployments)
      IFS=',' read -r -a deployments <<< "$2"
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

echo "Experiment ID: $experiment_id"
echo "Database: $database"
# echo "Deployments: ${deployments[@]}"

if [ -z "$experiment_id" ]; then
  echo "Error: Argument 'experiment' should be given and should be a positive integer (>0)"
  exit 1
fi

# Function to handle SIGINT (Ctrl+C)
handle_sigint() {
    echo "Caught SIGINT (Ctrl+C), continuing with the next scripts..."
}

# Trap SIGINT and call handle_sigint
trap handle_sigint SIGINT

# Write env-setup config content on a tmp file
env=$(python3 get_env_config.py --experiment $experiment_id --database $database)
# Create Docker Network
python3 env-setup.py --createNetwork --config $env
# Check that container IPs are free to use
availability=$(python3 orchestrator.py --checkIPs --envConfig $env)
if [[ "$availability" == *"Unavailable" ]]; then
  echo "Error: Cannot run with the defined container names and IPs"
  exit 1
fi
# Add the domain names
sudo python3 env-setup.py --addHosts --config $env
# Create certificates and containers, then start containers
python3 env-setup.py --generate --createEnv --start --config $env
# Run tester on replay mode
if [ ${#deployments[@]} -eq 0 ]; then
    echo "No specific deployments were given!"
    python3 tester.py --mode replay --experiment $experiment_id --database $database
else
    echo "Deployments to replay: ${deployments[@]}"
    python3 tester.py --mode replay --experiment $experiment_id --database $database --deployments "${deployments[@]}"
fi
# Stop and delete containers, then delete Docker network
python3 env-setup.py --stop --deleteEnv --deleteNetwork --config $env
# Delete domain names
sudo python3 env-setup.py --deleteHosts --config $env
# Remove temporary environment configuration
rm $env