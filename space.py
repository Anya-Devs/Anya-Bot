import os

def get_folder_size(path):
    """Recursively get folder size in bytes."""
    total_size = 0
    for dirpath, dirnames, filenames in os.walk(path):
        for f in filenames:
            try:
                fp = os.path.join(dirpath, f)
                total_size += os.path.getsize(fp)
            except (OSError, FileNotFoundError):
                pass
    return total_size

def human_readable_size(size, decimal_places=2):
    """Convert bytes to human-readable format."""
    for unit in ['B','KB','MB','GB','TB']:
        if size < 1024:
            return f"{size:.{decimal_places}f} {unit}"
        size /= 1024
    return f"{size:.{decimal_places}f} PB"

def list_large_folders(base_path=r"C:\Users\Owner", top_n=20):
    folder_sizes = []
    for item in os.listdir(base_path):
        item_path = os.path.join(base_path, item)
        if os.path.isdir(item_path):
            size = get_folder_size(item_path)
            folder_sizes.append((item_path, size))

    # Sort by size descending
    folder_sizes.sort(key=lambda x: x[1], reverse=True)

    print(f"Top {top_n} largest folders in '{base_path}':\n")
    for path, size in folder_sizes[:top_n]:
        print(f"{human_readable_size(size):>10} - {path}")

if __name__ == "__main__":
    list_large_folders()
