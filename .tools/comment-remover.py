import os
import re

def remove_comments_from_code(code):
    # Regular expression to match comments that are not inside strings
    def remove_comments(match):
        if match.group('quote'):
            return match.group(0)  # It's a string, keep it
        return ''  # It's a comment, remove it

    # Regex to handle both single-line and multi-line comments
    pattern = r'(?P<quote>["\']).*?\1|#.*?$'
    cleaned_code = re.sub(pattern, remove_comments, code, flags=re.DOTALL | re.MULTILINE)
    return cleaned_code

def process_files_in_folder(folder_path):
    for root, _, files in os.walk(folder_path):
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                with open(file_path, 'r', encoding='utf-8') as f:
                    code = f.read()
                
                cleaned_code = remove_comments_from_code(code)
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(cleaned_code)

folder_path = input("Enter in the dir path you want to uncomment: ")  # Specify the folder path here
process_files_in_folder(folder_path)
