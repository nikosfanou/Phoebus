#!/bin/bash

create_folder() {
    local folder=$1
    mkdir -p "$folder"
    if [ $? -eq 0 ]; then
        echo "Folder '$folder' created successfully."
    else
        echo "Failed to create folder '$folder'."
    fi
}

copy_files() {
    local from="$1/*"
    local to=$2
    cp -r $from $to
    if [ $? -eq 0 ]; then
        echo "Files '$from' copied successfully to '$to."
    else
        echo "Failed to copy files '$from' to '$to'."
    fi
}

main() {
    if [ -z "$1" ]; then
        echo "Usage: $0 <folder_name>"
        exit 1
    fi
    FOLDER_NAME="use-cases/$1"

    # Check if the folder already exists
    if [ -d "$FOLDER_NAME" ]; then
        echo "Error: Folder '$FOLDER_NAME' already exists. Aborting to prevent data loss."
        exit 1
    fi

    # tests folder which contains the expanded HTML test pages that the framework will visit during run of the use-case
    create_folder "$FOLDER_NAME/tests"
    # tests/resources folder which serves files from all URL paths (e.g., /resources/default.js)
    create_folder "$FOLDER_NAME/tests/resources"
    # user-scripts folder which contains the python selenium scripts or javascript files to be injected using driver.execute_script()
    create_folder "$FOLDER_NAME/user-scripts"
    # templates folder which contains the HTML template pages to be expanded to the main tests
    create_folder "$FOLDER_NAME/templates"
    # templates/resources folder which contains the templates for resources
    create_folder "$FOLDER_NAME/templates/resources"
    # templates/prototypes folder is splitted into 2 folders, raw and partial
    create_folder "$FOLDER_NAME/templates/prototypes"
    # raw folder contains templates that will be used as placeholders with their current form, without being processed
    create_folder "$FOLDER_NAME/templates/prototypes/raw"
    # partial folder contains templates that will be used as placeholders after being expanded themselves
    create_folder "$FOLDER_NAME/templates/prototypes/partial"
    # copy a python selenium template with instructions
    copy_files "default-files/user-scripts" "$FOLDER_NAME/user-scripts"
}

main $1