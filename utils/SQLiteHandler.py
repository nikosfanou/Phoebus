import json
import os
import sqlite3

'''
Handles the needed queries to the database
'''
class SQLiteHandler():
    _abs_path = os.path.dirname(os.path.abspath(__file__))
    _db_default_folder = os.path.normpath(os.path.join(_abs_path, "../db")) # default folder

    def __init__(self, db_name, db_folder = None):
        folder = self._db_default_folder if db_folder is None else db_folder
        self._db_path = os.path.join(folder, db_name)
        self._con = None
   
    def connect(self):
        # open db
        self._con = sqlite3.connect(self._db_path, timeout=600)

    def __enter__(self):
        # Called when entering the "with" block
        if self._con is None:
            self.connect()
        return self

    def close(self):
        # close db
        if self._con is None:
            return
        try:
            self._con.close()
        finally:
            self._con = None
            self._db_path = None

    def __exit__(self, exc_type, exc, tb): # arguments of the context manager protocol
        # Called when exiting the "with" block
        self.close()

    def execute_query(self, query: str, args=None, return_id=False, many=False):
        if self._con is None:
            return False

        cursor = self._con.cursor()

        try:
            if args is None:
                cursor.execute(query)

            elif many:
                # args should be an iterable of tuples
                cursor.executemany(query, args)

            else:
                # args should be a single tuple
                cursor.execute(query, args)

            result = cursor.rowcount > 0

            last_row_id = None
            if return_id:
                last_row_id = cursor.lastrowid

            self._con.commit()

            return (result, last_row_id) if return_id else result
        except Exception as e:
            print(e)
        finally:
            cursor.close()
    
    def fetch_query(self, query: str, args=None, all: bool = False):
        if self._con is None:
            raise RuntimeError("Database connection is not initialized")

        cursor = self._con.cursor()

        try:
            if args is None:
                cursor.execute(query)
            else:
                cursor.execute(query, args)

            return cursor.fetchall() if all else cursor.fetchone()

        finally:
            cursor.close()

    def alter_table_add_column(self, table, column):
        null_arg = "" if column['can_be_null'] is True else " NOT NULL"
        query = f"ALTER TABLE {table}\n"
        query += f"ADD COLUMN {column['name']} {column['type']}{null_arg};"
        print(query)
        return self.execute_query(query=query)
    
    # can print either a json or a list of jsons
    def pretty_print(cls, db_data, file = None):
        if db_data is None:
            print(None)
            return
        
        pretty_str = json.dumps(db_data, indent = 2)

        if file is None:
            print(pretty_str)
            print('\n')
        else:
            with open(file, "w") as fp:
                fp.write(pretty_str)


    '''
    Functions and tables for generated values (Generator).
    '''
    def create_mechanism_table(self):
        query = "CREATE TABLE IF NOT EXISTS mechanisms (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    name TEXT NOT NULL,\
                    label TEXT\
				)"
        return self.execute_query(query=query)
    
    def drop_mechanism_table(self):
        query = "DROP TABLE IF EXISTS mechanisms"
        return self.execute_query(query=query)
    
    def insert_mechanism_table(self, mechanism_name, label=None):
        query = "INSERT INTO mechanisms (name, label) VALUES(?, ?)"
        return self.execute_query(query=query, args = (mechanism_name, label), return_id=True)
        
    def get_mechanism_table(self):
        query = "SELECT * FROM mechanisms"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_mechanism_ids(self):
        query = "SELECT id FROM mechanisms"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_mechanism_ids_names(self):
        query = "SELECT id, name FROM mechanisms"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_mechanism_by_id(self, id):
        query = f"SELECT * FROM mechanisms WHERE id={id}"
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_mechanism_name_by_id(self, id):
        query = f"SELECT name FROM mechanisms WHERE id={id}"
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data


    def create_mechanism_values_table(self):
        query = "CREATE TABLE IF NOT EXISTS mechanism_values (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    mechanism_id INTEGER NOT NULL,\
					value TEXT,\
                    metadata json NOT NULL,\
                    container TEXT,\
                    UNIQUE(mechanism_id, value, container),\
                    FOREIGN KEY (mechanism_id) REFERENCES mechanisms(id)\
				)"
        return self.execute_query(query=query)
    
    def drop_mechanism_values_table(self):
        query = "DROP TABLE IF EXISTS mechanism_values"
        return self.execute_query(query=query)
    
    def insert_mechanism_values_table(self, value, metadata, mechanism_id, container=None):
        query = "INSERT OR IGNORE INTO mechanism_values (mechanism_id, value, metadata, container) VALUES(?, ?, json(?), ?)"
        is_inserted = self.execute_query(query=query, args = (mechanism_id, value, json.dumps(metadata), container))
        # Check if the insert was ignored
        query2 = "SELECT changes()"
        result = self.fetch_query(query=query2)
        changes = result[0] if result else 0
    
        # Reset the autoincrement value if the insert was ignored
        if changes == 0:
            query3 = "UPDATE SQLITE_SEQUENCE SET seq = seq - 1 WHERE name = 'mechanism_values'"
            self.execute_query(query=query3)
        return is_inserted
    
    def insert_many_mechanism_values_table(self, tuple_data):
        query = "INSERT OR IGNORE INTO mechanism_values (mechanism_id, value, metadata, container) VALUES(?, ?, json(?), ?)"
        return self.execute_query(query=query, args = tuple_data, many=True)
        
    def get_id_values_by_container_mechanism_values_table(self, container):
        query = f"SELECT id, value FROM mechanism_values WHERE container = '{container}' ORDER BY id ASC"
        return self.fetch_query(query=query, all=True)
    
    def get_id_values_mechanism_values_table(self):
        query = f"SELECT id, value FROM mechanism_values ORDER BY id ASC"
        return self.fetch_query(query=query, all=True)
    
    def get_mechanism_values_by_container(self, container):
        query = f"SELECT id, mechanism_id, value, metadata FROM mechanism_values WHERE container = '{container}' ORDER BY id ASC"
        return self.fetch_query(query=query, all=True)
    
    def get_mechanism_values_table(self):
        query = f"SELECT * FROM mechanism_values ORDER BY id ASC"
        return self.fetch_query(query=query, all=True)
    
    # NOTE: If we get metadata, use json package to make it dict (json.loads), so it needs preprocessing after getting from db and before giving for consumption
    def get_mechanism_values_by_mechanism_id(self, mechanism_id):
        query = f"SELECT value, metadata FROM mechanism_values WHERE mechanism_id = {mechanism_id} ORDER BY id ASC"
        return self.fetch_query(query=query, all=True)
        
    '''
    Functions to handle the central database that stores results, violation reports and other important information for analysis (Tester, Analyzer).
    '''
    
    '''
    Experiments DB
    '''
    def create_experiments_table(self):
        query = "CREATE TABLE IF NOT EXISTS experiments (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    db TEXT NOT NULL,\
					config json NOT NULL,\
                    env_config json NOT NULL,\
                    example TEXT NOT NULL,\
                    crossexample TEXT NOT NULL,\
                    date TEXT DEFAULT CURRENT_TIMESTAMP,\
                    experiment_exec_time REAL,\
                    values_generation_time REAL,\
                    values_retrieval_time REAL\
				)"
        return self.execute_query(query=query)
    
    def insert_experiments_table(self, db, config, env_config, example, crossexample):
        query = "INSERT INTO experiments (db, config, env_config, example, crossexample) VALUES(?, ?, ?, ?, ?)"
        return self.execute_query(query=query, args = (db, json.dumps(config), json.dumps(env_config), example, crossexample), return_id=True)
    
    def delete_experiment(self, experiment_id):
        get_deployments_query = "SELECT id FROM deployments WHERE experiment_id = ?"
        delete_browser_results_query = "DELETE FROM browser_results WHERE deployment_id = ?"
        delete_deployments_query = "DELETE FROM deployments WHERE experiment_id = ?"
        delete_experiment_query = "DELETE FROM experiments WHERE id = ?"
        deployments = self.fetch_query(get_deployments_query, args=(experiment_id, ), all=True)
        for deployment in deployments:
            deployment_id = deployment[0]
            self.execute_query(query=delete_browser_results_query, args=(deployment_id,))
        self.execute_query(query=delete_deployments_query, args=(experiment_id,))
        self.execute_query(query=delete_experiment_query, args=(experiment_id,))


    def update_experiment_execution_time(self, id, exec_time):
        query = "UPDATE experiments SET experiment_exec_time=? WHERE id=?;"
        return self.execute_query(query=query, args = (exec_time, id))
    
    def update_experiment_metrics(self, id, values_generation_time, values_retrieval_time):
        query = "UPDATE experiments SET values_generation_time = ?, values_retrieval_time = ? WHERE id=?;"
        return self.execute_query(query=query, args = (values_generation_time, values_retrieval_time, id))

    def get_experiment_metrics(self, id):
        query = "SELECT experiment_exec_time, values_generation_time, values_retrieval_time FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def drop_experiments_table(self):
        query = "DROP TABLE IF EXISTS experiments"
        return self.execute_query(query=query)
    
    def get_experiments_table(self):
        query = "SELECT * FROM experiments"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_experiments_by_id(self, id):
        query = "SELECT * FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_experiments_db_by_id(self, id):
        query = "SELECT db FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_experiments_config_by_id(self, id):
        query = "SELECT config FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_experiments_env_config_by_id(self, id):
        query = "SELECT env_config FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_used_domains_by_id(self, id):
        query = "SELECT example, crossexample FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_info_for_replay_mode(self, id):
        query = "SELECT config, env_config, example, crossexample FROM experiments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    '''
    Deployments DB (results per execution (1 per all mechanisms' unique ids))
    '''
    def create_deployments_table(self):
        query = "CREATE TABLE IF NOT EXISTS deployments (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    deployment_index INTEGER NOT NULL,\
                    test_environment json NOT NULL,\
                    experiment_id INTEGER NOT NULL,\
                    deployment_exec_time REAL,\
                    reboot INTEGER,\
                    reboot_time REAL,\
                    FOREIGN KEY (experiment_id) REFERENCES experiments(id)\
				)"
        return self.execute_query(query=query)

    def insert_deployments_table(self, deployment_index, test_environment, experiment_id):
        query = "INSERT INTO deployments (deployment_index, test_environment, experiment_id) VALUES(?, json(?), ?)"
        return self.execute_query(query=query, args = (deployment_index, json.dumps(test_environment), experiment_id), return_id=True)

    def update_deployment_execution_time(self, id, exec_time, reboot, reboot_time):
        query = "UPDATE deployments SET deployment_exec_time=?, reboot=?, reboot_time=? WHERE id=?;"
        return self.execute_query(query=query, args = (exec_time, 1 if reboot else 0, reboot_time, id))
    
    def get_deployment_exec_time(self, id):
        query = "SELECT deployment_exec_time FROM deployments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_deployments_metrics_by_experiment_id(self, experiment_id):
        query = "SELECT AVG(deployment_exec_time) FROM deployments WHERE experiment_id=%s" % str(experiment_id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def get_deployments_table(self):
        query = "SELECT * FROM deployments"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_deployments_by_id(self, id):
        query = "SELECT * FROM deployments WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    def get_deployments_by_experiment_id(self, experiment_id):
        query = "SELECT * FROM deployments WHERE experiment_id=%s" % str(experiment_id)
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_deployments_by_id_and_experiment_id(self, id, experiment_id):
        query = f"SELECT * FROM deployments WHERE id={id} AND experiment_id={experiment_id}"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data

    def drop_deployments_table(self):
        query = "DROP TABLE IF EXISTS deployments"
        return self.execute_query(query=query)
    
    '''
    Browser Results DB (results per single test)
    '''
    def create_browser_results_table(self): # name == browser_name
        query = "CREATE TABLE IF NOT EXISTS browser_results (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    name TEXT NOT NULL,\
                    version TEXT NOT NULL,\
					results json NOT NULL,\
                    thread INTEGER,\
                    deployment_id INTEGER NOT NULL,\
                    test_exec_time REAL,\
                    clear_browser_data_time REAL,\
                    mitmproxy_data json NOT NULL,\
                    FOREIGN KEY (deployment_id) REFERENCES deployments(id)\
				)"
        return self.execute_query(query=query)

    # NOTE: mitmproxy_data (requests) cannot be inserted, we have to update them after the deployment run is completed.
    def insert_browser_results_table(self, browser, version, results, thread, deployment_id, exec_time=None, clear_browser_data_time=None, mitmproxy_data={}):
        query = "INSERT INTO browser_results (name, version, results, thread, deployment_id, test_exec_time, clear_browser_data_time, mitmproxy_data) \
        VALUES(?, ?, json(?), ?, ?, ?, ?, json(?))"
        return self.execute_query(query=query, args = (browser, version, json.dumps(results),
                    thread, deployment_id, exec_time, clear_browser_data_time, json.dumps(mitmproxy_data)), return_id=True)

    def update_browser_results(self, id, results):
        query = "UPDATE browser_results SET results = json(?) WHERE id = ?"
        return self.execute_query(query=query, args = (json.dumps(results), str(id)))
    
    def update_browser_mitmproxy_data(self, id, mitmproxy_data):
        query = "UPDATE browser_results SET mitmproxy_data = json(?) WHERE id = ?"
        return self.execute_query(query=query, args = (json.dumps(mitmproxy_data), str(id)))

    def update_browser_metrics(self, id, exec_time, clear_browser_data_time):
        query = "UPDATE browser_results SET test_exec_time = ?, clear_browser_data_time = ? WHERE id = ?"
        return self.execute_query(query=query, args = (exec_time, clear_browser_data_time, str(id)))

    def get_browser_results_metrics_by_experiment_id(self, experiment_id):
        query = f"""SELECT
                    AVG(browser_results.test_exec_time) AS avg_test_exec_time,
                    AVG(browser_results.clear_browser_data_time) AS avg_clear_browser_data_time
                FROM
                    experiments
                JOIN
                    deployments ON experiments.id = deployments.experiment_id
                JOIN
                    browser_results ON deployments.id = browser_results.deployment_id
                WHERE
                    experiments.id = {experiment_id};
                """
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def get_browser_results_metrics_by_experiment_id_and_browser(self, experiment_id, browser):
        query = f"""SELECT
                    AVG(browser_results.test_exec_time) AS avg_test_exec_time,
                    AVG(browser_results.clear_browser_data_time) AS avg_clear_browser_data_time
                FROM
                    experiments
                JOIN
                    deployments ON experiments.id = deployments.experiment_id
                JOIN
                    browser_results ON deployments.id = browser_results.deployment_id
                WHERE
                    experiments.id = {experiment_id} AND browser_results.name = '{browser}';
                """
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def get_browser_results_table(self):
        query = "SELECT * FROM browser_results"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_browser_results_by_browser_name(self, browser_name):
        query = "SELECT * FROM browser_results WHERE name='%s'" % browser_name
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_browser_results_by_browser_version(self, browser_name, browser_version):
        query = "SELECT * FROM browser_results WHERE name='%s' and version='%s'" % (browser_name, browser_version)
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_browser_results_by_id(self, id):
        query = "SELECT * FROM browser_results WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def get_browser_results_by_deployment_id(self, deployment_id):
        query = "SELECT * FROM browser_results WHERE deployment_id=%s" % str(deployment_id)
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
       
    def get_only_results_from_browser_results_by_id(self, id):
        query = "SELECT results FROM browser_results WHERE id=%s" % str(id)
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data

    def get_only_results_from_browser_results_by_deployment_id(self, deployment_id):
        query = "SELECT results FROM browser_results WHERE deployment_id=%s" % str(deployment_id)
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return [json.loads(d) for d in data]

    def drop_browser_results_table(self):
        query = "DROP TABLE IF EXISTS browser_results"
        return self.execute_query(query=query)
    
    '''
    Violation reports DB (e.g. CSP violation report)
    Extract requested info from url.
    '''
    def create_violation_reports_table(self):
        query = "CREATE TABLE IF NOT EXISTS violation_reports (\
                    id INTEGER PRIMARY KEY AUTOINCREMENT,\
                    report_type TEXT NOT NULL,\
					report json NOT NULL,\
                    results_id INTEGER NOT NULL,\
                    FOREIGN KEY (results_id) REFERENCES browser_results(id)\
				)"
        return self.execute_query(query=query)
    
    def drop_violation_reports_table(self):
        query = "DROP TABLE IF EXISTS violation_reports"
        return self.execute_query(query=query)
    
    def insert_violation_report(self, report_type, report, results_id):
        query = "INSERT INTO violation_reports (report_type, report, results_id) VALUES(?, json(?), ?)"
        return self.execute_query(query=query, args = (report_type, json.dumps(report), results_id))
    
    def get_only_violation_reports(self):
        query = "SELECT report FROM violation_reports"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return [json.loads(d) for d in data]

    def get_violation_reports_table(self):
        query = "SELECT * FROM violation_reports"
        data = self.fetch_query(query=query, all=True)
        if not data:
            return []
        return data
    
    def get_violation_reports_by_browser_results_id(self, results_id):
        query = f"SELECT report_type, report FROM violation_reports WHERE results_id='{results_id}'"
        data = self.fetch_query(query=query)
        if not data:
            return None
        return data
    
    # ------ Utils for Analyzer ------ #
    def get_experiments_for_analysis(self, experiment_ids):
        """Fetches experiments by ids."""
        placeholders = ",".join(["?"] * len(experiment_ids))

        query = f"""
            SELECT id, experiment_exec_time, values_generation_time, values_retrieval_time
            FROM experiments
            WHERE id IN ({placeholders})
        """

        rows = self.fetch_query(query, experiment_ids, all=True)

        return [
            {
                "id": row[0],
                "experiment_exec_time": row[1],
                "values_generation_time": row[2],
                "values_retrieval_time": row[3],
            }
            for row in rows
        ]
    
    def get_deployments_for_analysis(self, experiment_ids):
        """Fetches deployments for given experiments."""
        placeholders = ",".join(["?"] * len(experiment_ids))

        query = f"""
            SELECT id, deployment_index, test_environment, experiment_id
            FROM deployments
            WHERE experiment_id IN ({placeholders})
        """

        rows = self.fetch_query(query, experiment_ids, all=True)

        return [
            {
                "id": row[0],
                "deployment_index": row[1],
                "test_environment": row[2],
                "experiment_id": row[3],
            }
            for row in rows
        ]

    def get_browser_results_for_analysis(self, experiment_ids):
        """Fetches browser results joined with deployments."""
        placeholders = ",".join(["?"] * len(experiment_ids))

        query = f"""
            SELECT 
                br.id,
                br.name,
                br.version,
                br.results,
                br.deployment_id,
                br.test_exec_time,
                br.mitmproxy_data,
                d.experiment_id
            FROM browser_results br
            JOIN deployments d ON br.deployment_id = d.id
            WHERE d.experiment_id IN ({placeholders})
        """

        rows = self.fetch_query(query, experiment_ids, all=True)

        return [
            {
                "id": row[0],
                "name": row[1],
                "version": row[2],
                "results": row[3],
                "deployment_id": row[4],
                "test_exec_time": row[5],
                "mitmproxy_data": row[6],
                "experiment_id": row[7],
            }
            for row in rows
        ]

    def get_violation_reports_for_analysis(self):
        """Fetches all violation reports (empty list if none)."""
        query = """
            SELECT results_id
            FROM violation_reports
        """

        rows = self.fetch_query(query, all=True)

        return [
            {"results_id": row[0]}
            for row in rows
        ]
    