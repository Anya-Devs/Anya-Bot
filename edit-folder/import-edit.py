import os

# Function to organize the imports in a file
def organize_imports_in_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    local_imports = []
    pip_imports = []
    other_lines = []

    # Separate the imports based on the prefix
    for line in lines:
        line = line.strip()

        # Skip empty lines and comments
        if not line or line.startswith('#'):
            other_lines.append(line)
        elif line.startswith('import ') or line.startswith('from '):
            if 'import' in line:
                if 'pip' in line:  # Check for pip imports (or any specific indicator)
                    pip_imports.append(line)
                else:
                    local_imports.append(line)
            else:
                local_imports.append(line)
        else:
            other_lines.append(line)

    # Sort imports by length (shortest to longest)
    local_imports.sort(key=len)
    pip_imports.sort(key=len)

    # Reorganize the imports with spacing
    organized_content = '\n'.join(local_imports) + '\n\n' + '\n'.join(pip_imports) + '\n\n' + '\n'.join(other_lines)

    # Write the organized content back to the file
    with open(file_path, 'w') as file:
        file.write(organized_content)


# Function to organize imports in all Python files within a folder
def organize_imports_in_folder(folder_path):
    # Walk through the folder and process each Python file
    for root, _, files in os.walk(folder_path):
        for file_name in files:
            if file_name.endswith('.py'):
                file_path = os.path.join(root, file_name)
                organize_imports_in_file(file_path)
                print(f"Organized imports in: {file_path}")


# Set the folder path where the Python files are located
folder_path = 'Enter in the dir path you want to : '

# Call the function to organize imports in all Python files in the folder
organize_imports_in_folder(folder_path)
