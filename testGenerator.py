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

def replace_with_new_text(content, text_combinations, text_from_files):
    # first replace with already generated texts
    for file_placeholder, texts in text_from_files.items():
        total_text = ''
        for text in texts:
            # don't forget to replace the auto id keyword as it may be used in a variable
            if AUTO_ID_KEYWORD in text:
                id = generate_uid()
                text = text.replace(AUTO_ID_KEYWORD, id)
            total_text += f"{text}\n"
        content = content.replace(file_placeholder, total_text)
    
    # then replace the whole element's text with generated combinations
    text = content
    content = ""
    for text_combination in text_combinations:
        tmp_text = text
        for placeholder, value in text_combination.items():
            tmp_text = tmp_text.replace(placeholder, value)
        content += f"{tmp_text}\n"
        if AUTO_ID_KEYWORD in content:
            id = generate_uid()
            content = content.replace(AUTO_ID_KEYWORD, id)
    
    # finally replace with reserved environment (domain and port) placeholders
    content = replace_reserved_environment_placeholders(value=content)
    return content

def generate_new_elements_with_new_text(element, text_combinations, text_from_files):
    new_tags = [element]
    new_tmp_texts = []
    new_texts = []
    tag_string_contents = get_tag_string_contents(tag=element)
    text_from_files_combinations = generate_combinations(dictionary=text_from_files)
    
    # create new text combinations based on file placeholders
    for text_from_file_combination in text_from_files_combinations:
        tmp_tag_string_contents = []
        for tag_string in tag_string_contents:
            for file_placeholder, file_text in text_from_file_combination.items():
                if AUTO_ID_KEYWORD in file_text:
                    id = generate_uid()
                    file_text = file_text.replace(AUTO_ID_KEYWORD, id)
                tag_string = tag_string.replace(file_placeholder, file_text)
            tmp_tag_string_contents.append(tag_string)
        new_tmp_texts.append(tmp_tag_string_contents)
    
    # create new text combinations based on regular placeholders
    for text_combination in text_combinations:
        if not new_tmp_texts:
            new_tmp_texts = [tag_string_contents]
        for tmp_tag_string_contents in new_tmp_texts:
            new_tmp_tag_string_contents = []
            for tmp_text in tmp_tag_string_contents:
                for placeholder, value in text_combination.items():
                    tmp_text = tmp_text.replace(placeholder, value)
                if AUTO_ID_KEYWORD in tmp_text:
                    id = generate_uid()
                    tmp_text = tmp_text.replace(AUTO_ID_KEYWORD, id)
                new_tmp_tag_string_contents.append(tmp_text)
            new_texts.append(new_tmp_tag_string_contents)
    
    # finally replace with reserved environment (domain and port) placeholders
    # and create the new elements
    for index, new_string_contents in enumerate(new_texts):
        if index != 0:
            element_copy = create_tag_copy(tag=element)
            tag_string_contents_copy = get_tag_string_contents(tag=element_copy)
            for item1, item2 in zip(tag_string_contents_copy, new_string_contents):
                item2 = replace_reserved_environment_placeholders(value=item2)
                item2 = escape_closing_tag(element_name=element.name, content=item2)
                # NOTE: item1 is NavigableString
                item1.replace_with(item2)
            new_tags.append(element_copy)
        else:
            for item1, item2 in zip(tag_string_contents, new_string_contents):
                item2 = replace_reserved_environment_placeholders(value=item2)
                item2 = escape_closing_tag(element_name=element.name, content=item2)
                # NOTE: item1 is NavigableString
                item1.replace_with(item2)
    return new_tags

def count_tag_children(tag):
    return len(tag.find_all(recursive=False))  # search on its children only

def create_tag_copy(tag):
    return copy.copy(tag)

def deep_clone_tag(soup, tag):
    # if no nested elements
    if count_tag_children(tag=tag) == 0:
        new_tag = soup.new_tag(tag.name, **tag.attrs)
        # if there are contents, they will be NavigableString objects!
        for content in tag.contents:
            new_tag.append(copy.deepcopy(content))
        return new_tag
    else:
        return BeautifulSoup(str(tag), "html.parser").find()

# Create string to give the whole placeholder list in a "list" format, to be used in files like JavaScript files, e.g., elements.list -> ['a', 'abbr', ...]
def add_placeholders_list_property(placeholders_dict):
    for placeholder in placeholders_dict.copy():
        placeholders_dict[f"{placeholder}.list"] = [json.dumps(placeholders_dict[placeholder])]

def add_other_useful_placeholders():
    other_default_placeholders = {
        "{HTTP_SCHEMES}": [
            "http",
            "https"
        ],
        "{WS_SCHEMES}": [
            "ws",
            "wss"
        ],
        "{EXAMPLE_TEST_HOSTS}": [
            "{EXAMPLE}",
            "{SUB_EXAMPLE}",
            "{CROSSEXAMPLE}",
            "localhost"
        ],
        "{SUBEXAMPLE_TEST_HOSTS}": [
            "{EXAMPLE}",
            "{SUB_EXAMPLE}",
            "{SUB2_EXAMPLE}",
            "{CROSSEXAMPLE}",
            "{SUB_CROSSEXAMPLE}",
            "localhost"
        ],
        "{EXAMPLE_TEST_IPS}": [
            "{EXAMPLE_IP}",
            "{SUB_EXAMPLE_IP}",
            "{CROSSEXAMPLE_IP}",
            "127.0.0.1"
        ],
        "{SUBEXAMPLE_TEST_IPS}": [
            "{EXAMPLE_IP}",
            "{SUB_EXAMPLE_IP}",
            "{SUB2_EXAMPLE_IP}",
            "{CROSSEXAMPLE_IP}",
            "{SUB_CROSSEXAMPLE_IP}",
            "127.0.0.1"
        ],
        "{DEFAULT_PORTS}": [
            "80",
            "443"
        ],
        "{CUSTOM_PORTS}": [
            "{PORT}",
            "{SSL_PORT}"
        ],
        "{NO_SSL_PORTS}": [
            "80",
            "{PORT}"
        ],
        "{ALL_SSL_PORTS}": [
            "443",
            "{SSL_PORT}"
        ],
    }
    other_overridable_placeholders = {
        "{URL}": [
            ""
        ],
        "{BASE_URL}": [
            "{URL}/"
        ],
        "{FRAME_URL}": [
            "{URL}/index.php"
        ],
        "{SRCDOC}": [""],
        "{IMG_URL}": [
            "{URL}/resources/default.jpg"
        ],
        "{ICON_URL}": [
            "{URL}/resources/favicon.ico"
        ],
        "{APPLE_ICON_URL}": [
            "{URL}/resources/apple-touch-icon.png"
        ],
        "{SVG_URL}": [
            "{URL}/resources/default.svg"
        ],
        "{VIDEO_URL}": [
            "{URL}/resources/default.webm"
        ],
        "{AUDIO_URL}": [
            "{URL}/resources/default.wav"
        ],
        "{TRACK_URL}": [
            "{URL}/resources/default.vtt"
        ],
        "{CSS_URL}": [
            "{URL}/resources/default.css"
        ],
        "{FONT_URL}": [
            "{URL}/resources/default.ttf"
        ],
        "{SCRIPT_URL}": [
            "{URL}/resources/default.js"
        ],
        "{JSON_URL}": [
            "{URL}/resources/default.json"
        ],
        "{TEXT_URL}": [
            "{URL}/resources/default.txt"
        ],
        "{XML_URL}": [
            "{URL}/resources/default.xml"
        ],
        "{HTML_URL}": [
            "{URL}/resources/default.html"
        ],
        "{MANIFEST_URL}": [
            "{URL}/resources/site.webmanifest"
        ],
        "{VTT_URL}": [
            "{URL}/resources/default.vtt"
        ],
        "{WASM_URL}": [
            "{URL}/resources/default.wasm"
        ],
        "{WAT_URL}": [
            "{URL}/resources/default.wat"
        ],
        "{EVENT_SOURCE_URL}": [
            "{URL}/resources/sse.php"
        ],
        "{ANCHOR_URL}": ["#"],
        "{AREA_URL}": ["#"],
        "{FORM_ACTION}": ["#"],
        "{PAGE_URL}": ["/"],
        "{ORIGIN_URL}": [
            "https://{EXAMPLE}"
        ],
        "{TARGET_KEYWORD}": [
            "_self",
            "_blank",
            "_parent",
            "_top"
        ],
        "{INPUT_TYPES_NO_IMAGE}": [
            "button",
            "checkbox",
            "color",
            "date",
            "datetime-local",
            "email",
            "file",
            "hidden",
            "month",
            "number",
            "password",
            "radio",
            "range",
            "reset",
            "search",
            "submit",
            "tel",
            "text",
            "time",
            "url",
            "week",
            "datetime"
        ]
        
    }
    other_default_placeholders['{ALL_SCHEMES}'] = other_default_placeholders['{HTTP_SCHEMES}'] + other_default_placeholders['{WS_SCHEMES}']
    other_default_placeholders['{ALL_HOSTS}'] = other_default_placeholders['{SUBEXAMPLE_TEST_HOSTS}']
    other_default_placeholders['{ALL_IPS}'] = other_default_placeholders['{SUBEXAMPLE_TEST_IPS}']
    other_default_placeholders['{ALL_PORTS}'] = other_default_placeholders['{NO_SSL_PORTS}'] + other_default_placeholders['{ALL_SSL_PORTS}']
    return other_default_placeholders, other_overridable_placeholders

def initialize_known_info():
    ELEMENTS_CONFIG = "./configs/extensive-html-elements-list.json"
    EVENTS_CONFIG = "./configs/extensive-html-events-list.json"
    ATTRIBUTES_CONFIG = "./configs/extensive-html-attributes-per-element-list.json"
    TEXT_ELEMENTS_LIST = "./configs/extensive-html-inline-text-elements-list.json"
    MANDATORY_LIST = "./configs/extensive-html-mandatory-attributes-and-elements-list.json"
    mandatory_list = read_config(MANDATORY_LIST)
    text_elements_list = read_config(TEXT_ELEMENTS_LIST)
    elements = read_config(ELEMENTS_CONFIG)
    events = read_config(EVENTS_CONFIG)
    attributes = read_config(ATTRIBUTES_CONFIG)
    known_elements = {
        'elements': []
    }
    known_events = {
        'events': []
    }
    known_attributes = {
        'event_attrs': [],
        'attributes': []
    }
    
    # Creating placeholders for elements
    for type, values in elements.items():
        values = list(dict.fromkeys(values)) # deduplicate
        known_elements[f"elements.{type}"] = values
        known_elements['elements'].extend(values)
    
    # Creating placeholders for events and event attributes
    for type, values in events.items():
        values = list(dict.fromkeys(values)) # deduplicate
        known_events[f"events.{type}"] = values
        known_events['events'].extend(values)
        listener_values = ['on' + value for value in values]
        known_attributes[f'event_attrs.{type}'] = listener_values
        known_attributes['event_attrs'].extend(listener_values)
    
    # Creating placeholders for attributes
    for element_or_type, values in attributes.items():
        values = list(dict.fromkeys(values)) # deduplicate
        known_attributes[f"attributes.{element_or_type}"] = values
        known_attributes['attributes'].extend(values)
    
    # Deduplicate
    known_elements['elements'] = list(dict.fromkeys(known_elements['elements']))
    known_events['events'] = list(dict.fromkeys(known_events['events']))
    known_attributes['event_attrs'] = list(dict.fromkeys(known_attributes['event_attrs']))
    known_attributes['attributes'] = list(dict.fromkeys(known_attributes['attributes']))
    
    print(f"Considering number of elements: {len(known_elements['elements'])}")
    print(f"Considering number of attributes: {len(known_attributes['attributes'])}")
    print(f"Considering number of events and event attributes {len(known_events['events'])}")
    return known_elements, known_events, known_attributes, add_other_useful_placeholders(), mandatory_list, text_elements_list

# similar to populate_known_with_custom method for placeholders
# file placeholders are only used to replace texts inside other files,
# it helps the user not to write the same thing again and again!
def file_placeholders_replacement(file_placeholders_dict):
    file_placeholders_keys = list(file_placeholders_dict.keys())
    for placeholder in file_placeholders_keys:
        texts = file_placeholders_dict[placeholder]
        final_texts = []
        for text in texts:
            tmp = [text]
            while True:
                tmp2 = []
                for tmp_text in tmp.copy():
                    placeholders_exist = {}
                    for placeholder_nested in file_placeholders_keys:
                        # this would cause eternal replacement and overflow in case of user's mistake so avoid it! 
                        if placeholder == placeholder_nested:
                            continue
                        if placeholder_nested in tmp_text:
                            placeholders_exist[placeholder_nested] = file_placeholders_dict[placeholder_nested]
                    if not placeholders_exist:
                        tmp.remove(tmp_text)
                        final_texts.append(tmp_text)
                        continue
                    combinations = generate_combinations(dictionary=placeholders_exist)
                    for combination in combinations:
                        tmp2_text = tmp_text
                        for existing_placeholder, value in combination.items():
                            tmp2_text = tmp2_text.replace(existing_placeholder, value)
                        tmp2.append(tmp2_text)
                if not tmp2:
                    break
                tmp = tmp2
        file_placeholders_dict[placeholder] = final_texts

def find_placeholders_filtered(s, placeholders):
    matches = []

    # collect all matches
    for ph in placeholders:
        start = 0
        L = len(ph)
        while True:
            idx = s.find(ph, start)
            if idx == -1:
                break
            matches.append((idx, idx + L, ph))
            start = idx + 1

    # sort: left to right, prefer longer at same start
    matches.sort(key=lambda x: (x[0], -(x[1] - x[0])))

    accepted = []
    covered_until = -1

    for start, end, ph in matches:
        if start >= covered_until:
            accepted.append((start, end, ph))
            covered_until = end
        # else: overlaps with previous accepted so discard

    # return unique placeholders
    return list({ph for _, _, ph in accepted})

# Recursive
def expand_value(
        value,
        placeholders,
        _depth=0,
        _seen=None
    ):

    if _seen is None:
        _seen = set()

    present = find_placeholders_filtered(value, placeholders)
    if not present:
        return {value}

    results = []
    for ph in present:
        key = (value, ph)
        if key in _seen:
            continue
        for replacement in placeholders[ph]:
            new_value = value.replace(ph, replacement, 1)
            results.extend(
                expand_value(
                    new_value,
                    placeholders,
                    _depth + 1,
                    _seen | {key}
                )
            )
    return results

def expand_values( # expand custom placeholders and set to placeholders dict!
        values,
        placeholders
    ):
    results = []
    for v in values:
        results.extend(expand_value(v, placeholders))
    return results

def merge_user_with_mandatory_placeholders(user_placeholders, mandatory_placeholders):
    merged = dict(user_placeholders)
    for k, v in mandatory_placeholders.items():
        if k not in merged:
            merged[k] = v
    return merged

# known: known_elements / known_attributes / known_events / other known placeholders for default URL schemes, ports, paths, hosts etc.
# custom: user-defined placeholders + some predefined overridable placeholders for frame/script/media etc. URLs !
def populate_known_with_custom(placeholders, custom_placeholders):
    for placeholder in custom_placeholders:
        expanded_values = expand_values(values=custom_placeholders[placeholder], placeholders=placeholders)
        placeholders[placeholder] = expanded_values

def expand_file_placeholders_inside_placeholders(placeholders_dict, file_placeholders_dict):
    for placeholder, values in placeholders_dict.items():
        new_values = []
        for value in values:
            expanded = [value]
            # expand all file placeholders inside this value
            for file_placeholder, file_values in file_placeholders_dict.items():
                tmp_results = []
                for val in expanded:
                    if file_placeholder in val:
                        for file_text in file_values:
                            tmp_results.append(val.replace(file_placeholder, file_text))
                    else:
                        tmp_results.append(val)
                expanded = tmp_results
            new_values.extend(expanded)
        # deduplicate (important to avoid explosion)
        placeholders_dict[placeholder] = list(dict.fromkeys(new_values))


def exclude(placeholders, exclude):
    for placeholder, values in placeholders.items():
        for val in exclude.get(placeholder, []):
            if val in values:
                values.remove(val)

def replace_reserved_environment_placeholders(value):
    # Replace the reserved url placeholders like {EXAMPLE} and {PORT} that existed in template
    for placeholder in DOMAINS_DICT:
        if placeholder in value:
            value = value.replace(placeholder, DOMAINS_DICT[placeholder])
    for placeholder in PORTS_DICT:
        if placeholder in value:
            value = value.replace(placeholder, PORTS_DICT[placeholder])
    for placeholder in FRAMEWORK_IDS_DICT:
        if placeholder in value:
            value = value.replace(placeholder, FRAMEWORK_IDS_DICT[placeholder])
    return value

def handle_php_variables(value, php_vars):
    matches = re.findall(r"\{\$([a-zA-Z_][a-zA-Z0-9_]*(?:\[[^\]]+\]|\->[a-zA-Z_][a-zA-Z0-9_]*)*)\}", value) # find {$var} and return var
    for match in matches:
        # replace the user-defined php variables
        php_variable = f"\${match}"
        value = value.replace(f'{{${match}}}', php_variable)
        php_vars.add(php_variable)
    return value

def find_elements_with_attribute(soup, attribute):
    return soup.find_all(lambda tag: tag.has_attr(attribute))

def find_elements_with_attribute_value(soup, attributes_dict):
    return soup.find_all(attrs=attributes_dict)

def get_tag_string_contents(tag):
    texts = []
    for content in tag.contents:
        if isinstance(content, NavigableString):
            if content.strip():
                texts.append(content)
    return texts

def get_string_contents_before_element(parent, tag_index):
    contents = parent.contents
    if tag_index == 0: # it is the first element, no strings before
        return []
    contents_before = []
    for i in range(tag_index-1, -1, -1): # iterate and store in reverse order
        if isinstance(contents[i], NavigableString):
            if contents[i].strip():
                contents_before.append(contents[i])
        else: # we get string contents until we reach a tag!
            break
    return contents_before

def get_string_contents_after_element(parent, tag_index):
    contents = parent.contents
    contents_len = len(contents)
    if tag_index == contents_len: # it is the last content, no strings after (we don't do tag_index + 1 == contents_len because we have already extracted the current element from its parent contents)
        return []
    contents_after = []
    for i in range(tag_index, contents_len, 1):
        if isinstance(contents[i], NavigableString):
            if contents[i].strip():
                contents_after.append(contents[i])
        else: # we get string contents until we reach a tag!
            break
    return contents_after

def get_exact_index(parent, element):
    for i, child in enumerate(parent.contents):
        if child is element:
            return i
    return -1

def assign_reserved_keywords(soup, tag_php_block_pairs):
    tags = soup.find_all()
    PHP_INTERNAL_KEYWORD = "-{__AUTO.ID.INDEX__}"
    for tag in tags:
        tag.attrs.pop('_generated', None) # NOTE: Remove helper attribute _generated from required parent element handling.
        php_vars = set()
        for attr in tag.attrs:
            if isinstance(tag[attr], list):
                tag[attr] = ' '.join(tag[attr])
            if type(tag[attr]) is not str:
                continue
            
            # find php variable notation in order to replace with a php block
            tag[attr] = handle_php_variables(value=tag[attr], php_vars=php_vars)
            # also replace missed reserved domain and port keywords (missed because no combinations of attribute values were made for the corresponding element so we didn't proceed to replacements)
            tag[attr] = replace_reserved_environment_placeholders(value=tag[attr])
            
            # Replace reserved keyword {AUTO.ID}
            if AUTO_ID_KEYWORD in tag[attr]:
                generated_id = generate_uid()
                if php_vars:
                    generated_id += PHP_INTERNAL_KEYWORD # NOTE: We handle html-attribute mechanisms like integrity, with PHP variables. If these mechanisms take N values, then N elements will be generated, so we need to change a little the ID to be unique for each of  them ! 
                tag[attr] = tag[attr].replace(AUTO_ID_KEYWORD, generated_id)
        
        if 'id' not in tag.attrs: # All elements should have an id !
            generated_id = generate_uid()
            if php_vars:
                generated_id += PHP_INTERNAL_KEYWORD
            tag['id'] = generated_id
        
        tag_string_contents = get_tag_string_contents(tag=tag)
        if tag_string_contents:
            # Also search in element's text
            for text in tag_string_contents:
                tmp_text = text
                tmp_text = handle_php_variables(value=tmp_text, php_vars=php_vars)
                text.replace_with(tmp_text)
        
        if php_vars:
            php_value = tag.prettify(formatter=None)
            php_block = create_php_blocks(php_value=php_value, php_vars=php_vars, php_internal_index=PHP_INTERNAL_KEYWORD)
            tag_php_block_pairs.append({'tag': tag, 'block': php_block})

def restore_duplicate_attributes(html, duplicate_attributes):
    for values in duplicate_attributes.values():
        for attribute, random_uids in values.items():
            for random_uid in random_uids:
                tmp_attribute = f"{attribute}{random_uid}"
                html = html.replace(tmp_attribute, attribute)
    return html

def replace_nth_attr(tag, attr):
    count = 0
    replaced_uids = []

    def replacer(match):
        nonlocal count
        count += 1
        if count == 1:
            return match.group(0)  # Keep first attribute unchanged
        random_id = generate_uid()
        replaced_uids.append(random_id)
        return f'{attr}{random_id}' # Rename the rest like onloadv123, onloadv456, etc.
    
    # use re.escape to escape special characters like . (dot) inside attribute name
    pattern = rf'\b{re.escape(attr)}\b'
    return re.sub(pattern, replacer, tag, count=0), replaced_uids

# As BeautifulSoup doesn't support duplicate attributes, e.g., <script onload="..." onload="...">, in order to support it we initially change the next N-1 occurrences by adding a random UID so that we can parse and handle with BeautifulSoup, and before extracting the final tests, we reconstruct these attribute names (restore_duplicate_attributes).
def rename_duplicate_attributes(html):
    attribute_pattern = re.compile(
        r'([A-Za-z0-9_.:-]+)(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s"\'=<>`]+))?'
    )

    duplicates = {}
    def process_tag(match):
        attribute_replaced_names = {}
        tag = match.group(0)
        modified_tag = tag
        # Find all attributes in the tag
        attributes = attribute_pattern.findall(tag)
        attributes.pop(0)
        already_replaced = []
        for attr in attributes:
            if attr in already_replaced:
                continue
            is_duplicate = attributes.count(attr) != 1
            if not is_duplicate:
                continue
            modified_tag, attribute_replaced_names[attr] = replace_nth_attr(tag=modified_tag, attr=attr)
            already_replaced.append(attr)
        if attribute_replaced_names:
            key = BeautifulSoup(modified_tag, 'html.parser').find() # get and store with the tag object
            duplicates[key] = attribute_replaced_names
        return modified_tag

    # Regex to find tags. Does not match comments and does not match ending tag (>) inside attribute value, e.g., </iframe> inside <iframe srcdoc> doesn't close the level-1 iframe!
    TAG_PATTERN = re.compile(
        r'<\s*[\w\.-]+(?:\s+[\w\:\.-]+(?:\s*=\s*(?:"[^"]*"|\'[^\']*\'|[^\s>]+))?)*\s*/?>',
        re.DOTALL
    )
    processed_html = re.sub(TAG_PATTERN, process_tag, html)

    return processed_html, duplicates

def are_tags_equal_ignoring_contents(tag1, tag2):
    return tag1.name == tag2.name and tag1.attrs == tag2.attrs

"""
NOTE: If we have duplicate attributes and these attributes are placeholders, we will have some duplicate combinations (e.g., onload onerror and onerror onload). We only need to keep 1 occurrence (the 1st)!
Why ? Because even if we kept both, BeautifulSoup sorts the attribute names in alphabetical order, and thus we would have exact same elements (duplicates)!
"""
def discard_duplicate_attribute_combinations(attributes_combinations, duplicates):
    uids = set([item for sublist in duplicates.values() for item in sublist])
    unique_combinations = []
    for combination in attributes_combinations.copy():
        unique_attributes = set()
        for attr in combination.values():
            break_flag = False
            for uid in uids:
                if attr.endswith(uid):
                    unique_attributes.add(attr.replace(uid, ""))
                    break_flag = True
                    break
            if break_flag is False:
                unique_attributes.add(attr)
        if unique_attributes not in unique_combinations:
            unique_combinations.append(unique_attributes)
        else:
            attributes_combinations.remove(combination)

        
def remove_comments_from_text(text_type:str, text:str):
    if text_type == 'js':
        return remove_javascript_comments(js_code=text)
    elif text_type == 'css':
        return remove_css_comments(css_code=text)
    elif text_type == 'html' or text_type == 'php':
        return remove_html_comments(html_content=text)
    return text

def remove_comments_from_element_text(element:str, text:str):
    if element == 'script':
        return remove_javascript_comments(js_code=text)
    elif element == 'style':
        return remove_css_comments(css_code=text)
    return text

def remove_javascript_comments(js_code):
    tokens = esprima.tokenize(js_code, { "comment": True })
    for token in tokens:
        if token.type == 'BlockComment':
            value = '/*' + token.value + '*/'
            js_code = js_code.replace(value, '')
        elif token.type == 'LineComment':
            value = '//' + token.value
            js_code = js_code.replace(value, '')
    return js_code

def remove_css_comments(css_code):
    rules = tinycss2.parse_stylesheet(css_code, skip_comments=True)
    clean_css = tinycss2.serialize(rules)
    return clean_css

def split_by_counter(items, counter):
    less, greater = [], []
    for item in items:
        if item["counter"] < counter:
            less.append(item)
        elif item["counter"] > counter:
            greater.append(item)
    return less, greater

def indexed_filename(filename, index, index_prefix=""):
    if filename.endswith(".once.php"):
        base = filename[:-9]  # remove ".once.php"
        return f"{base}_{index_prefix}{index}.once.php"
    else:
        base, ext = os.path.splitext(filename)
        return f"{base}_{index_prefix}{index}{ext}"

def handle_isolation(soup, output_filename, soup_files_pairs):
    all_nodes = soup.find_all(True) # all elements in DOM order
    isolated_elements = []
    preserved_elements = []
    counter = 0
    for elem in all_nodes:
        inside = False
        if elem.has_attr("isolated"):
            isolated_elements.append({"counter": counter, "element": elem, "ancestors": get_ancestors_chain(element=elem)})
            inside = True
        if elem.has_attr("preserved"):
            preserved_elements.append({"counter": counter, "element": elem, "ancestors": get_ancestors_chain(element=elem)})
            inside = True
        if inside: # NOTE: by doing this, and by filtering (not including) the == in split_by_counter, we filter out of preserved_elements list any element that has both the isolated and preserved attribute. In this way, for this certain isolated element we won't have it duplicate because it is also a preserved element, however it will be included in other isolated elements!
            counter += 1
    if not isolated_elements:
        return
    new_soups = extract_isolated_elements(isolated_elements=isolated_elements, preserved_elements=preserved_elements)
    for index, new_soup in enumerate(new_soups):
        changed_output_filename = indexed_filename(filename=output_filename, index=index + 1, index_prefix="iso_") # files created due to isolation are marked with iso_#
        soup_files_pairs.append({'file': changed_output_filename, "soup": new_soup})
    
def remove_attribute_from_elements(soup, attribute):
    elements = find_elements_with_attribute(soup=soup, attribute=attribute)
    for element in elements:
        del element.attrs[attribute]

def get_ancestors_chain(element):
    current = element
    parent_hierarchy = []
    while current.parent is not None:
        if current.parent.name == '[document]':
            break
        parent_hierarchy.append(current.parent)
        current = current.parent
    return parent_hierarchy

# NOTE: ancestors_already_added_set keeps track of matching ancestors between the old and the new tree for reference and to not duplicate common ancestors
def match_old_with_new_ancestor(old_ancestor, ancestors_already_added_set):
    for ancestors_pair in ancestors_already_added_set:
        old_parent = ancestors_pair[0]
        new_parent = ancestors_pair[1]
        if old_ancestor == old_parent:
            return new_parent
    return None

def add_element_ancestors_tree(soup, element, ancestors_tree, ancestors_already_added_set):
    new_element = create_tag_copy(tag=element)
    new_parent = soup
    for parent in reversed(ancestors_tree):
        tmp_parent = match_old_with_new_ancestor(old_ancestor=parent, ancestors_already_added_set=ancestors_already_added_set)
        if tmp_parent is None:
            new_tag = soup.new_tag(parent.name, attrs=parent.attrs)
            new_parent.append(new_tag)
            new_parent = new_tag
            ancestors_already_added_set.add((parent, new_tag))
        else:
            new_parent = tmp_parent
    new_parent.append(new_element)

# NOTE: We do not keep sibling elements on isolation, only the descendants, and the direct ancestors chain until root.
def extract_isolated_elements(isolated_elements, preserved_elements):
    new_soups = []
    for isolated_dict in isolated_elements:
        isolated_element = isolated_dict['element']
        parent_hierarchy = isolated_dict['ancestors']
        new_soup_obj = BeautifulSoup("", "html.parser")
        ancestors_already_added_set = set()
        prev_preserved, next_preserved = split_by_counter(items=preserved_elements, counter=isolated_dict['counter'])
        # Add ancestors tree of preserved elements before the current isolated one in the DOM tree order
        for previous in prev_preserved:
            add_element_ancestors_tree(soup=new_soup_obj, element=previous['element'], ancestors_tree=previous['ancestors'], ancestors_already_added_set=ancestors_already_added_set)
        # Add ancestors tree of current isolated element
        add_element_ancestors_tree(soup=new_soup_obj, element=isolated_element, ancestors_tree=parent_hierarchy, ancestors_already_added_set=ancestors_already_added_set)
        # Add ancestors tree of preserved elements after the current isolated one in the DOM tree order
        for next in next_preserved:
            add_element_ancestors_tree(soup=new_soup_obj, element=next['element'], ancestors_tree=next['ancestors'], ancestors_already_added_set=ancestors_already_added_set)
        remove_attribute_from_elements(soup=new_soup_obj, attribute='isolated')
        remove_attribute_from_elements(soup=new_soup_obj, attribute='preserved')
        new_soups.append(new_soup_obj)
    for isolated_dict in isolated_elements:
        isolated_dict['element'].extract()
    return new_soups

def is_leaf(tag):
    return isinstance(tag, Tag) and not tag.find()

def get_leaf_nodes(tag):
    return [t for t in tag.descendants if is_leaf(t)]

def handle_limit_elements_size(soup_files_pairs, max_elements):
    updated_soup_files_pairs = []
    for soup_files_pair in soup_files_pairs:
        soup = soup_files_pair['soup']
        output_filename = soup_files_pair['file']
        all_nodes = soup.find_all(True)
        if len(all_nodes) <= max_elements:
            updated_soup_files_pairs.append(soup_files_pair)
            continue

        # Create a soup with only the preserved elements
        preserved_only = find_elements_with_attribute(soup=soup, attribute="preserved")
        preserved_only_soup = BeautifulSoup("", "html.parser")
        preserved_ancestors_already_added_set = set()
        for preserved_elem in preserved_only:
            preserved_elem_ancestors_tree = get_ancestors_chain(preserved_elem)
            add_element_ancestors_tree(soup=preserved_only_soup, element=preserved_elem, ancestors_tree=preserved_elem_ancestors_tree, ancestors_already_added_set=preserved_ancestors_already_added_set)            
        
        # Calculate how many elements we will have in every generated page derived by this page
        all_preserved_count = len(preserved_only_soup.find_all(True))
        if all_preserved_count > max_elements:
            raise Exception("The amount of the 'preserved' elements are more than the max elements size given")
        new_max_elements_size = max_elements - all_preserved_count
        new_soups = []
        new_soup = BeautifulSoup("", "html.parser")
        counter = 0
        at_least_one_path = False
        ancestors_already_added_set = set()
        previous_preserved = []
        
        for elem in all_nodes:
            
            if elem.has_attr("preserved"):
                ancestors_tree = get_ancestors_chain(element=elem)
                add_element_ancestors_tree(soup=new_soup, element=elem, ancestors_tree=ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
                previous_preserved.append((elem, ancestors_tree))
            
            elif is_leaf(tag=elem):
                ancestors_tree = get_ancestors_chain(element=elem)
                new_ancestors_counter = calculate_new_ancestors(ancestors_tree=ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
                counter += 1 + new_ancestors_counter
                
                if counter <= new_max_elements_size:
                    at_least_one_path = True
                    add_element_ancestors_tree(soup=new_soup, element=elem, ancestors_tree=ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
                
                else: # exceeds limit so it cannot be added in this soup, it will be added in the next!            
                    if at_least_one_path is False: # correctness check
                        raise Exception("This elements' path cannot be added to a different page without exceeding the elements size limit set by you. Please increase the limit!")
                    index = len(previous_preserved)
                    next_preserved = preserved_only[index:]
                    
                    for next in next_preserved:
                        next_ancestors_tree = get_ancestors_chain(element=next)
                        add_element_ancestors_tree(soup=new_soup, element=next, ancestors_tree=next_ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
                    
                    new_soups.append(new_soup)
                    new_soup = BeautifulSoup("", "html.parser")
                    at_least_one_path = False
                    ancestors_already_added_set = set()
                    counter = 1 + new_ancestors_counter
                    
                    if counter > new_max_elements_size:
                        raise Exception("This elements' path cannot be added to a different page without exceeding the elements size limit set by you. Please increase the limit!")
                    else:
                        for preserved_elem, preserved_elem_ancestors_tree in previous_preserved:
                            add_element_ancestors_tree(soup=new_soup, element=preserved_elem, ancestors_tree=preserved_elem_ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
                        at_least_one_path = True
                        add_element_ancestors_tree(soup=new_soup, element=elem, ancestors_tree=ancestors_tree, ancestors_already_added_set=ancestors_already_added_set)
        
        new_soups.append(new_soup)
        for index, new_soup in enumerate(new_soups):
            if index == 0:
                changed_output_filename = output_filename
            else:
                changed_output_filename = indexed_filename(filename=output_filename, index=index, index_prefix="lim_") # files created due to limits in total elements size are marked with lim_#
            updated_soup_files_pairs.append({'file': changed_output_filename, "soup": new_soup})
    return updated_soup_files_pairs

def calculate_new_ancestors(ancestors_tree, ancestors_already_added_set):
    counter = 0
    for ancestor in ancestors_tree:
        if match_old_with_new_ancestor(old_ancestor=ancestor, ancestors_already_added_set=ancestors_already_added_set):
            break
        else:
            counter += 1
    return counter

def handle_file(content, placeholders_dict, file_placeholders_dict, output_path, output_filename):
    text_combinations, text_from_files = get_text_combinations(content=content, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
    content = replace_with_new_text(content=content, text_combinations=text_combinations, text_from_files=text_from_files)
    write_file(os.path.join(output_path, output_filename), content)

def handle_js_test(content, placeholders_dict, file_placeholders_dict, output_path, output_filename):
    content = remove_javascript_comments(js_code=content)
    handle_file(content=content, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict, output_path=output_path, output_filename=output_filename)

def handle_css_test(content, placeholders_dict, file_placeholders_dict, output_path, output_filename):
    content = remove_css_comments(css_code=content)
    handle_file(content=content, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict, output_path=output_path, output_filename=output_filename)

def handle_php_test(html_content, placeholders_dict, file_placeholders_dict, original_placeholders_dict, output_path, output_filename, mandatory_list, text_elements_list, use_case_path, max_elements_limit = None):
    # preprocess html and replace duplicate attributes with a random uid
    preprocessed_html_content, duplicate_attributes = rename_duplicate_attributes(html=html_content)
    soup = BeautifulSoup(preprocessed_html_content, 'html.parser')
    remove_html_comments_from_soup(soup=soup)
    elements_in_html = soup.find_all()
    elements_stats = f"Test file: {output_filename}\nStart Total Elements: {len(elements_in_html)}\n"
    elements_in_html.reverse() # for performance efficiency because child elements with placeholders are replaced/generated only once
    counter = 0
    for element in elements_in_html:
        parent_element = element.parent
        element_index = get_exact_index(parent=parent_element, element=element)
        generate_mandatory_data = True if element.name in original_placeholders_dict else False
        element.extract()
        # NOTE: Must call count_tag_children() after extract()
        element_has_siblings = bool(count_tag_children(tag=parent_element))
        # NOTE: As we use insert/append to keep the order of elements, we must use a similar approach for texts (before/after or in-between elements) to keep the order!
        if element_has_siblings:
            sibling_string_contents = get_string_contents_before_element(parent=parent_element, tag_index=element_index)
        else:
            sibling_string_contents = get_string_contents_after_element(parent=parent_element, tag_index=element_index)
        
        # NOTE: So we extract the needed sibling NavigationString objects and we will re-append/insert again later!
        for sibling_string_content in sibling_string_contents:
            sibling_string_content.extract()
        final_generated_tags = []
        new_tmp_placeholders = []
        parsed_element_with_duplicates = None
        # NOTE: if e.g., attributes placeholder exists twice in an element, we have already preprocessed the html code to change the name of the second occurrence like <tag attributes="" attributes{UID}="" />
        # We check if duplicate attribute is a placeholder, and add in the end of its values the same unique identifier, we also update duplicate_attributes with the new attributes.
        for parsed_element in duplicate_attributes:
            if are_tags_equal_ignoring_contents(tag1=element, tag2=parsed_element):
                parsed_element_with_duplicates = parsed_element
                for original_attr, replaced_uids in duplicate_attributes[parsed_element].copy().items():
                    if original_attr in placeholders_dict:
                        for random_uid in replaced_uids:
                            tmp_attr = f"{original_attr}{random_uid}"
                            new_tmp_placeholders.append(tmp_attr)
                            placeholders_dict[tmp_attr] = []
                            for placeholder_value in placeholders_dict[original_attr]:
                                placeholders_dict[tmp_attr].append(f"{placeholder_value}{random_uid}")
                                duplicate_attributes[parsed_element][placeholder_value] = duplicate_attributes[parsed_element][original_attr]
                        del duplicate_attributes[parsed_element][original_attr]
        
        # Get combinations of attributes and attribute values for expansion.
        attributes_combinations, attribute_values_combinations = get_attribute_and_values_combinations(element=element, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

        if parsed_element_with_duplicates is not None:
            discard_duplicate_attribute_combinations(attributes_combinations=attributes_combinations, duplicates=duplicate_attributes[parsed_element_with_duplicates])

        tag_string_contents = get_tag_string_contents(tag=element)
        if not tag_string_contents:
            text_combinations, text_from_files = [{}, {}]
        else:
            tag_string_contents_single_string = ""
            for tag_string in tag_string_contents:
                if not tag_string.strip():
                    tag_string_contents_single_string += tag_string
                    continue
                # remove comments from element's text (if element is script or style)
                tag_string_no_comments = remove_comments_from_element_text(element=element.name, text=tag_string)
                tag_string.replace_with(tag_string_no_comments)
                tag_string_contents_single_string += tag_string

            # Get inline contents combinations for expansion.
            text_combinations, text_from_files = get_text_combinations(content=tag_string_contents_single_string, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

        # First replace element placeholders
        new_elements = get_new_elements(element=element, placeholders_dict=placeholders_dict)
        new_tags = generate_new_elements(soup=soup, main_element=element, new_elements=new_elements)
        # NOTE: new_tags includes element so it will always execute the for loop
        for tmp_tag in new_tags:
            # Second replace attribute values placeholders
            # NOTE: tmp_tags_with_replaced_attribute_values includes tmp_tag so it will always execute the for loop
            tmp_tags_with_replaced_attribute_values = generate_new_elements_with_new_attribute_values(soup=soup, element=tmp_tag, attribute_values_combinations=attribute_values_combinations)
            for tmp2_tag in tmp_tags_with_replaced_attribute_values:
                # Third replace attribute placeholders
                tmp_tags_with_replaced_attributes = generate_new_elements_with_new_attributes(soup=soup, element=tmp2_tag, attributes_combinations=attributes_combinations)
                for tmp3_tag in tmp_tags_with_replaced_attributes:
                    tmp3_tag_string_contents = get_tag_string_contents(tag=tmp3_tag)
                    counter += 1
                    if not tmp3_tag_string_contents:
                        final_generated_tags.append(tmp3_tag)
                        continue
                    # Fourth replace text placeholders
                    final_tags = generate_new_elements_with_new_text(element=tmp3_tag, text_combinations=text_combinations, text_from_files=text_from_files)
                    final_generated_tags += final_tags
        
        # Add elements in soup!
        if element_has_siblings:
            # use insert(0) if element has siblings to keep correct order!
            final_generated_tags.reverse()
            for final_generated_tag in final_generated_tags:
                parent_element.insert(0, final_generated_tag)
                # Add mandatory attributes/parent/child elements
                if generate_mandatory_data:
                    handle_required_attributes_and_elements(soup=soup, element=final_generated_tag, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
                    can_accept_text(element=final_generated_tag, text_elements_list=text_elements_list)
            # re-insert string contents
            for sibling_string_content in sibling_string_contents:
                parent_element.insert(0, sibling_string_content)
        else:
            # else if no siblings, use append() for better performance
            for final_generated_tag in final_generated_tags:
                parent_element.append(final_generated_tag)
                # Add mandatory attributes/parent/child elements
                if generate_mandatory_data:
                    handle_required_attributes_and_elements(soup=soup, element=final_generated_tag, mandatory_list=mandatory_list, original_placeholders_dict=original_placeholders_dict, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)
                    can_accept_text(element=final_generated_tag, text_elements_list=text_elements_list)
            # re-append string contents
            for sibling_string_content in sibling_string_contents:
                parent_element.append(sibling_string_content)
        for new_tmp_placeholder in new_tmp_placeholders:
            del placeholders_dict[new_tmp_placeholder]
    
    soup_files_pairs = []
    # check if some tags need to be tested in isolation
    handle_isolation(soup=soup, output_filename=output_filename, soup_files_pairs=soup_files_pairs)
    # add the main soup object too
    soup_files_pairs.insert(0, {'file': output_filename, "soup": soup })
    # check if we must limit the elements size per page
    if max_elements_limit and max_elements_limit > 0:
        soup_files_pairs = handle_limit_elements_size(soup_files_pairs=soup_files_pairs, max_elements=max_elements_limit)
    elements_stats += f"Final Total Test files derived by this template: {len(soup_files_pairs)}\n"
    count_total_elements = 0
    
    # for each soup_object, replace any tags that contain php var values with the corresponding php block code and write on file
    for soup_file_pair in soup_files_pairs:
        remove_attribute_from_elements(soup=soup_file_pair["soup"], attribute='preserved')
        tag_php_block_pairs = []
        assign_reserved_keywords(soup=soup_file_pair['soup'], tag_php_block_pairs=tag_php_block_pairs)
        count_total_elements += len(soup_file_pair['soup'].find_all())
        replace_tags_with_php_blocks(soup_obj=soup_file_pair['soup'], tag_php_block_pairs=tag_php_block_pairs)
        postprocess_html_content = restore_duplicate_attributes(html=soup_file_pair['soup'].prettify(formatter=None), duplicate_attributes=duplicate_attributes) # formatter = None so that < will not be displayed as &lt
        write_file(os.path.join(output_path, soup_file_pair['file']), postprocess_html_content)
    
    elements_stats += f"Final Total Elements (in all test files): {count_total_elements}\n\n"
    print(elements_stats)
    append_file(os.path.join(use_case_path, "stats.txt"), elements_stats)

def create_test(content, placeholders_dict, file_placeholders_dict, original_placeholders_dict, output_path, output_filename, mandatory_list, text_elements_list, use_case_path, max_elements_limit=None):
    if output_filename.endswith('.js'):
        handle_js_test(content=content, placeholders_dict=placeholders_dict,
            file_placeholders_dict=file_placeholders_dict, output_path=output_path,
            output_filename=output_filename)
    elif output_filename.endswith('.css'):
        handle_css_test(content=content, placeholders_dict=placeholders_dict,
            file_placeholders_dict=file_placeholders_dict, output_path=output_path,
            output_filename=output_filename)
    elif output_filename.endswith('.html') or output_filename.endswith('.php'):
        handle_php_test(html_content=content, placeholders_dict=placeholders_dict,
            file_placeholders_dict=file_placeholders_dict, original_placeholders_dict=original_placeholders_dict,
            output_path=output_path, output_filename=output_filename,
            mandatory_list=mandatory_list, text_elements_list=text_elements_list,
            max_elements_limit=max_elements_limit, use_case_path=use_case_path)
    else:
        handle_file(content=content, placeholders_dict=placeholders_dict,
            file_placeholders_dict=file_placeholders_dict, output_path=output_path,
            output_filename=output_filename)

def read_file_and_create_test(input_filepath, output_path, output_filename, placeholders_dict, file_placeholders_dict, original_placeholders_dict, mandatory_list, text_elements_list, use_case_path, max_elements_limit=None):
    content = read_file(input_filepath)
    if content is None:
        exit(1)
    if content.strip():
        create_test(content=content, placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict, original_placeholders_dict=original_placeholders_dict, output_path=output_path, output_filename=output_filename, mandatory_list=mandatory_list, text_elements_list=text_elements_list, max_elements_limit=max_elements_limit, use_case_path=use_case_path)

def call_cloc(path, not_match=None): # for LoC stats etc.
    cmd = ["cloc", path]
    if not_match:
        cmd += ["--fullpath", f"--not-match-d={not_match}"]
    
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True
    )
    return result.stdout

def generate_tests(config):
    # read from pre-defined configs
    known_elements, known_events, known_attributes, (other_useful_default_placeholders, other_useful_overridable_placeholders), mandatory_list, text_elements_list = initialize_known_info()
    for test in config:
        start = time.time()
        use_case_path = test.get('use_case', None)
        if use_case_path is None:
            print('[ERROR] Use case path was not given in config!')
            exit(1)
        use_case_path = os.path.join("use-cases", use_case_path)
        templates_path = os.path.join(use_case_path, 'templates')
        tests_path = os.path.join(use_case_path, 'tests')
        prototypes_path = os.path.join(tests_path, "prototypes")
        if not os.path.exists(templates_path):
            print(f'[ERROR] Folder `templates` is missing for use case path: `{use_case_path}`!')
            exit(1)
        
        write_file(os.path.join(use_case_path, 'stats.txt'), "")
        # Call cloc for statistic on templates
        template_stats = "\nStatistics for Templates:\n" + call_cloc(path=templates_path, not_match='/prototypes/')
        
        # Config arguments
        options = test.get('html', {})
        user_placeholders_dict = options.get('placeholders', {})
        file_placeholders_dict = options.get('file_placeholders', {})
        exclude_placeholders_dict = options.get('exclude', {})
        max_elements_limit = options.get('max_elements_limit', None)
        placeholders_dict = {**known_elements, **known_events, **known_attributes}
        original_placeholders_dict = copy.deepcopy(placeholders_dict)
        
        placeholders_dict = {**placeholders_dict, **other_useful_default_placeholders}
        user_placeholders_dict = merge_user_with_mandatory_placeholders(user_placeholders=user_placeholders_dict, mandatory_placeholders=other_useful_overridable_placeholders)
        # Store here ALL placeholders (custom and reserved)
        populate_known_with_custom(placeholders=placeholders_dict, custom_placeholders=user_placeholders_dict)
        del user_placeholders_dict
        
        # Exclude values from placeholders, this is to help user remove elements/attributes from reserved placeholders/values but it is used for all placeholders as well
        exclude(placeholders=placeholders_dict, exclude=exclude_placeholders_dict)
        
        # NOTE: Add .list property on placeholders to return them as lists in a string format, mainly for javascript usage.
        add_placeholders_list_property(placeholders_dict=placeholders_dict)
        print("Considering number of placeholders: ", len(list(placeholders_dict.keys())))
        
        # NOTE: Sort by length descending to avoid prefix collisions!
        placeholders_dict = dict(sorted(placeholders_dict.items(), key=lambda item: -len(item[0])))
        file_placeholders_dict = dict(sorted(file_placeholders_dict.items(), key=lambda item: -len(item[0])))
        
        # Copy ALL template files to tests folder to start processing
        shutil.copytree(templates_path, tests_path, dirs_exist_ok=True)
        # NOTE: Prioritize file_placeholders files as they will be used inside other files
        for file_placeholder_values in file_placeholders_dict.values():
            for index, filename in enumerate(file_placeholder_values):
                filename = os.path.normpath(filename)
                dirname = os.path.dirname(filename)
                if dirname.startswith('/'):
                    dirname = dirname[1:]
                output_path = os.path.join(prototypes_path, dirname)
                output_filename = os.path.basename(filename)
                output_file_complete_path = os.path.join(output_path, output_filename)
                # NOTE: We only process files from folder partial
                if dirname == "partial":
                    read_file_and_create_test(input_filepath=output_file_complete_path,
                        output_path=output_path, output_filename=output_filename,
                        placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict,
                        original_placeholders_dict=original_placeholders_dict,
                        mandatory_list=mandatory_list, text_elements_list=text_elements_list,
                        max_elements_limit=max_elements_limit, use_case_path=use_case_path
                    )
                # remove relative path and add corresponding post-process text
                file_placeholder_values.pop(index)
                text = read_file(filename=output_file_complete_path)
                if text is None:
                    print(f'[ERROR] File: {filename} does not exist or not able to open it!')
                    exit(1)
                extension = filename.split('.')[-1]
                text = remove_comments_from_text(text_type=extension, text=text)
                # insert in the same position the corresponding text
                file_placeholder_values.insert(index, text)
        
        file_placeholders_replacement(file_placeholders_dict=file_placeholders_dict)
        # similar to populate_known_with_custom() but for file placeholders
        expand_file_placeholders_inside_placeholders(placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict)

        for root, _, files in os.walk(templates_path):
            # We only process files inside tests and tests/resources folders
            if not files or (root != templates_path and root != os.path.join(templates_path, 'resources')):
                continue
            output_path = root.replace(templates_path, tests_path, 1)
            for file in files:
                # output_file_complete_path is still the input here, that will be processed and give us the output
                output_file_complete_path = os.path.join(output_path, file)
                read_file_and_create_test(input_filepath=output_file_complete_path,
                    output_path=output_path, output_filename=file,
                    placeholders_dict=placeholders_dict, file_placeholders_dict=file_placeholders_dict,
                    original_placeholders_dict=original_placeholders_dict,
                    mandatory_list=mandatory_list, text_elements_list=text_elements_list,
                    max_elements_limit=max_elements_limit, use_case_path=use_case_path
                )
        
        shutil.rmtree(os.path.join(tests_path, "prototypes"), ignore_errors=True) # rm prototypes from tests, only needed as templates
        
        # Call cloc for statistic on tests
        tests_stats = "\nStatistics for Generated Tests:\n" + call_cloc(path=tests_path)
        end = time.time()
        time_stat = f'\nTotal time to generate the tests: {end - start} seconds'
        stats = template_stats + tests_stats + time_stat
        print(stats)
        append_file(os.path.join(use_case_path, 'stats.txt'), stats)

def get_args():
    parser = ArgumentParser()
    parser.add_argument("-c", "--config", dest = "config", nargs = 1, required=True, help = "The configuration file.")
    return parser.parse_args()

if __name__ == "__main__":
    args = get_args()
    # print(args)
    config = read_config(args.config[0])
    if not config:
        print('Exiting...')
        exit(1)
    if type(config) is not list:
        if type(config) is dict:
            config = [config]
        else:
            print('Wrong config format. Exiting...')
            exit(1)
    generate_tests(config=config)
