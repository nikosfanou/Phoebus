import json
import time
from collections import defaultdict

from utils.SQLiteHandler import SQLiteHandler

def parse_json_safe(value):
    if value is None:
        return {}
    if isinstance(value, dict):
        return value
    return json.loads(value)

def build_browser_id(name, version):
    return f"{name}-{version}"

def extract_test_environment(te_json):
    # Extracts test_environment field (minimal for report).
    te = parse_json_safe(te_json)

    return {
        "run_on": te.get("run_on"),
        "status_code": te.get("status_code"),
        "test_file": te.get("test_file"),
        "mechanism_values": [
            {
                "mechanism": mv.get("mechanism") if mv.get("type") == "mechanism" else "custom_header",
                "values": [v[0] for v in mv.get("values", [])] if mv.get("type") == "mechanism" else mv.get("headers", [])
            }
            for mv in te.get("mechanism_values", [])
        ]
    }

def extract_test_environment_full(te_json):
    # Returns whole test_environment field (with metadata) for simplified input.
    return parse_json_safe(te_json)

def values_equal(values):
    serialized = set(json.dumps(v, sort_keys=True) for v in values)
    return len(serialized) <= 1

def build_discrepancy(path, browser_values):
    grouped = defaultdict(list)

    for browser, value in browser_values.items():
        grouped[json.dumps(value, sort_keys=True)].append(browser)

    return {
        "path": list(path),
        "values": [
            {
                "browsers": browsers,
                "value": json.loads(value)
            }
            for value, browsers in grouped.items()
        ]
    }

def compare_recursive(browser_values, path=(), discrepancies=None):
    """
    Recursively compares browser values while avoiding redundant discrepancies.

    Example:
    Brave, Edge, Chrome -> {'object': True, 'embed': True}
    Firefox, Tor -> None
    WebKit -> {'object': False, 'embed': False}
    Will create:
        1. {'object': True, 'embed': True} vs {'object': False, 'embed': False} vs None
        2. object: False vs True (no Firefox,Tor in this discrepancy)
        3. embed: False vs True (no Firefox,Tor in this discrepancy)
    """

    if discrepancies is None:
        discrepancies = []

    # remove browsers missing this path
    existing = {
        browser: value
        for browser, value in browser_values.items()
    }

    if not existing:
        return discrepancies

    values = list(existing.values())

    # fully identical -> stop
    if values_equal(values):
        return discrepancies

    # determine structural categories
    dict_group = {}
    list_group = {}
    primitive_group = {}

    for browser, value in existing.items():
        if isinstance(value, dict):
            dict_group[browser] = value
        elif isinstance(value, (list, tuple)):
            list_group[browser] = value
        else:
            primitive_group[browser] = value

    non_empty_groups = [
        g for g in [dict_group, list_group, primitive_group] if g
    ]

    # Mixed Types
    if len(non_empty_groups) > 1:
        discrepancies.append(build_discrepancy(path, existing))

        # recurse only into structured groups like dict/list

        # dict subgroup
        if len(dict_group) >= 2:
            dict_values = list(dict_group.values())

            # recurse only if subgroup internally differs
            if not values_equal(dict_values):

                all_keys = set()
                for d in dict_values:
                    all_keys |= set(d.keys())

                for key in all_keys:
                    child_values = {
                        browser: value.get(key, None)
                        for browser, value in dict_group.items()
                    }

                    compare_recursive(
                        child_values,
                        path + (key,),
                        discrepancies
                    )

        # list subgroup
        if len(list_group) >= 2:
            list_values = list(list_group.values())

            # recurse only if subgroup internally differs
            if not values_equal(list_values):

                max_len = max(len(v) for v in list_values)

                for idx in range(max_len):
                    child_values = {}

                    for browser, value in list_group.items():
                        if idx < len(value):
                            child_values[browser] = value[idx]
                        else:
                            child_values[browser] = None

                    compare_recursive(
                        child_values,
                        path + (idx,),
                        discrepancies
                    )

        return discrepancies

    # dicts only
    if dict_group:

        all_keys = set()
        for d in dict_group.values():
            all_keys |= set(d.keys())

        for key in all_keys:
            child_values = {
                browser: value.get(key, None)
                for browser, value in dict_group.items()
            }

            compare_recursive(
                child_values,
                path + (key,),
                discrepancies
            )

        return discrepancies

    # lists only
    if list_group:

        max_len = max(len(v) for v in list_group.values())

        for idx in range(max_len):
            child_values = {}

            for browser, value in list_group.items():
                if idx < len(value):
                    child_values[browser] = value[idx]
                else:
                    child_values[browser] = None

            compare_recursive(
                child_values,
                path + (idx,),
                discrepancies
            )

        return discrepancies

    # terminal values only
    discrepancies.append(build_discrepancy(path, existing))

    return discrepancies

def compare_results_per_group(browser_results):
    # Compares nested results recursively
    return compare_recursive(browser_results)

def compare_requests_per_group(browser_requests):
    # Compares requests presence across browsers
    all_requests = set()

    for reqs in browser_requests.values():
        all_requests |= set(reqs.keys())

    discrepancies = []

    for req in all_requests:
        values = {}
        for browser, reqs in browser_requests.items():
            values[browser] = req in reqs

        if len(set(values.values())) <= 1:
            continue

        grouped = defaultdict(list)
        for browser, val in values.items():
            grouped[val].append(browser)

        discrepancies.append({
            "request": req,
            "values": [
                {"browsers": browsers, "value": val}
                for val, browsers in grouped.items()
            ]
        })

    return discrepancies

def build_violation_lookup(violation_rows):
    # looks if violation report exists for this id
    lookup = set()
    for row in violation_rows:
        lookup.add(row["results_id"])
    return lookup

def compare_violations_per_group(browser_ids, browser_result_ids, violation_lookup):
    # Compares violation presence across browsers
    values = {}

    for browser in browser_ids:
        results_id = browser_result_ids[browser]
        values[browser] = results_id in violation_lookup

    if len(set(values.values())) <= 1:
        return []

    grouped = defaultdict(list)
    for browser, val in values.items():
        grouped[val].append(browser)

    return [{
        "values": [
            {"browsers": browsers, "value": val}
            for val, browsers in grouped.items()
        ]
    }]

def process_browser_group(
    key,
    data,
    report,
    simplified,
    violation_lookup,
    results_count_ref,
    requests_count_ref,
    violations_count_ref
):
    browsers = data["browsers"]

    results_map = {b: v["results"] for b, v in browsers.items()}
    requests_map = {b: v["requests"] for b, v in browsers.items()}

    result_diffs = compare_results_per_group(results_map)
    request_diffs = compare_requests_per_group(requests_map)

    violation_diffs = []
    if violation_lookup is not None:
        violation_diffs = compare_violations_per_group(
            list(browsers.keys()),
            data["result_ids"],
            violation_lookup
        )

    if not (result_diffs or request_diffs or violation_diffs):
        return

    entry = {
        **data["test_env_min"]
    }

    dep_index = key[0]

    simp_entry = {
        "deployment_index": dep_index,
        **data["test_env_full"]
    }

    if result_diffs:
        entry["results"] = result_diffs
        simp_entry["results"] = result_diffs
        results_count_ref[0] += len(result_diffs)

    if request_diffs:
        entry["requests"] = request_diffs
        simp_entry["requests"] = request_diffs
        requests_count_ref[0] += len(request_diffs)

    if violation_diffs:
        entry["violations"] = violation_diffs
        simp_entry["violations"] = violation_diffs
        violations_count_ref[0] += len(violation_diffs)

    report["comparisons"].append(entry)
    simplified.append(simp_entry)

def analyze_across_browsers(database, experiment_ids):
    # Main function, builds detailed report (across browsers) and simplified report's input.
    start_time = time.time()

    with SQLiteHandler(database) as db:
        experiments = db.get_experiments_for_analysis(experiment_ids)
        deployments = db.get_deployments_for_analysis(experiment_ids)
        browser_results = db.get_browser_results_for_analysis(experiment_ids)
        violation_rows = db.get_violation_reports_for_analysis()

    violation_lookup = None
    if violation_rows:
        violation_lookup = build_violation_lookup(violation_rows)

    groups = {}

    deployment_map = {d["id"]: d for d in deployments}

    expected_browser_count = len({
        build_browser_id(br["name"], br["version"])
        for br in browser_results
    })

    report = {"metrics": {}, "comparisons": []}
    simplified = []

    results_count = [0]
    requests_count = [0]
    violations_count = [0]

    # metrics per browser
    exec_times = defaultdict(list)
    for br in browser_results:
        browser_id = build_browser_id(br["name"], br["version"])
        exec_times[browser_id].append(br["test_exec_time"])

    avg_exec = {
        b: sum(v)/len(v) for b, v in exec_times.items() if v
    }

    # grouping loop
    for i, br in enumerate(browser_results):

        dep = deployment_map[br["deployment_id"]]

        te = parse_json_safe(dep["test_environment"])

        key = (
            dep["deployment_index"],
            te.get("run_on"),
            te.get("status_code"),
            te.get("test_file")
        )

        browser_id = build_browser_id(br["name"], br["version"])

        if key not in groups:
            groups[key] = {
                "test_env_min": extract_test_environment(dep["test_environment"]),
                "test_env_full": extract_test_environment_full(dep["test_environment"]),
                "browsers": {},
                "result_ids": {}
            }

        if browser_id in groups[key]["browsers"]:
            raise Exception(f"Duplicate browser entry for key {key} and browser {browser_id}")

        groups[key]["browsers"][browser_id] = {
            "results": parse_json_safe(br["results"]),
            "requests": parse_json_safe(br["mitmproxy_data"])
        }

        groups[key]["result_ids"][browser_id] = br["id"]

        # every 100 iterations process completed groups -> memory-handling enhancement
        if i % 100 == 0:

            completed_keys = []

            for gkey, data in groups.items():

                if len(data["browsers"]) != expected_browser_count:
                    continue

                process_browser_group(
                    gkey,
                    data,
                    report,
                    simplified,
                    violation_lookup,
                    results_count,
                    requests_count,
                    violations_count
                )

                completed_keys.append(gkey)

            # free completed groups -> memory-handling enhancement
            for gkey in completed_keys:
                del groups[gkey]

    # process remaining groups
    for gkey, data in groups.items():

        process_browser_group(
            gkey,
            data,
            report,
            simplified,
            violation_lookup,
            results_count,
            requests_count,
            violations_count
        )

    # metrics
    experiment_metrics = {
        exp["id"]: {
            "experiment_exec_time": exp.get("experiment_exec_time"),
            "values_generation_time": exp.get("values_generation_time"),
            "values_retrieval_time": exp.get("values_retrieval_time"),
        }
        for exp in experiments
    }

    report["metrics"] = {
        "experiments": experiment_metrics,
        "avg_test_exec_time_per_browser": avg_exec,
        "discrepancies": {
            "results": results_count[0],
            "requests": requests_count[0],
            "violations": violations_count[0],
        },
        "analysis_time": time.time() - start_time,
    }

    report["metrics"]["total_discrepancies"] = sum(
        [c for c in report["metrics"]["discrepancies"].values()]
    )

    return report, simplified

def process_version_group(
    key,
    data,
    report,
    simplified,
    violation_lookup,
    results_count,
    requests_count,
    violations_count
):
    dep_index, run_on, status_code, test_file, browser_name = key

    browsers = data["browsers"]

    # Need at least 2 versions to compare
    if len(browsers) < 2:
        return

    results_map = {b: v["results"] for b, v in browsers.items()}
    requests_map = {b: v["requests"] for b, v in browsers.items()}

    result_diffs = compare_results_per_group(results_map)
    request_diffs = compare_requests_per_group(requests_map)

    violation_diffs = []
    if violation_lookup is not None:
        violation_diffs = compare_violations_per_group(
            list(browsers.keys()),
            data["result_ids"],
            violation_lookup
        )

    if not (result_diffs or request_diffs or violation_diffs):
        return

    entry = {
        "deployment_index": dep_index,
        "browser": browser_name,
        **data["test_env_min"]
    }

    simp_entry = {
        "deployment_index": dep_index,
        "browser": browser_name,
        **data["test_env_full"]
    }

    if result_diffs:
        entry["results"] = result_diffs
        simp_entry["results"] = result_diffs
        results_count[browser_name] += len(result_diffs)

    if request_diffs:
        entry["requests"] = request_diffs
        simp_entry["requests"] = request_diffs
        requests_count[browser_name] += len(request_diffs)

    if violation_diffs:
        entry["violations"] = violation_diffs
        simp_entry["violations"] = violation_diffs
        violations_count[browser_name] += len(violation_diffs)

    report["comparisons"].append(entry)
    simplified.append(simp_entry)

def analyze_across_versions(database, experiment_ids):
    # Analyzes discrepancies across versions (same browser across experiments)
    start_time = time.time()

    with SQLiteHandler(database) as db:
        deployments = db.get_deployments_for_analysis(experiment_ids)
        browser_results = db.get_browser_results_for_analysis(experiment_ids)
        violation_rows = db.get_violation_reports_for_analysis()

    violation_lookup = None
    if violation_rows:
        violation_lookup = build_violation_lookup(violation_rows)

    groups = {}

    deployment_map = {d["id"]: d for d in deployments}

    expected_versions_per_group = len({
        f"{br['name']}-{br['version']}-exp{br['experiment_id']}"
        for br in browser_results
    })

    report = {"metrics": {}, "comparisons": []}
    simplified = []

    results_count = defaultdict(int)
    requests_count = defaultdict(int)
    violations_count = defaultdict(int)

    # metrics per browser_id
    exec_times = defaultdict(list)
    for br in browser_results:
        browser_id = f"{br['name']}-{br['version']}-exp{br['experiment_id']}"
        exec_times[browser_id].append(br["test_exec_time"])

    avg_exec = {
        b: sum(v)/len(v) for b, v in exec_times.items() if v
    }

    # grouping loop
    for i, br in enumerate(browser_results):

        dep = deployment_map[br["deployment_id"]]

        te = parse_json_safe(dep["test_environment"])

        key = (
            dep["deployment_index"],
            te.get("run_on"),
            te.get("status_code"),
            te.get("test_file"),
            br["name"]
        )

        browser_id = f"{br['name']}-{br['version']}-exp{br['experiment_id']}"

        if key not in groups:
            groups[key] = {
                "test_env_min": extract_test_environment(dep["test_environment"]),
                "test_env_full": extract_test_environment_full(dep["test_environment"]),
                "browsers": {},
                "result_ids": {}
            }

        if browser_id in groups[key]["browsers"]:
            raise Exception(f"Duplicate browser entry for key {key} and browser {browser_id}")

        groups[key]["browsers"][browser_id] = {
            "results": parse_json_safe(br["results"]),
            "requests": parse_json_safe(br["mitmproxy_data"])
        }

        groups[key]["result_ids"][browser_id] = br["id"]

        # every 100 iterations process completed groups -> memory-handling enhancement
        if i % 100 == 0:

            completed_keys = []

            for gkey, data in groups.items():

                if len(data["browsers"]) != expected_versions_per_group:
                    continue

                process_version_group(
                    gkey,
                    data,
                    report,
                    simplified,
                    violation_lookup,
                    results_count,
                    requests_count,
                    violations_count
                )

                completed_keys.append(gkey)

            # free completed groups -> memory-handling enhancement
            for gkey in completed_keys:
                del groups[gkey]

    # process remaining groups
    for gkey, data in groups.items():

        process_version_group(
            gkey,
            data,
            report,
            simplified,
            violation_lookup,
            results_count,
            requests_count,
            violations_count
        )

    # metrics
    report["metrics"] = {
        "avg_test_exec_time_per_browser": avg_exec,
        "discrepancies": {
            "results": dict(results_count),
            "requests": dict(requests_count),
            "violations": dict(violations_count),
        },
        "analysis_time": time.time() - start_time,
    }

    return report, simplified

def analyze(database, experiment_ids, mode="browsers"):
    if mode == "browsers":
        return analyze_across_browsers(database, experiment_ids)
    elif mode == "versions":
        return analyze_across_versions(database, experiment_ids)
    else:
        raise ValueError(f"Unknown mode: {mode}")
