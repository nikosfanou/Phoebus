from copy import deepcopy
import json
from collections import Counter
from collections import defaultdict
import time

# Constants
AGG_FIELDS = ["status_code", "custom_headers", "run_on"]
MUTATION_AGG_FIELDS = [
    "case",
    "replace_from",
    "replace_to",
    "char",
    "populate_char_position",
]
DELIMITER_FIELDS = [
    "directives_delimiter",
    "directive_values_delimiter",
    "values_delimiter",
]
METADATA_FIELDS = [
    *MUTATION_AGG_FIELDS,
    "has_prefix",
    *DELIMITER_FIELDS
]

# Helpers 
def normalize_result(value):
    if isinstance(value, (dict, list)):
        return json.dumps(value, sort_keys=True)
    return value

def path_to_test_id(test_file, path):
    return f"{test_file}->{'->'.join(map(str, path))}"

def is_mutation(meta):
    return meta.get("mutation") is True

def is_custom(meta):
    return meta.get("custom_value") or meta.get("mechanism_is_not_set")

def is_normal(meta):
    return not is_mutation(meta) and not is_custom(meta)

def identity_to_counter(identity):
    if identity is None:
        return None

    items = []
    for directive, values in identity:
        if not values:
            items.append((directive, None))
        else:
            for v in values:
                items.append((directive, v))

    return Counter(items) # counters how many times we observe a directive-value pair, helpful in duplicates and in merging

def counter_is_subset(a, b):
    for k in a:
        if a[k] > b.get(k, 0): # compares identities and decides if the one is subset of the other e.g., DENY subset of DENY, SAMEORIGIN !
            return False
    return True

def deployments_equal_except_identity(d1, d2, mech_name, pos):
    # status_code
    if d1["status_code"] != d2["status_code"]: return False

    # run_on
    if d1["run_on"] != d2["run_on"]: return False

    # headers
    if d1["custom_headers"] != d2["custom_headers"]: return False

    # mechanisms
    if set(d1["mechanisms"]) != set(d2["mechanisms"]):
        return False

    for mech in d1["mechanisms"]:
        vals1 = d1["mechanisms"][mech]
        vals2 = d2["mechanisms"][mech]

        if len(vals1) != len(vals2):
            return False

        for i, (v1, v2) in enumerate(zip(vals1, vals2)):
            # skip ONLY the identity we are merging
            if mech == mech_name and i == pos:
                continue

            # normal / duplicate
            if v1["identity"] is not None and v2["identity"] is not None:
                if v1["metadata"] != v2["metadata"]:
                    return False

            # at least one is custom / mutation
            else:
                if v1["value"] != v2["value"]:
                    return False

                if v1["metadata"] != v2["metadata"]:
                    return False

    return True

def make_hashable(obj):
    if isinstance(obj, dict):
        return tuple(
            (k, make_hashable(v))
            for k, v in sorted(obj.items())
        )
    elif isinstance(obj, list) or isinstance(obj, tuple):
        return tuple(make_hashable(v) for v in obj)
    else:
        return obj

def build_aggregation_key(dep, ignore_field):
    raw_key = (
        dep["status_code"] if ignore_field != "status_code" else None,
        dep["run_on"] if ignore_field != "run_on" else None,
        dep["custom_headers"] if ignore_field != "custom_headers" else None,

        tuple(
            (m, tuple(
                (
                    v["value"],
                    v["metadata"]
                )
                for v in dep["mechanisms"][m]
            ))
            for m in sorted(dep["mechanisms"])
        )
    )

    return make_hashable(raw_key)

def metadata_key(meta, ignore_field):
    raw = {
        k: v
        for k, v in meta.items()
        if k != ignore_field
    }

    return make_hashable(raw)

def clean_traceability(deployments):
    for d in deployments:
        ids = d["deployment_id"]
        evidence = d["evidence"]

        # normalize to lists
        if not isinstance(ids, list):
            ids = [ids]

        if not isinstance(evidence, list):
            evidence = [evidence]

        d["deployment_id"], d["evidence"] = deduplicate_traceability(
            ids,
            evidence
        )

def deduplicate_traceability(ids, evidence):
    assert len(ids) == len(evidence), "Traceability misalignment!" # shouldn't break here ever!
    
    seen = set()
    new_ids = []
    new_evidence = []

    for i, e in zip(ids, evidence):
        if i in seen:
            continue
        seen.add(i)
        new_ids.append(i)
        new_evidence.append(e)

    return new_ids, new_evidence


# Phase 1 - Data preparation (Clustering + Identity building)
def build_clusters(simplified_input):
    clusters = {}

    for entry in simplified_input:
        deployment_index = entry["deployment_index"]
        mechanism_values = entry.get("mechanism_values")
        status_code = entry.get("status_code")
        run_on = entry.get("run_on")
        test_file = entry.get("test_file")

        # move out of mechanism_values field to participate in aggregation phase
        custom_headers = []
        mechanisms_only = []
        for mv in (mechanism_values or []):
            if mv.get("type") == "header":
                custom_headers.extend(mv.get("headers", []))
            else:
                mechanisms_only.append(mv)

        if not custom_headers:
            custom_headers = None

        # Build identity
        mechanisms = {}

        for mv in mechanisms_only:
            mech_name = mv.get("mechanism")
            values = mv.get("values", [])

            mechanisms.setdefault(mech_name, [])

            for value_string, metadata in values:
                metadata = deepcopy(metadata)

                if is_normal(metadata):
                    identity = build_identity(metadata)
                else:
                    identity = None  # mutation or custom

                mechanisms[mech_name].append({
                    "value": value_string,
                    "metadata": metadata,
                    "identity": identity,
                })
        
        evidence_entry = {
            mech_name: [v["value"] for v in mech_values]
            for mech_name, mech_values in mechanisms.items()
        }

        # Build clusters
        for section in ["results", "requests", "violations"]:
            if section not in entry:
                continue

            for diff in entry[section]:
                path = diff.get("path") or diff.get("request") or ["violation"]
                test_id = path_to_test_id(test_file, path)

                for group in diff["values"]:
                    result = normalize_result(group["value"])

                    for browser in group["browsers"]:

                        # init structures
                        clusters.setdefault(browser, {})
                        clusters[browser].setdefault(section, {})
                        clusters[browser][section].setdefault(result, {})
                        clusters[browser][section][result].setdefault(test_id, [])

                        # append entry (minimal)
                        clusters[browser][section][result][test_id].append({
                            "deployment_id": [deployment_index],
                            "status_code": status_code,
                            "run_on": run_on,
                            "custom_headers": custom_headers,
                            "mechanisms": mechanisms,
                            "evidence": [evidence_entry]
                        })

    return clusters

def build_identity(metadata):
    directives = metadata.get("has_directive")
    values = metadata.get("has_value")
    pairs = metadata.get("has_directive_values_pair")

    if not directives:
        return None

    if isinstance(directives, str):
        directives = [directives]

    if isinstance(values, str):
        values = [values]

    # duplicates case
    if metadata.get("duplicate"):
        directive = directives[0]
        vals = values or []

        # 0 values -> both empty
        if len(vals) == 0:
            return [
                (directive, ()),
                (directive, ())
            ]

        # 1 value -> both same
        elif len(vals) == 1:
            return [
                (directive, (vals[0],)),
                (directive, (vals[0],))
            ]

        # 2 values -> one each
        elif len(vals) == 2:
            return [
                (directive, (vals[0],)),
                (directive, (vals[1],))
            ]

        else:
            raise ValueError(f"Unexpected duplicate values: {vals}")

    # Normal cases
    identity = []
    if pairs is not None: # "has_directive_values_pair" field exists
        for directive, vals in zip(directives, pairs):
            identity.append((directive, tuple(vals or [])))
    else:
        directive = directives[0] # if no pairs, then only 1 directive (so we can reconstruct has_directive_values_pair easily)
        identity.append((directive, tuple(values or [])))

    return identity

# Phase 2 - Merging
def merge_mechanism(deployments, mech_name):
    if len(deployments) <= 1: # Nothing to merge if <= 1 deployment
        return deployments

    result = []
    used = [False] * len(deployments)

    num_positions = len(deployments[0]["mechanisms"].get(mech_name, []))

    for pos in range(num_positions): # merge per position
        items = []

        for idx, dep in enumerate(deployments):
            if used[idx]:
                continue

            if mech_name not in dep["mechanisms"]:
                continue

            v = dep["mechanisms"][mech_name][pos]

            if v["identity"] is None:
                continue  # skip custom/mutation

            counter = identity_to_counter(v["identity"])
            items.append((idx, dep, v, counter))

        if len(items) <= 1:
            continue

        # sort smallest counter/identity first
        items.sort(key=lambda x: sum(x[3].values()))

        for base_idx, base_dep, base_v, base_counter in items:
            if used[base_idx]:
                continue

            covered = []

            for idx, dep, v, counter in items:
                if used[idx]:
                    continue

                if not deployments_equal_except_identity(
                    base_dep, dep, mech_name, pos
                ): # everything else should be IDENTICAL strictly
                    continue

                if counter_is_subset(base_counter, counter): # e.g., script-src 'self' is subset of script-src 'self' 'none'
                    covered.append(idx)

            if len(covered) <= 1:
                continue # nothing to be merged

            # merge
            merged = deepcopy(base_dep)

            merged_ids = []
            merged_evidence = []

            # keep deployment_id and evidence for traceability
            for idx in covered:
                d = deployments[idx]

                if isinstance(d["deployment_id"], list):
                    merged_ids.extend(d["deployment_id"])
                else:
                    merged_ids.append(d["deployment_id"])

                merged_evidence.extend(d["evidence"])
                used[idx] = True

            merged["deployment_id"] = merged_ids
            merged["evidence"] = merged_evidence

            result.append(merged)

    # leftovers
    for idx, dep in enumerate(deployments):
        if not used[idx]:
            result.append(dep)

    return result

def merge_phase(deployments):
    if not deployments:
        return deployments  # nothing to process

    # collect all mechanism names across deployments
    mechanisms = set()
    for dep in deployments:
        mechanisms.update(dep["mechanisms"].keys())

    current = deployments  # we progressively update this

    # process one mechanism at a time
    for mech in mechanisms:
        groups = {}
        passthrough = []

        for dep in current:
            # deployments without this mechanism -> untouched
            if mech not in dep["mechanisms"]:
                passthrough.append(dep)
                continue

            # build grouping key = EVERYTHING except the mechanism we merge
            key = (
                dep["status_code"],
                dep["run_on"],
                tuple(dep["custom_headers"] or []),

                # include ALL OTHER mechanisms strictly
                tuple(
                    (m, tuple(
                        (v["value"], make_hashable(v["metadata"]))
                        for v in dep["mechanisms"][m]
                    ))
                    for m in sorted(dep["mechanisms"])
                    if m != mech
                )
            )

            groups.setdefault(key, []).append(dep)

        new_current = []

        # run merging INSIDE each group
        for group in groups.values():
            merged = merge_mechanism(group, mech)
            new_current.extend(merged)

        # add back untouched deployments
        new_current.extend(passthrough)

        current = new_current  # update for next mechanism

    return current

# Phase 3 - Aggregation
def aggregate_metadata_field(deployments, field):
    groups = {}

    for dep in deployments:
        raw_key = (
            dep["status_code"],
            dep["run_on"],
            dep["custom_headers"],

            # mechanisms BUT ignoring one metadata field (the one being aggregated each time)
            tuple(
                (m, tuple(
                    (
                        v["value"],
                        metadata_key(v["metadata"], field)
                    )
                    for v in dep["mechanisms"][m]
                ))
                for m in sorted(dep["mechanisms"])
            )
        )

        key = make_hashable(raw_key)

        groups.setdefault(key, []).append(dep)

    result = []

    for group in groups.values():
        if len(group) == 1:
            result.append(group[0])
            continue

        merged = deepcopy(group[0])

        # aggregate ONLY the target metadata field
        for m in merged["mechanisms"]:
            for i, v in enumerate(merged["mechanisms"][m]):
                values = []

                for d in group:
                    meta = d["mechanisms"][m][i]["metadata"]
                    val = meta.get(field)

                    if isinstance(val, list):
                        values.extend(val)
                    else:
                        values.append(val)

                # deduplicate while preserving order
                values = list(dict.fromkeys(values))

                merged["mechanisms"][m][i]["metadata"][field] = values

        # merge traceability (aligned lists)
        merged_ids = []
        merged_evidence = []

        for d in group:
            if isinstance(d["deployment_id"], list):
                merged_ids.extend(d["deployment_id"])
            else:
                merged_ids.append(d["deployment_id"])

            merged_evidence.extend(d["evidence"])

        merged["deployment_id"] = merged_ids
        merged["evidence"] = merged_evidence

        result.append(merged)

    return result

def aggregate_on_field(deployments, field):
    groups = {}

    for dep in deployments:
        key = build_aggregation_key(dep, field)

        groups.setdefault(key, []).append(dep)

    result = []

    for group in groups.values():

        # no aggregation needed
        if len(group) == 1:
            result.append(group[0])
            continue

        values = []

        merged_ids = []
        merged_evidence = []

        # aggregate values
        for d in group:

            val = d[field]

            # preserve grouped custom-header structure
            if field == "custom_headers":

                if val is None:
                    continue

                # normalize, e.g., "abc" -> ["abc"]
                if not isinstance(val, list):
                    val = [val]

                # preserve deployment grouping
                values.append(val)

            # normal aggregation
            else:

                if isinstance(val, list):
                    values.extend(val)
                else:
                    values.append(val)

            # traceability
            ids = d["deployment_id"]

            if not isinstance(ids, list):
                ids = [ids]

            merged_ids.extend(ids)

            merged_evidence.extend(d["evidence"])

        # finalize
        merged = deepcopy(group[0])
        merged[field] = values
        merged["deployment_id"] = merged_ids
        merged["evidence"] = merged_evidence
        result.append(merged)

    return result

def aggregation_phase(deployments):
    current = deployments
    for field in AGG_FIELDS:
        current = aggregate_on_field(current, field)

    for meta_field in METADATA_FIELDS:
        current = aggregate_metadata_field(current, meta_field)

    clean_traceability(deployments=current)

    return current

def build_simplified_report(simplified_input):
    stats = {"simplification_time": 0, "rules_per_browser": {}}
    start_time = time.time()

    clusters = build_clusters(simplified_input=simplified_input)

    merged_clusters = {}
    for browser, sections in clusters.items():
        merged_clusters.setdefault(browser, {})
        stats["rules_per_browser"].setdefault(browser, {})

        for section, results in sections.items():
            merged_clusters[browser].setdefault(section, {})
            stats["rules_per_browser"][browser].setdefault(section, {})

            for result, tests in results.items():
                merged_clusters[browser][section].setdefault(result, {})

                for test_id, entries in tests.items():
                    merged_entries = merge_phase(entries)
                    aggregated_entries = aggregation_phase(deployments=merged_entries)
                    merged_clusters[browser][section][result][test_id] = aggregated_entries
            
            behavior_clusters = build_behavior_clusters(clusters=merged_clusters[browser][section])
            behavior_region_clusters, num_of_rules = build_behavior_region_clusters_strict_equality(behavior_clusters=behavior_clusters)
            merged_clusters[browser][section] = behavior_region_clusters
            stats["rules_per_browser"][browser][section] = num_of_rules
    
    stats["simplification_time"] = time.time() - start_time
    return merged_clusters, stats

def build_behavior_clusters(clusters):
    """
    behavior_signature
        -> test_id
            -> results
                -> deployments
    """

    behavior_clusters = defaultdict(
        lambda: defaultdict(dict)
    )

    # collect all results per test
    test_results = defaultdict(dict)

    for result, tests in clusters.items():

        for test_id, deployments in tests.items():

            # preserve FULL deployments
            test_results[test_id][result] = deepcopy(
                deployments
            )

    # cluster by RESULT SET
    for test_id, result_map in test_results.items():

        behavior_signature = frozenset(
            result_map.keys()
        )

        behavior_clusters[
            behavior_signature
        ][test_id] = result_map

    return dict(behavior_clusters)

def build_behavior_region_clusters_strict_equality(behavior_clusters):

    """   
    behavior_signature
      -> deployment_signature
          -> grouped tests
    """
    final_clusters = {}

    # total produced rules
    total_region_clusters = 0

    # iterate behavior clusters
    for behavior_signature, tests_map in behavior_clusters.items():

        region_clusters = defaultdict(lambda: {
            "tests": [],
            "results": {},
            "deployments": defaultdict(dict)
        })

        # analyze tests
        for test_id, result_map in tests_map.items():

            deployment_signature = []

            # build STRICT deployment signature
            for result, deployments in result_map.items():

                deployment_ids = set()

                for deployment in deployments:

                    ids = deployment["deployment_id"]

                    if not isinstance(ids, list):
                        ids = [ids]

                    deployment_ids.update(ids)

                deployment_signature.append((
                    json.dumps(result, sort_keys=True)
                    if isinstance(result, dict)
                    else str(result),

                    tuple(sorted(deployment_ids))
                ))

            deployment_signature = tuple(
                sorted(deployment_signature)
            )

            # cluster
            cluster = region_clusters[
                deployment_signature
            ]

            cluster["tests"].append(test_id)

            # preserve FULL deployments
            for result, deployments in result_map.items():

                cluster["deployments"][test_id][result] = deployments

                deployment_ids = set()

                for deployment in deployments:

                    ids = deployment["deployment_id"]

                    if not isinstance(ids, list):
                        ids = [ids]

                    deployment_ids.update(ids)

                cluster["results"][result] = sorted(
                    deployment_ids
                )

        total_region_clusters += len(region_clusters)

        final_clusters[
            behavior_signature
        ] = dict(region_clusters)

    return final_clusters, total_region_clusters
