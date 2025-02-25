import os

# Define the path to the pokemon.py file
file_path = 'Events/poketwo_anti_thief.py'  # Change to the correct path of your file if necessary

def replace_paths_in_file(file_path, old_path, new_path):
    """Reads a Python file, replaces old paths with new paths, and writes back the changes."""
    # Read the content of the file
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.read()
    
    # Replace old path with new path
    updated_content = file_content.replace(old_path, new_path)
    
    # Write the updated content back to the file
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)

    print(f"Replaced all occurrences of '{old_path}' with '{new_path}' in {file_path}")

if __name__ == "__main__":
    # Define the old path and new path
    old_path = "Data/pokemon/"
    new_path = "Data/commands/pokemon/"
    
    # Ensure the file exists before trying to replace
    if os.path.exists(file_path):
        replace_paths_in_file(file_path, old_path, new_path)
    else:
        print(f"File {file_path} does not exist.")
