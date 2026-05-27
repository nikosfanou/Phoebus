from argparse import ArgumentParser
import itertools
import json
import uuid
import copy
import os
from bs4 import BeautifulSoup, Comment, NavigableString, Tag
import re
import esprima
import tinycss2
import time
import shutil
import subprocess

DOMAINS_DICT = {
    '{EXAMPLE}': '<?= $example ?>',
    '{SUB_EXAMPLE}': '<?= $sub_example ?>',
    '{SUB2_EXAMPLE}': '<?= $sub2_example ?>',
    '{CROSSEXAMPLE}': '<?= $crossexample ?>',
    '{SUB_CROSSEXAMPLE}': '<?= $sub_crossexample ?>',
    '{EXAMPLE_IP}': '<?= $example_ip ?>',
    '{SUB_EXAMPLE_IP}': '<?= $sub_example_ip ?>',
    '{SUB2_EXAMPLE_IP}': '<?= $sub2_example_ip ?>',
    '{CROSSEXAMPLE_IP}': '<?= $crossexample_ip ?>',
    '{SUB_CROSSEXAMPLE_IP}': '<?= $sub_crossexample_ip ?>',
}

PORTS_DICT = {
    '{PORT}': '<?= $custom_port ?>',
    '{SSL_PORT}': '<?= $custom_ssl_port ?>',
}

FRAMEWORK_IDS_DICT = {
    '{RESULTS_ID}': '<?= $results_id ?>',
}

AUTO_ID_KEYWORD = "{AUTO.ID}"

def get_html_comments(soup):
    comments = soup.find_all(string=lambda text: isinstance(text, Comment))
    return comments

def remove_html_comments(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    comments = get_html_comments(soup=soup)
    for comment in comments:
        comment.extract()
    return soup.prettify(formatter=None)

def remove_html_comments_from_soup(soup):
    comments = get_html_comments(soup=soup)
    for comment in comments:
        comment.extract()
    return

def read_file(filename):
    try:
        with open(filename, "r") as fp:
            content = fp.read()
    except Exception as e:
        print(f'[ERROR] Could not read from file {filename}...')
        print(e)
        content = None
    return content

def write_file(filename, content):
    try:
        with open(filename, "w") as fp:
            fp.write(content)
    except Exception as e:
        print(f'[ERROR] Could not write to the file {filename}...')
        print(e)
    return

def append_file(filename, content):
    try:
        with open(filename, "a+") as fp:
            fp.write(content)
    except Exception as e:
        print(f'[ERROR] Could not append to the file {filename}...')
        print(e)
    return

def read_config(filename):
    try:
        with open(filename, "r") as fp:
            config = json.load(fp)
    except Exception as e:
        print(e)
        config = None
    return config

def generate_combinations(dictionary):
    attributes = list(dictionary.keys())
    all_lists = []
    for attr in attributes:
        all_lists.append(dictionary[attr])
    # generate all possible combinations
    list_of_tuples = itertools.product(*all_lists)
    combinations = []
    for tupl in list_of_tuples:
        combination = {}
        for index, attr in enumerate(attributes):
            combination[attr] = tupl[index]
        combinations.append(combination)
    return combinations

def generate_uid():
    generated_id = str(uuid.uuid4()).replace('-', '')
    return f"v{generated_id}"

'''
php_value is the pre-generated/replaced tag in string format
php_vars are the names of the php variables (with the symbol \$)
This method replaces the element with a PHP block of code that handles the php variable that is used as attribute value in at least one attribute of the element.
'''
def create_php_blocks(php_value, php_vars, php_internal_index):
    # escape and remove php block chars
    php_value_formatted = php_value.replace('"', '\\"').replace("<?= ", "").replace(" ?>", "")
    output = f"""<?php $_res = ["{php_value_formatted}"];"""
    # add php block for every variable
    for var_str in php_vars:
        var = var_str.replace('\$', '$')
        var_to_replace_str = var.replace("'", "\\'")
        output += f"""
        $_tmp_res = [];
        if (isset({var})) {{
            $_res_len = count($_res);
            for ($_i = 0; $_i < $_res_len; $_i++){{
                if (is_array({var})) {{
                    $_varLength = count({var});
                    for ($_j = 0; $_j < $_varLength; $_j++) {{
                        $_newString = str_replace('{var_to_replace_str}', {var}[$_j], $_res[$_i]);
                        $_newString = str_replace('{php_internal_index}', strval($_j), $_newString);
                        array_push($_tmp_res, $_newString);
                    }}
                }} else {{
                    $_newString = str_replace('{var_to_replace_str}', {var}, $_res[$_i]);
                    $_newString = str_replace('{php_internal_index}', '', $_newString);
                    array_push($_tmp_res, $_newString);
                }}
            }}
        }}
        $_res = $_tmp_res;
        """
    # the combinations of values of all php variables (strings or arrays) are complete, echo them into the html file
    output += """
        for ($_i = 0; $_i < count($_res); $_i++){
            echo $_res[$_i];
        }
    ?>
    """
    return clean_whitespace(output)

def clean_whitespace(text): # remove new lines and undesired spaces and make it one-line
    return re.sub(r'\s+', ' ', text).strip()

def replace_tags_with_php_blocks(soup_obj, tag_php_block_pairs):
    all_tags = soup_obj.find_all()
    for obj in tag_php_block_pairs:
        for tag in all_tags:
            if obj['tag'] == tag:
                tag.replace_with(obj['block'])
                break


### Methods to detect if an element needs sth to be functional.

def detect_required_attributes(element, data):
    for attr in data.keys():
        if attr not in element.attrs:
            return False
    return True

def detect_required_parent(element, data):
    parent_name = data['tag']
    if parent_name == element.parent.name:
        return True
    return False

def detect_required_ancestor(element, data):
    ancestor_name = data['tag']
    current = element
    while current.parent is not None and current.parent.name != '[document]':
        if current.parent.name == ancestor_name:
            return True
        current = current.parent
    return False

def detect_required_child(element, data):
    child_name = data['tag']
    for child in element.children:
        if child.name == child_name:
            return True
    return False

def detect_required_inline_contents(element):
    for content in element.contents:
        if isinstance(content, NavigableString) and not content.strip():
            continue
        else:
            return True
    return False


### Methods to create requirements of an element, e.g., when an element is functional only under a specific parent element.

def create_required_parent(soup, element, data, mandatory_list, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    parent_name = data['tag']
    new_parent = soup.new_tag(parent_name)
    new_parent.attrs['_generated'] = '1'
    element.wrap(new_parent)
    if data.get('no_defaults', False): # if no_defaults is True, then create the new element with the new instructions if any, not the default ones !
        mandatory_list = copy.deepcopy(mandatory_list)
        data = copy.deepcopy(data)
        del data['tag']
        del data['no_defaults']
        mandatory_list[parent_name] = [data] if data else []
    # Newly added element may need its process as well!
    handle_required_attributes_and_elements(soup=soup, element=new_parent, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

def create_required_child(soup, element, data, mandatory_list, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    child_name = data['tag']
    new_child = soup.new_tag(child_name)
    element.append(new_child)
    if data.get('no_defaults', False): # if no_defaults is True, then create the new element with the new instructions if any, not the default ones !
        mandatory_list = copy.deepcopy(mandatory_list)
        data = copy.deepcopy(data)
        del data['tag']
        del data['no_defaults']
        mandatory_list[child_name] = [data] if data else []
    # Newly added element may need its process as well!
    handle_required_attributes_and_elements(soup=soup, element=new_child, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

def create_required_attributes(soup, element, data, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    for attr, value in data.items():
        if attr not in element.attrs:
            element[attr] = value
    attribute_values_combinations = get_only_attribute_values_combinations(element=element, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
    new_elements = generate_new_elements_with_new_attribute_values(soup=soup, element=element, attribute_values_combinations=attribute_values_combinations)
    for new_element in reversed(new_elements):
        if new_element == element: continue
        else: element.insert_after(new_element)
    return new_elements

def create_required_inline_contents(element,data):
    element.append(data)

def create_required_attributes_and_elements(soup, element, condition, results, mandatory_list, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    elements = [element]
    if results[0] is False:
        data = condition['mandatory_attributes']
        elements = create_required_attributes(soup=soup, element=element, data=data, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
    for n_element in elements:
        if results[1] is False:
            data = condition['mandatory_ancestor']
            create_required_parent(soup=soup, element=n_element, data=data, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
        if results[2] is False:
            data = condition['mandatory_parent']
            create_required_parent(soup=soup, element=n_element, data=data, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
        if results[3] is False:
            data = condition['mandatory_child']
            create_required_child(soup=soup, element=n_element, data=data, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
        if results[4] is False:
            data = condition['mandatory_contents']
            create_required_inline_contents(element=n_element, data=data)

def _detect_required_attributes_and_elements(element, condition):
    results = [None, None, None, None, None]
    if 'mandatory_attributes' in condition:
        data = condition['mandatory_attributes']
        results[0] = detect_required_attributes(element=element, data=data)
    if 'mandatory_ancestor' in condition:
        data = condition['mandatory_ancestor']
        results[1] = detect_required_ancestor(element=element, data=data)
    if 'mandatory_parent' in condition:
        data = condition['mandatory_parent']
        results[2] = detect_required_parent(element=element, data=data)
    if 'mandatory_child' in condition:
        data = condition['mandatory_child']
        results[3] = detect_required_child(element=element, data=data)
    if 'mandatory_contents' in condition:
        data = condition['mandatory_contents']
        results[4] = detect_required_inline_contents(element=element)
    return results

def is_generated_element(element):
    return element.attrs.get('_generated') == '1'

def detect_required_attributes_and_elements(soup, element, mandatory_list, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    element_name = element.name
    conditions_list = mandatory_list[element_name]
    made_changes = False
    for condition in conditions_list:
        element_copy = deep_clone_tag(soup, element)
        element.insert_after(element_copy)
        # NOTE: If an element fully meets the condition here skip, no need to generate identical element!
        results = _detect_required_attributes_and_elements(element=element_copy, condition=condition)
        if results.count(False) > 0:
            create_required_attributes_and_elements(soup=soup, element=element_copy, condition=condition, results=results, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
            made_changes = True
            if is_generated_element(element):
                break
    if made_changes:
        element.extract()

def handle_required_attributes_and_elements(soup, element, mandatory_list, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    element_name = element.name
    if element_name not in mandatory_list:
        return
    detect_required_attributes_and_elements(soup=soup, element=element, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

def can_accept_text(element, text_elements_list):
    element_name = element.name
    vanilla_text = "TEXT"
    vanilla_date = "01/01/2025"
    for content in element.contents.copy():
        if isinstance(content, NavigableString):
            if not content.strip():
                element.contents.remove(content)
                # or content.extract()
    contents_len = len(element.contents)
    if not contents_len:
        if element_name in text_elements_list['text']:
            element.append(vanilla_text)
        elif element_name in text_elements_list['date']:
            element.append(vanilla_date)

"""
soup => BeautifulSoup object
main_element => the element from which we will generate the new ones
new_elements => a list of element names for the new elements

Generate new elements while replacing placeholders in element name
"""
def generate_new_elements(soup, main_element, new_elements):
    copy_main_element = create_tag_copy(tag=main_element)
    new_tags = []
    for element in new_elements:
        copy_main_element.name = element
        new_tag = deep_clone_tag(soup=soup, tag=copy_main_element)
        new_tags.append(new_tag)
    if not new_tags:
        new_tags.append(main_element)
    return new_tags

"""
element => an HTML element
attribute_values => a dictionary with the placeholders and the attribute value they should be replaced with

Traverse the element's attributes and if a placeholder exists in the attribute's value, replace it
"""
def replace_attribute_values(element, attribute_values):
    for placeholder, attribute_value in attribute_values.items():
        for attribute in element.attrs:
            if isinstance(element.attrs[attribute], list):
                element.attrs[attribute] = ' '.join(element.attrs[attribute])
            if placeholder in element.attrs[attribute]:
                element.attrs[attribute] = element.attrs[attribute].replace(placeholder, attribute_value)
            element.attrs[attribute] = replace_reserved_environment_placeholders(value=element.attrs[attribute])


"""
soup => BeautifulSoup object
element => the element from which we will generate the new ones
new_attribute_values => a list of dictionaries with the placeholders and the attribute values they should be replaced with

Generate new elements while replacing placeholders in attributes values
"""
def generate_new_elements_with_new_attribute_values(soup, element, attribute_values_combinations):
    element_copy = create_tag_copy(tag=element)
    new_tags = [element]
    for index, attribute_values in enumerate(attribute_values_combinations):
        if index != 0:
            new_tag = create_tag_copy(tag=element_copy)
            replace_attribute_values(element=new_tag, attribute_values=attribute_values)
            new_tags.append(new_tag)
        else:
            replace_attribute_values(element=element, attribute_values=attribute_values)
    return new_tags

"""
element => an HTML element
attributes => a dictionary with the attribute placeholders and the attributes they should be replaced with

Replace placeholders in attributes' name with given value
"""
def replace_attributes(element, attributes):
    for placeholder, attribute in attributes.items():
        element.attrs[attribute] = element.attrs[placeholder]
        del element.attrs[placeholder]


"""
soup => BeautifulSoup object
element => the element from which we will generate the new ones
new_attributes => a list of dictionaries with the placeholders and the attribute they should be replaced with

Generate new elements while replacing placeholders in attributes
"""
def generate_new_elements_with_new_attributes(soup, element, attributes_combinations):
    element_copy = create_tag_copy(tag=element)
    new_tags = [element]
    for index, attributes in enumerate(attributes_combinations):
        if index != 0:
            new_tag = create_tag_copy(tag=element_copy)
            replace_attributes(element=new_tag, attributes=attributes)
            new_tags.append(new_tag)
        else:
            replace_attributes(element=element,attributes=attributes)
    return new_tags

"""
element => the element from which we will generate the new ones
placeholders_dict => dictionary containing placeholders and their values

Get the elements that correspond to the placeholder in element's name
"""
def get_new_elements(element, placeholders_dict):
    placeholder_in_tag_name = None
    for placeholder_name in placeholders_dict:
        if element.name.lower() == placeholder_name.lower():
            placeholder_in_tag_name = placeholder_name
            break
    new_elements = placeholders_dict[placeholder_in_tag_name] if placeholder_in_tag_name is not None else []
    return new_elements

"""
element => the element from which we will generate the new ones
placeholders_dict => dictionary containing placeholders and their values

Get the attributes that correspond to the placeholders in attributes' name
AND
Get the attribute values that correspond to the placeholders in attributes' values
"""
def get_attribute_and_values_combinations(element, placeholders_dict, file_placeholders_dict):
    attributes = element.attrs
    attributes_to_replace = {}
    attribute_values_to_generate = {}
    for attribute, values in attributes.items():
        # Check if attribute name is placeholder and get values
        for placeholder_name in placeholders_dict:
            attribute_lower = attribute.lower()
            placeholder_name_lower = placeholder_name.lower()
            if attribute_lower == placeholder_name_lower:
                attributes_to_replace[placeholder_name] = placeholders_dict[placeholder_name]
                break
        
        if isinstance(values, list):
            values = ' '.join(values)
        
        # Replace first the file placeholders, then the placeholders
        # NOTE: In any case we shouldn't add the same placeholder name both on file_placeholders and on placeholders so we are safe to create 1 dict
        get_file_placeholders_final_texts(text_from_files=attribute_values_to_generate, content=values, placeholders_dict=placeholders_dict,file_placeholders_dict=file_placeholders_dict)
        for placeholder_name in placeholders_dict:
            if placeholder_name in values:
                attribute_values_to_generate[placeholder_name] = placeholders_dict[placeholder_name]
                values = values.replace(placeholder_name, "")
    attribute_values_combinations = generate_combinations(dictionary=attribute_values_to_generate)
    attributes_combinations = generate_combinations(dictionary=attributes_to_replace)
    return attributes_combinations, attribute_values_combinations

# Same with get_attribute_and_values_combinations but only for attribute values
def get_only_attribute_values_combinations(element, original_placeholders_dict, placeholders_dict, file_placeholders_dict):
    attributes = element.attrs
    attribute_values_to_generate = {}
    for _, values in attributes.items():
        if isinstance(values, list):
            values = ' '.join(values)

        get_file_placeholders_final_texts(text_from_files=attribute_values_to_generate, content=values, placeholders_dict=placeholders_dict,file_placeholders_dict=file_placeholders_dict)
        for placeholder_name in original_placeholders_dict:
            if placeholder_name in values:
                attribute_values_to_generate[placeholder_name] = original_placeholders_dict[placeholder_name]
                values = values.replace(placeholder_name, "")
        for placeholder_name in placeholders_dict:
            if placeholder_name in values:
                attribute_values_to_generate[placeholder_name] = placeholders_dict[placeholder_name]
                values = values.replace(placeholder_name, "")
    attribute_values_combinations = generate_combinations(dictionary=attribute_values_to_generate)
    return attribute_values_combinations

def get_file_placeholders_final_texts(text_from_files, content, placeholders_dict, file_placeholders_dict):
    for file_placeholder, texts in file_placeholders_dict.items():
        if file_placeholder in text_from_files:
            continue
        if file_placeholder in content:
            text_from_files[file_placeholder] = []
            for text in texts:
                tmp_txt = text
                nested_text_from_files_to_replace = {}
                # find placeholders inside read text and create combinations
                for placeholder_name in placeholders_dict:
                    if placeholder_name in tmp_txt:
                        nested_text_from_files_to_replace[placeholder_name] = placeholders_dict[placeholder_name]
                        tmp_txt = tmp_txt.replace(placeholder_name, "")
                nested_text_from_files_combinations = generate_combinations(dictionary=nested_text_from_files_to_replace)
                # if no combinations, replace the text as is!
                if not nested_text_from_files_combinations:
                    text_from_files[file_placeholder].append(text)
                else:
                    # else for each combination replace placeholders on text and add it on the list for this file placeholder
                    for combination in nested_text_from_files_combinations:
                        tmp2_txt = text
                        for key,value in combination.items():
                            tmp2_txt = tmp2_txt.replace(key,value)
                        text_from_files[file_placeholder].append(tmp2_txt)

def get_text_combinations(content, placeholders_dict, file_placeholders_dict):
    text_to_replace = {} # this dict will take lists of placeholder values
    text_from_files_to_replace = {}
    # Read text from files to create combinations
    get_file_placeholders_final_texts(text_from_files=text_from_files_to_replace, content=content,placeholders_dict=placeholders_dict,file_placeholders_dict=file_placeholders_dict)
    # Read text from element to create combinations
    for placeholder_name in placeholders_dict:
        if placeholder_name in content:
            text_to_replace[placeholder_name] = placeholders_dict[placeholder_name]
            content = content.replace(placeholder_name, "")
    text_combinations = generate_combinations(dictionary=text_to_replace)
    return text_combinations, text_from_files_to_replace

def escape_closing_tag(element_name, content):
    element_closing = f"</{element_name}>"
    if element_closing in content:
        content = content.replace(element_closing, f"<\/{element_name}>")
    return content

# NOTE: Here {AUTO.ID} may be used as a variable name, so we want to give same value
def replace_element_with_new_text(element, text_combinations, text_from_files):
    for content in element.contents:
        if isinstance(content, NavigableString) and content.strip():
            new_text = replace_with_new_text(content=content, text_combinations=text_combinations, text_from_files=text_from_files)
            # and if the closing of the current element exists in element's string, replace </element> with <\/element> to avoid HTML parser of browsers to mishandle it!
            # e.g., </script> converts to <\/script> inside another <script> !
            text_with_escaped_tags = escape_closing_tag(element_name=element.name, content=new_text)
            if text_with_escaped_tags != content:
                content.replace_with(text_with_escaped_tags)
