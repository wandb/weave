# Assumes that the base virtual environment exists, activate it.
. base/bin/activate

# Create the derived virtual environment.
python -m venv ./derived

# Make the derived virtual environment import base's packages too.



#!/bin/bash

# Function to process each file
process_file() {
    local file="$1"
    local name=$(basename "$filename" | awk -F. '{print $2}')
    local venv_root="./test_venvs/venvs/derived_$name"
    echo "$name"
    echo "Creating test env $name for: $file in $venv_root"
    python -m venv venv_root

    base_site_packages="$(python -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    derived_site_packages="$($venv_root -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
    echo "$base_site_packages" > "$derived_site_packages"/_base_packages.pth
}

# Check if directory is provided
if [ -z "$1" ]; then
    echo "Usage: $0 <directory>"
    exit 1
fi

directory="$1"

# Check if the directory exists
if [ ! -d "$directory" ]; then
    echo "Directory $directory does not exist."
    exit 1
fi

# Iterate over each file in the directory
for file in "$directory"/*; do
    if [ -f "$file" ]; then
        process_file "$file"
    fi
done

echo "All files processed."
