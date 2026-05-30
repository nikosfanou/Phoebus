import json5
import json
import itertools
import math
from argparse import ArgumentParser
from copy import deepcopy

from utils.Mutator import Mutator
from utils.SQLiteHandler import SQLiteHandler

class CONSTANTS:
    CONFIG_FILE = "configs/mechanisms.jsonc"
    RANDOM_HASH = "sha256-fRpUEnsiJQL1t5tfsIAwYRUqRPkrN+I8ZSe69mXU2po=" # Hash of `abcdefg`
    SCRIPT_VARIANTS = [
        "{CORRECT_SCRIPT_HASH}",
        RANDOM_HASH, # wrong hash
        RANDOM_HASH + 'i' # invalid hash
    ]

    STYLE_VARIANTS = [
        "{CORRECT_STYLE_HASH}",
        RANDOM_HASH, # wrong hash
        RANDOM_HASH + 'i' # invalid hash
    ]

def read_json(config):
    config_obj = None
    with open(config, 'r') as fp:
        config_obj = json5.load(fp) # json5 to be able to parse c-style comments without errors, https://stackoverflow.com/questions/29959191/how-to-parse-json-file-with-c-style-comments
    return config_obj

def write_json(config, data):
    with open(config, 'w+') as fp:
        json.dump(data, fp, indent=4)

def write_to_database(database, data):
    container = None
    with SQLiteHandler(database) as handler:
        handler.create_mechanism_table()
        handler.create_mechanism_values_table()
        for entry in data:
            mechanism_name = entry['mechanism']
            result, mechanism_id = handler.insert_mechanism_table(mechanism_name=mechanism_name, label=None)
            if not result:
                print(f'[ERROR] Could not insert {mechanism_name} in mechanisms table!')
                break

            tuple_data = [(mechanism_id, json.dumps(value[0]), json.dumps(value[1]), container) for value in entry['values']]
            handler.insert_many_mechanism_values_table(tuple_data=tuple_data)

def get_args():
    parser = ArgumentParser()
    parser.add_argument("-j", "--json", dest = "json", type=str, help = "The JSON file where the generated values will be stored.")
    parser.add_argument("-db", "--database", dest = "database", type=str, help = "The SQLite database file (from folder db) where the generated values will be stored.")
    parser.add_argument("-c", "--config", dest = "config", required=True, type=str, help = "User-defined configuration for the generation of mechanism values.")
    args = parser.parse_args()
    if not args.json and not args.database:
        parser.error("Please select at least 1 of the 2 available options (json/sqlite) to store the generated data! Run --help for more.")
    return args

def get_type(mechanism, config):
    html_attributes = list(config.get('html',{}).keys())
    if mechanism in html_attributes:
        return 'html'
    http_headers = list(config.get('headers',{}).keys())
    if mechanism in http_headers:
        return 'headers'
    print(f'[WARN] Mechanism `{mechanism}` is neither an html attribute nor an http header based on the provided predefined-mechanisms descriptions configuration.')
    return 'other'

def create_subdict(d, keys):
    return {k: d[k] for k in keys if k in d}

def find_placeholders(s, placeholders):
    return [ph for ph in placeholders if ph in s]

def expand_value(
    value,
    placeholders,
    _depth=0,
    _seen=None
):
    if _seen is None:
        _seen = set()

    # Find placeholders that actually exist in this string
    present = find_placeholders(value, placeholders)

    # No expandable placeholders -> terminal value
    if not present:
        return {value}

    results = set()
    for ph in present:
        # Avoid infinite self-cycles like {PORT} -> {PORT}
        key = (value, ph)
        if key in _seen:
            continue

        for replacement in placeholders[ph]:
            new_value = value.replace(ph, replacement, 1)

            results.update(
                expand_value(
                    new_value,
                    placeholders,
                    _depth + 1,
                    _seen | {key}
                )
            )
    return results

def expand_values(values, placeholders):
    results = set()
    for v in values:
        results.update(expand_value(v, placeholders))
    return sorted(results)

def expand_directives(directives, placeholders):
    for directive in directives.copy():
        directives[directive] = expand_values(values=directives[directive], placeholders=placeholders)

def deduplicate_by_value(pairs):
    seen = set()
    result = []
    for value, metadata in pairs:
        if value in seen:
            continue
        seen.add(value)
        result.append([value, metadata])
    return result

def remove_mutated_header_from_metadata(mechanism_values):
    for _, metadata in mechanism_values:
        if 'mutated_header' in metadata:
            del metadata['mutated_header']


#### Functionality to handle hashes automatically

# ! For this method to work correctly, has_value and has_directive (and has_directive_values_pair ofc) MUST be lists even if containing only one value
def replace_hash_placeholder_meta(meta, placeholder, replacement):
    m = deepcopy(meta)

    if "has_value" in m:
        m["has_value"] = [
            v.replace(placeholder, replacement) for v in m["has_value"]
        ]
    
    if "has_directive" in m:
        m["has_directive"] = [
            v.replace(placeholder, replacement) for v in m["has_directive"]
        ]

    if "has_directive_values_pair" in m:
        new_pairs = []
        for pair in m["has_directive_values_pair"]:
            new_pairs.append([
                v.replace(placeholder, replacement) for v in pair
            ])
        m["has_directive_values_pair"] = new_pairs

    return m

def replace_all_hashes(prod_items, placeholder, replacements):
    new_items = []
    repl_iter = iter(replacements)

    for v, meta in prod_items:
        v_new = v
        m_new = deepcopy(meta)

        while placeholder in v_new:
            r = next(repl_iter)
            v_new = v_new.replace(placeholder, r, 1)
            m_new = replace_hash_placeholder_meta(m_new, placeholder, r)

        new_items.append([v_new, m_new])

    return new_items

# We have the following facts and cases:
# Facts:
# {SCRIPT_HASH} is replaced with CONSTANTS.SCRIPT_VARIANTS
# {STYLE_HASH} is replaced with CONSTANTS.STYLE_VARIANTS
# Two or more occurences of the same hash placeholder in a mechanism value generate all possible combinations (even if they exist on the same directive or different).
# When both (style & script) hash placeholders exist together, we split to 2 cases:
# 1. We first generate combinations for one of the hash placeholders, e.g., {SCRIPT_HASH}, and during these combinations, we have the {STYLE_HASH} replaced with {CORRECT_STYLE_HASH} ONLY!
# 2. Then we do the opposite.
# Cases:
# 1. script-src '{SCRIPT_HASH}' '{SCRIPT_HASH}' -> all possible combinations (correct, correct), (correct, wrong), (wrong, correct), (wrong, wrong)
# 2. script-src '{SCRIPT_HASH}'; script-src-elem '{SCRIPT_HASH}' -> all possible combinations (correct, correct), (correct, wrong), (wrong, correct), (wrong, wrong)
# 3. style-src '{STYLE_HASH}'; script-src '{SCRIPT_HASH}' -> (correct, correct), (correct, wrong), (correct, invalid), (wrong, correct), (invalid, correct) -> so 5 cases instead of 9
def expand_hash_placeholders(prod):
    script_count = sum(v.count("{SCRIPT_HASH}") for v, _ in prod)
    style_count = sum(v.count("{STYLE_HASH}") for v, _ in prod)

    results = []

    # only script hashes
    if script_count and not style_count:
        for combo in itertools.product(CONSTANTS.SCRIPT_VARIANTS, repeat=script_count):
            results.append(replace_all_hashes(prod, "{SCRIPT_HASH}", combo))

    # only style hashes
    elif style_count and not script_count:
        for combo in itertools.product(CONSTANTS.STYLE_VARIANTS, repeat=style_count):
            results.append(replace_all_hashes(prod, "{STYLE_HASH}", combo))

    # both present so split tests
    elif script_count and style_count:
        # script tests
        prod_fixed_style = [
            (
                v.replace("{STYLE_HASH}", "{CORRECT_STYLE_HASH}"),
                replace_hash_placeholder_meta(meta, "{STYLE_HASH}", "{CORRECT_STYLE_HASH}")
            )
            for v, meta in prod
        ]

        for combo in itertools.product(CONSTANTS.SCRIPT_VARIANTS, repeat=script_count):
            results.append(replace_all_hashes(prod_fixed_style, "{SCRIPT_HASH}", combo))

        # style tests
        prod_fixed_script = [
            (
                v.replace("{SCRIPT_HASH}", "{CORRECT_SCRIPT_HASH}"),
                replace_hash_placeholder_meta(meta, "{SCRIPT_HASH}", "{CORRECT_SCRIPT_HASH}")
            )
            for v, meta in prod
        ]

        for combo in itertools.product(CONSTANTS.STYLE_VARIANTS, repeat=style_count):
            results.append(replace_all_hashes(prod_fixed_script, "{STYLE_HASH}", combo))

    else:
        results.append(list(prod))

    return results

def expand_pair_placeholders(value, meta):
    pairs = [(value, meta)]
    expanded = expand_hash_placeholders(pairs)
    # print(expanded)
    return [p[0] for p in expanded]

####

def parse_descriptions(mechanism, type_s, predefined_description, user_defined_description):
    # General settings
    # test directives
    test_directives = user_defined_description.get('test_directives', []) # if not given then test all
    # no defaults
    no_defaults = user_defined_description.get('no_defaults', False) # if not set then create default valid values
    
    # Common settings
    # delimiters - user-defined description inherits by predefined description
    predefined_delimiters = {
        "directives_delimiter": predefined_description.get("directives_delimiter", " "), # default space
        "directive_values_delimiter": predefined_description.get("directive_values_delimiter", " "), # default space
        "values_delimiter": predefined_description.get("values_delimiter", " "), # default space
    }
    user_defined_delimiters = {
        "directives_delimiter": user_defined_description.get("directives_delimiter", None),
        "directive_values_delimiter": user_defined_description.get("directive_values_delimiter", None),
        "values_delimiter": user_defined_description.get("values_delimiter", None),
    }
    for delim in user_defined_delimiters:
        if user_defined_delimiters[delim] is None:
            user_defined_delimiters[delim] = predefined_delimiters[delim]
    
    # enclose values in parenthesis (e.g., for Permissions-Policy) - user-defined description inherits by predefined description
    enclose_in_parenthesis_predefined = predefined_description.get('enclose_in_parenthesis', False) # if not set then do not enclose generated values in parenthesis
    enclose_in_parenthesis_user_defined = user_defined_description.get('enclose_in_parenthesis', None)
    if enclose_in_parenthesis_user_defined is None:
        enclose_in_parenthesis_user_defined = enclose_in_parenthesis_predefined
    
    # placeholders - overridable (concatenate)
    predefined_placeholders = predefined_description.get('placeholders', {})
    user_defined_placeholders = user_defined_description.get('placeholders', {})
    placeholders = {**predefined_placeholders, **user_defined_placeholders} # override predefined
    
    # constants - overridable (replace)
    predefined_constants = predefined_description.get('constants', [])
    user_defined_constants = user_defined_description.get('constants', None)
    if user_defined_constants is None:
        user_defined_constants = predefined_constants
    constants = user_defined_constants
    
    # directives - overridable (concatenate)
    predefined_directives = predefined_description.get('directives', {})
    if type(predefined_directives) is list:
        predefined_directives = {expanded_key: [] for key in predefined_directives for expanded_key in expand_value(key, placeholders)}
    elif type(predefined_directives) is dict:
        for key in predefined_directives.copy():
            expanded_keys = list(expand_value(key, placeholders))
            if len(expanded_keys) == 1 and expanded_keys[0] == key:
                continue
            for expanded_key in expanded_keys:
                predefined_directives[expanded_key] = predefined_directives[key]
            del predefined_directives[key]
    else:
        print("[ERROR] Field directives can only be dict or list!")
        exit(1)
    user_defined_directives = user_defined_description.get('directives', {})
    if type(user_defined_directives) is list:
        user_defined_directives = {expanded_key: [] for key in user_defined_directives for expanded_key in expand_value(key, placeholders)}
    elif type(user_defined_directives) is dict:
        for key in user_defined_directives.copy():
            expanded_keys = list(expand_value(key, placeholders))
            if len(expanded_keys) == 1 and expanded_keys[0] == key:
                continue
            for expanded_key in expanded_keys:
                user_defined_directives[expanded_key] = user_defined_directives[key]
            del user_defined_directives[key]
    else:
        print("[ERROR] Field directives can only be dict or list!")
        exit(1)
    tmp_directives = {**predefined_directives, **user_defined_directives} # override predefined
    if test_directives:
        directives = create_subdict(d=tmp_directives, keys=test_directives)
    else:
        directives = tmp_directives
    
    # add some more useful placeholders
    if not '{DIRECTIVES}' in placeholders:
        placeholders['{DIRECTIVES}'] = list(tmp_directives.keys())
    if not '{TEST_DIRECTIVES}' in placeholders:
        placeholders['{TEST_DIRECTIVES}'] = list(directives.keys())
    
    # replacement/expansion of the values of the directives with placeholders
    expand_directives(directives=directives, placeholders=placeholders)

    # Generate values based on modes/options
    mechanism_values = generate(mechanism, type_s, user_defined_description, directives, user_defined_delimiters, placeholders, constants, enclose_in_parenthesis_user_defined)
    if not no_defaults:
        mechanism_values += generate(mechanism, type_s, predefined_description, directives, predefined_delimiters, placeholders, constants, enclose_in_parenthesis_predefined)
    return deduplicate_by_value(mechanism_values) # deduplicate

def parse_non_configured_mechanism_description(description):
    placeholders = description.get('placeholders', {})
    # custom values
    custom_values = description.get('custom_values', []) # if set, the values as is (after placeholders replacement) will be added in the beginning of the generated values
    mechanism_values = generate_custom_values(custom_values=custom_values, placeholders=placeholders)
    # run the first deployment without setting this mechanism
    run_without_mechanism_first = description.get('run_without_mechanism_first', False) # if set, the first deployment will not set a value for this mechanism!
    if run_without_mechanism_first:
        mechanism_values.insert(0, [None, {'mechanism_is_not_set': True}])
    return deduplicate_by_value(mechanism_values)

def combinations_generator(description, directives, delimiters, enclose_in_parenthesis):
    mechanism_values = []
    # multiple directives combinations
    multiple_directives = description.get('multiple_directives', None) # if not set then do not generate combinations of directives
    # multiple values combinations
    multiple_values = description.get('multiple_values', None) # if not set then do not generate combinations of values
    
    if multiple_directives is not None or multiple_values is not None: # NOTE: this if statement is needed because in some cases we may not want to test combinations, but only mutations, or duplicates, or custom values. Without that, we would always get combinations of single duplicate-value pairs.
        
        if multiple_directives is None:
            multiple_directives = False
        if multiple_values is None:
            multiple_values = False
        
        # directives combinations limit
        multiple_directives_limit = description.get('multiple_directives_limit', (1, -1)) # if not set then if multiple_directives is True, generate all directives combinations without any limit. When multiple_directives is False, it does not affect.
        # values combinations limit
        multiple_values_limit = description.get('multiple_values_limit', (1, -1)) # if not set then if multiple_values is True, generate all values combinations without any limit. When multiple_values is False, it does not affect.
        # directives combinations with all possible orders
        multiple_directives_all_orders = description.get('multiple_directives_all_orders', False)
        # values combinations with all possible orders
        multiple_values_all_orders = description.get('multiple_values_all_orders', False)
        mechanism_values = generate_combinations(directives_dict=directives, delimiters=delimiters, multiple_directives=multiple_directives, multiple_values=multiple_values, multiple_directives_limit=multiple_directives_limit, multiple_values_limit=multiple_values_limit, multiple_directives_all_orders=multiple_directives_all_orders, multiple_values_all_orders=multiple_values_all_orders, enclose_in_parenthesis=enclose_in_parenthesis)
    return mechanism_values

def merge_descriptions(description_from, description_to):
    new_description = deepcopy(description_to)
    for field in description_from:
        new_description[field] = description_from[field]
    return new_description

def generate(mechanism, type_s, description, directives, delimiters, placeholders, constants, enclose_in_parenthesis):
    mechanism_values = []
    mutation_values = []
    # corner-case/invalid mutations
    corner_case_mutations = description.get('corner_case_mutations', False) # if not set, do not create any invalid mutations to test browser parsers
    if corner_case_mutations:
        mutation_values = generate_corner_case_mutations(mechanism, type_s, directives, delimiters, enclose_in_parenthesis)
    
    # combinations of valid values
    generate_field = description.get('generate')
    if generate_field is None:
        mechanism_values += combinations_generator(description=description, directives=directives, delimiters=delimiters, enclose_in_parenthesis=enclose_in_parenthesis)
    else:
        if type(generate_field) is list: # we allow multiple combination modes to be defined, e.g., (directives combination with single values & single directives with values combinations)
            for generate_obj in generate_field:
                merged_description = merge_descriptions(description_from=generate_obj, description_to=description)
                mechanism_values += combinations_generator(description=merged_description, directives=directives, delimiters=delimiters, enclose_in_parenthesis=enclose_in_parenthesis)

    # duplicate directives
    duplicate_directives = description.get('duplicate_directives', False) # if not set then do not generate values containing duplicate directives
    if duplicate_directives:
        mechanism_values += generate_duplicate_directives(directives_dict=directives,delimiters=delimiters,enclose_in_parenthesis=enclose_in_parenthesis)
    
    mechanism_values += mutation_values # better run mutations after normal values
    mutation_values = None # clear

    # constants -- if set, these values will be concatenated in the beginning of EVERY generated value
    constants = expand_values(values=constants, placeholders=placeholders)
    if constants:
        mechanism_values = generate_concatenated_constants(constants=constants, mechanism_values=mechanism_values)
    remove_mutated_header_from_metadata(mechanism_values) # we needed this metadata field to concatenate correctly and reconstruct the mutated values, but now we don't need it anymore.

    # custom values
    custom_values = description.get('custom_values', []) # if set, the values as is (after placeholders replacement) will be added in the beginning of the generated values
    mechanism_values += generate_custom_values(custom_values=custom_values, placeholders=placeholders)
    
    # run the first deployment without setting this mechanism
    run_without_mechanism_first = description.get('run_without_mechanism_first', False) # if set, the first deployment will not set a value for this mechanism!
    if run_without_mechanism_first:
        mechanism_values.insert(0, [None, {'mechanism_is_not_set': True}])
    return mechanism_values

# We apply mutations (e.g., case changes etc.) on all single directive-value pairs.
def generate_corner_case_mutations(mechanism, type_s, directives, delimiters, enclose_in_parenthesis):
    mutator = Mutator()
    mutated_headers = mutator.run_all([mechanism], header_name_mutation=True) if type_s == 'headers' else {} # mutation on header names
    
    mechanism_values = []
    dv_delim = delimiters["directive_values_delimiter"]

    for directive in directives:
        values = directives[directive]
        values = list(dict.fromkeys(values))
        mech_values_with_metadata = []

        if not values:
            mech_values_with_metadata.append([directive, {"has_directive": [directive]}]) # adding value, metadata!
        else:
            # add all values, but if empty value and enclose_in_parenthesis is true replace it with ()
            mech_values_with_metadata = [[dv_delim.join([directive, '()']), {"has_directive": [directive], "directive_values_delimiter": dv_delim, "has_value": [val], "enclose_value_in_parenthesis": True}] if val == '' and enclose_in_parenthesis else [dv_delim.join([directive, val]), {"has_directive": [directive], "directive_values_delimiter": dv_delim, "has_value": [val]}] for val in values]
            # then also add all values enclosed with parenthesis (we only have single values here)
            if enclose_in_parenthesis:
                for val in values:
                    if val != '':
                        mech_values_with_metadata.append([dv_delim.join([directive, f'({val})']), {"has_directive": [directive], "directive_values_delimiter": dv_delim, "has_value": [val], "enclose_value_in_parenthesis": True}])
        
        for val, metadata in mech_values_with_metadata:
            expanded_pairs = expand_pair_placeholders(value=val, meta=metadata)
            for e_val, e_meta in expanded_pairs:
                for mutated_header, mutated_header_metadata in mutated_headers.items():
                    mechanism_values.append([f"{mutated_header}: {e_val}", {**mutated_header_metadata, **e_meta, "mutated_header": mutated_header}])
                mutated_values = mutator.run_all([e_val]) # mutation on mechanism values
                mechanism_values += [[mut_val, {**mut_meta, **e_meta}] for mut_val, mut_meta in mutated_values.items()]
    
    return mechanism_values

# NOTE: Missing metadata means this feature was not used (e.g., delimiters) or that it can be easily reconstructed and we don't have to store it apriori (e.g., directive_values_pair when has_directive contains only 1 directive)!
def generate_combinations(
        directives_dict,
        delimiters,
        multiple_directives=False,
        multiple_values=False,
        multiple_directives_limit=(1, -1),
        multiple_values_limit=(1, -1),
        multiple_directives_all_orders=False,
        multiple_values_all_orders=False,
        enclose_in_parenthesis=False
    ):

    d_delim = delimiters["directives_delimiter"]
    v_delim = delimiters["values_delimiter"]
    dv_delim = delimiters["directive_values_delimiter"]

    directives = list(directives_dict.keys())

    min_d, max_d = multiple_directives_limit
    if min_d == -1:
        min_d = len(directives)
    if max_d == -1:
        max_d = len(directives)
    if min_d > max_d:
        print(f"[ERROR] Minimum limit is higher than maximum limit.\nMin:{min_d}\nMax:{max_d}")
        exit(-1)

    min_v, max_v = multiple_values_limit
    if min_v == -1:
        min_v = math.inf
    if max_v == -1:
        max_v = math.inf
    if min_v > max_v:
        print(f"[ERROR] Minimum limit is higher than maximum limit.\nMin:{min_v}\nMax:{max_v}")
        exit(-1)

    results = []
    directives_combinations_method = itertools.permutations if multiple_directives_all_orders else itertools.combinations
    values_combinations_method = itertools.permutations if multiple_values_all_orders else itertools.combinations

    # directives combinations
    if multiple_directives:
        dir_sets = []
        for r in range(min(min_d, len(directives)), min(max_d, len(directives)) + 1):
            dir_sets.extend(directives_combinations_method(directives, r))
    else:
        dir_sets = [(d,) for d in directives]

    # values combinations per directive group
    for dir_group in dir_sets:
        parts = []

        g_metadata = {"has_directive": [], "has_directive_values_pair": []}
        if len(dir_group) > 1:
            g_metadata["directives_delimiter"] = d_delim

        for d in dir_group:
            metadata = deepcopy(g_metadata)
            metadata['has_directive'].append(d)
            values = deepcopy(directives_dict[d])

            if not values:
                metadata['has_directive_values_pair'].append([]) # empty list of values means no values for this directive, e.g., SAMEORIGIN.
                parts.append([[d, metadata]])
                continue
            
            metadata['directive_values_delimiter'] = dv_delim
            metadata['has_value'] = []
            for_parts = []
            if '' in values:
                empty_value = f"{d}{dv_delim}()" if enclose_in_parenthesis else f"{d}{dv_delim}"
                metadata_copy = deepcopy(metadata)
                metadata_copy['has_value'].append('')
                if enclose_in_parenthesis:
                    metadata_copy['enclose_in_parenthesis'] = True
                for_parts.append([empty_value, metadata_copy])
                values.remove('') # empty value does not participate in combinations !
            
            if not values: # check after remove if we now have an empty list of values
                parts.append(for_parts)
                continue
            
            vsets = []
            if multiple_values:
                for r in range(min(min_v, len(values)), min(max_v, len(values)) + 1):
                    for combo in values_combinations_method(values, r):
                        metadata_copy = deepcopy(metadata)
                        for v in combo:
                            metadata_copy['has_value'].append(v)
                        if r == 1: # if only single values (r=1) and enclose_in_parenthesis is true then add the single values both with and without parenthesis! e.g., geolocation=* and geolocation=(*)!
                            vsets.append([v_delim.join(combo), metadata_copy])
                            if enclose_in_parenthesis:
                                metadata_copy2 = deepcopy(metadata_copy)
                                metadata_copy2['enclose_in_parenthesis'] = True
                                vsets.append([f"({v_delim.join(combo)})", metadata_copy2])
                        else: # if multiple values though, and enclose_in_parenthesis is true, always enclose them in parenthesis!
                            vsets.append([f"({v_delim.join(combo)})", {**metadata_copy, "values_delimiter": v_delim, "enclose_in_parenthesis": True}] if enclose_in_parenthesis else [v_delim.join(combo), {**metadata_copy, "values_delimiter": v_delim}])
            else:
                for v in values:
                    metadata_copy = deepcopy(metadata)
                    metadata_copy['has_value'].append(v)
                    vsets.append([v, metadata_copy])
                    if enclose_in_parenthesis:
                        v_with_parenthesis = f"({v})"
                        metadata_copy2 = deepcopy(metadata_copy)
                        metadata_copy2['enclose_in_parenthesis'] = True
                        vsets.append([v_with_parenthesis, metadata_copy2])

            for_parts += [[f"{d}{dv_delim}{v}", meta] for v, meta in vsets]
            parts.append(for_parts)

        # cartesian product across directives
        for prod_combinations in itertools.product(*parts):
            prod_combinations_with_replaced_hashes = expand_hash_placeholders(prod_combinations)
            for prod in prod_combinations_with_replaced_hashes:
                if len(prod) == 1:
                    del prod[0][1]['has_directive_values_pair'] # no need to store it, can be reconstructed easily later
                    results.append(prod[0])
                else:
                    meta_pivot = None
                    all_values = []
                    all_has_value = []
                    for i, (v, meta) in enumerate(prod):
                        all_values.append(v)
                        if i == 0:
                            meta_pivot = meta
                            all_has_value.append(deepcopy(meta.get('has_value', [])))
                            continue
                        all_has_value.append(deepcopy(meta.get('has_value', [])))
                        meta_pivot = merge_metadata(meta1=meta_pivot, meta2=meta)
                    meta_pivot['has_directive_values_pair'] = [v for v in all_has_value]
                    results.append([d_delim.join(all_values), meta_pivot])

    return results

def merge_metadata(meta1, meta2): # different values in same fields merged to a list during combinations generation
    keys = set(meta1.keys()).intersection(meta2.keys())
    merged = {**meta1, **meta2}
    for key in keys:
        if meta1[key] == meta2[key]:
            continue
        if type(meta1[key]) is not list:
            meta1[key] = [meta1[key]]
        if type(meta2[key]) is not list:
            meta2[key] = [meta2[key]]
        try:
            merged[key] = list(dict.fromkeys(meta1[key] + meta2[key]))
        except Exception as e:
            pass
    return merged

# NOTE: Duplicates have only 1 directive, with only 2 occurences, and only 1 value per occurence.
# NOTE: Duplicates need the same directive, so apply hash placeholders replacement only on their values.
def generate_duplicate_directives(directives_dict, delimiters, enclose_in_parenthesis):
    mechanism_values = []
    d_delim = delimiters["directives_delimiter"]
    dv_delim = delimiters["directive_values_delimiter"]
    directives = list(directives_dict.keys())

    for directive in directives:
        values = directives_dict[directive]
        expanded_directives = expand_pair_placeholders(directive, {})

        for expanded_directive, _ in expanded_directives:
            metadata = {"has_directive": [expanded_directive], "directives_delimiter": d_delim, "duplicate": True}
            
            if not values:
                value = d_delim.join([expanded_directive, expanded_directive])
                mechanism_values.append([value, metadata])
                continue
            
            combined = [values, values]
            for first_val, second_val in itertools.product(*combined):
                first_values = []
                second_values = []
                if enclose_in_parenthesis:
                    if first_val == '':
                        first_values.append(['()', {"enclose_in_parenthesis": True, "has_value": ['']}])
                    else:
                        first_values.append([first_val, {"has_value": [first_val]}])
                        first_values.append([f"({first_val})", {"enclose_in_parenthesis": True, "has_value": [first_val]}])
                    
                    if second_val == '':
                        second_values.append(['()', {"enclose_in_parenthesis": True, "has_value": ['']}])
                    else:
                        second_values.append([second_val, {"has_value": [second_val]}])
                        second_values.append([f"({second_val})", {"enclose_in_parenthesis": True, "has_value": [second_val]}])
                
                else:
                    first_values.append([first_val, {"has_value": [first_val]}])
                    second_values.append([second_val, {"has_value": [second_val]}])
                
                for (f_v, f_meta), (s_v, s_meta) in itertools.product(first_values, second_values):
                    first_directive = dv_delim.join([directive, f_v])
                    second_directive = dv_delim.join([directive, s_v])

                    input_prod = (
                        [first_directive, {**metadata, **f_meta}],
                        [second_directive, {**metadata, **s_meta}]
                    )
                    # print('Input: ', input_prod)
                    expanded_prod = expand_hash_placeholders(input_prod)
                    for prod in expanded_prod:
                        # prod has length 2, always
                        first_expanded_value = prod[0][0]
                        first_expanded_meta = prod[0][1]
                        second_expanded_value = prod[1][0]
                        second_expanded_meta = prod[1][1]
                        # print('Output: ', [d_delim.join([first_expanded_value, second_expanded_value]), merge_metadata(first_expanded_meta, second_expanded_meta)])
                        mechanism_values.append([d_delim.join([first_expanded_value, second_expanded_value]), merge_metadata(first_expanded_meta, second_expanded_meta)])

    return mechanism_values

def generate_concatenated_constants(constants, mechanism_values):
    concatenated_values = []
    for mechanism_value, metadata in mechanism_values:
        header = f"{metadata['mutated_header']}: " if metadata.get("mutation_in") == "header_name" else ""
        value = mechanism_value.replace(header, "") if header else mechanism_value
        for constant in constants:
            expanded_constants = expand_pair_placeholders(value=constant, meta={})
            for e_constant, _ in expanded_constants:
                metadata['has_prefix'] = e_constant
                concatenated_values.append([header + e_constant + value, deepcopy(metadata)])
    return concatenated_values

def generate_custom_values(custom_values, placeholders):
    new_values = []
    for val in expand_values(values=custom_values, placeholders=placeholders):
        expanded_values = expand_pair_placeholders(value=val, meta={})
        for e_val, _ in expanded_values:
            new_values.append([e_val, {"custom_value": True}])
    return new_values

# NOTE: [Tester] If value from values is: None -> don't set mechanism at all | str -> set 1 mechanism with this value, | list -> set multiple mechanisms with these values. We can also have multiple occurences of the same mechanism now e.g. Set-Cookie & Set-Cookie !
def main(input, output_json, output_database):
    user_defined_descriptions_l = read_json(input)
    final_values_l = []
    for user_defined_description_obj in user_defined_descriptions_l:
        mechanism_str = user_defined_description_obj['mechanism']
        mechanisms_config_str = user_defined_description_obj.get('mechanisms_description', CONSTANTS.CONFIG_FILE)
        predefined_descriptions_obj = read_json(mechanisms_config_str)
        type_str = get_type(mechanism=mechanism_str, config=predefined_descriptions_obj)
        mechanism_values = []
        if type_str != 'other':
            mechanism_values = parse_descriptions(mechanism=mechanism_str, type_s=type_str, predefined_description=predefined_descriptions_obj[type_str][mechanism_str], user_defined_description=user_defined_description_obj)
        else: # not existing in the mechanisms.jsonc
            mechanism_values = parse_non_configured_mechanism_description(description=user_defined_description_obj)
        if not mechanism_values:
            mechanism_values.append([None, {'mechanism_is_not_set': True}])
        print('Total:', len(mechanism_values))
        final_values_l.append({"mechanism": mechanism_str, "values": mechanism_values})
    if output_database:
        write_to_database(database=args.database, data=final_values_l)
    if output_json:
        write_json(config=output_json, data=final_values_l)

if __name__ == '__main__':
    args = get_args()
    print(args)
    main(input=args.config, output_json=args.json, output_database=args.database)
