'''
This Python script builds the Database that will hold the execution results.
'''
from utils.SQLiteHandler import SQLiteHandler

from argparse import ArgumentParser

class Constants:
    CENTRAL_DB = "central.db"

# Get the command line arguments
def get_args():
    parser = ArgumentParser()
    parser.add_argument("-db", "--database", default = Constants.CENTRAL_DB, dest = "database", type=str, help = f"The database file where we store the execution results. Default value is {Constants.CENTRAL_DB}")
    args = parser.parse_args()
    return args

def main():
    args = get_args()
    # DB and Tables creation
    with SQLiteHandler(args.database) as db:
        db.create_experiments_table()
        db.create_deployments_table()
        db.create_browser_results_table()
        db.create_violation_reports_table()


if __name__ == "__main__":
    main()
    