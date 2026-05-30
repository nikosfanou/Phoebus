from utils.SQLiteHandler import SQLiteHandler

from argparse import ArgumentParser
import json
import uuid
import os

class Constants:
    CENTRAL_DB = "central.db"
    CONFIGS_DIR = "configs"

# Get the command line arguments
def get_args():
    parser = ArgumentParser()
    parser.add_argument("-e", "--experiment", dest="experiment", required=True, type=int, help = "The experiment id of the env-setup configuration to retrieve.")
    parser.add_argument("-db", "--database", default = Constants.CENTRAL_DB, dest = "database", type=str, help = f"The database file where we store the execution results. Default value is {Constants.CENTRAL_DB}")
    args = parser.parse_args()
    return args

def get_env_config_by_experiment_id(experiment_id, database):
    with SQLiteHandler(database) as central_db:
        data = central_db.get_experiments_env_config_by_id(id = experiment_id)
        return data

def write_to_json(output, file):
    output_str = json.dumps(output, indent=4)
    with open(file, "w+") as fp:
        fp.write(output_str)

def generate_uid():
    return str(uuid.uuid4()).replace('-', '')

if __name__ == "__main__":
    args = get_args()
    env_config_content = get_env_config_by_experiment_id(experiment_id=args.experiment, database=args.database)
    if env_config_content:
        env_config_content = json.loads(env_config_content[0])
        uid = generate_uid()
        file = os.path.join(Constants.CONFIGS_DIR, f"env-setup-tmp-{uid}.json")
        write_to_json(output=env_config_content, file=file)
        print(file)
    else:
        exit(1)
