import os


file_path = 'Events/poketwo_anti_thief.py'  

def replace_paths_in_file(file_path, old_path, new_path):
    """Reads a Python file, replaces old paths with new paths, and writes back the changes."""
    
    with open(file_path, 'r', encoding='utf-8') as file:
        file_content = file.read()
    
    updated_content = file_content.replace(old_path, new_path)
    
    
    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(updated_content)

    print(f"Replaced all occurrences of '{old_path}' with '{new_path}' in {file_path}")

if __name__ == "__main__":
    
    old_path = "Data/pokemon/"
    new_path = "Data/commands/pokemon/"
    
    
    if os.path.exists(file_path):
        replace_paths_in_file(file_path, old_path, new_path)
    else:
        print(f"File {file_path} does not exist.")
