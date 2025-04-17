import os
import re

def remove_comments_from_code(code, file_path):
    removed_comments = []

    def replacer(match):
        string_literal = match.group('string')
        comment = match.group('comment')
        if string_literal:
            return string_literal
        elif comment:
            removed_comments.append((file_path, comment.strip()))
            return ''
        return match.group(0)

    pattern = r'''
        (?P<string>
            "(?:\\.|[^"\\])*"
            |
            '(?:\\.|[^'\\])*'
        )
        |
        (?P<comment>\#.*?$)
    '''

    cleaned_code = re.sub(pattern, replacer, code, flags=re.MULTILINE | re.VERBOSE)
    return cleaned_code, removed_comments


def remove_comments_in_folder(folder_path):
    py_files = []

    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                py_files.append(os.path.join(root, file))

    if not py_files:
        print("No Python files found.")
        return

    print(f"Found {len(py_files)} Python files:")
    for file in py_files:
        print(f" - {file}")

    confirm = input("\nThis will permanently remove comments from these files. Proceed? (yes/no): ").strip().lower()
    if confirm != "yes":
        print("Aborted.")
        return

    all_removed = []
    for file_path in py_files:
        with open(file_path, 'r', encoding='utf-8') as f:
            code = f.read()

        cleaned_code, removed = remove_comments_from_code(code, file_path)
        all_removed.extend(removed)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_code)

    print(f"\nComments removed from {len(py_files)} files.")
    if all_removed:
        print("\nRemoved comments:")
        for file, comment in all_removed:
            print(f"{file}: {comment}")


def organize_imports_in_file(file_path):
    with open(file_path, 'r') as file:
        lines = file.readlines()

    local_imports = []
    pip_imports = []
    other_lines = []

    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            other_lines.append(line)
        elif stripped.startswith('import ') or stripped.startswith('from '):
            if 'pip' in stripped:
                pip_imports.append(line)
            else:
                local_imports.append(line)
        else:
            other_lines.append(line)

    local_imports.sort(key=len)
    pip_imports.sort(key=len)

    organized_content = '\n'.join(local_imports) + '\n\n' + '\n'.join(pip_imports) + '\n\n' + ''.join(other_lines)
    with open(file_path, 'w') as file:
        file.write(organized_content)


def organize_imports_in_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                organize_imports_in_file(file_path)
                print(f"Organized imports in: {file_path}")


def replace_paths_in_file(file_path, old_path, new_path):
    with open(file_path, 'r', encoding='utf-8') as file:
        content = file.read()

    updated = content.replace(old_path, new_path)

    with open(file_path, 'w', encoding='utf-8') as file:
        file.write(updated)

    print(f"Replaced all occurrences of '{old_path}' with '{new_path}' in {file_path}")


def path_replacement_prompt():
    file_path = input("Enter the file path to update: ").strip()
    old_path = input("Old path to replace: ").strip()
    new_path = input("New path to insert: ").strip()

    if os.path.exists(file_path):
        replace_paths_in_file(file_path, old_path, new_path)
    else:
        print(f"File {file_path} does not exist.")


def main():
    print("\n--- Python Code File Tool ---")
    print("Select a function to run:\n")
    print("1. Remove comments from Python files")
    print("2. Organize imports in Python files")
    print("3. Replace file paths in a single file")

    try:
        choice = int(input("\nEnter choice (1-3): ").strip())
    except ValueError:
        print("Invalid input.")
        return

    if choice in (1, 2):
        folder_path = input("Enter directory path: ").strip()
        if not os.path.isdir(folder_path):
            print("Invalid directory.")
            return
        if choice == 1:
            remove_comments_in_folder(folder_path)
        else:
            organize_imports_in_folder(folder_path)
    elif choice == 3:
        path_replacement_prompt()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    main()
