import os

def remove_comments_from_file(file_path):
    if not os.path.exists(file_path):
        print(f"The file at {file_path} does not exist.")
        return

    with open(file_path, 'r') as file:
        lines = file.readlines()

    with open(file_path, 'w') as file:
        for line in lines:
            # Remove comments by finding '#' and replacing the comment part with spaces
            if '#' in line:
                code, comment = line.split('#', 1)
                file.write(code + ' ' * len(comment) + '\n')
            elif '""""' in line:
                code, comment = line.split('"""', 1)
                file.write(code + ' ' * len(comment) + '\n')
            else:
                file.write(line)

    print(f"Comments have been removed and replaced with spaces in {file_path}.")

if __name__ == "__main__":
    file_path = input("Enter the path to the Python file: ").strip()
    remove_comments_from_file(file_path)
