'''
This Python script builds the Central Database that will hold all execution results.
'''
from utils.SQLiteHandler import SQLiteHandler

CENTRAL_DB = "central.db"

def main():
    # DB and Tables creation
    with SQLiteHandler(CENTRAL_DB) as db:
        db.create_experiments_table()
        db.create_deployments_table()
        db.create_browser_results_table()
        db.create_violation_reports_table()


if __name__ == "__main__":
    main()
    