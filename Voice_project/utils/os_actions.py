import os, shutil

def perform_os_action(action, target, destination=None):
    try:
        if action == "create_file":
            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(target)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            with open(target, 'w') as f:
                f.write("")  # Create empty file
            return f"Created file: {target}"

        elif action == "delete_file":
            if os.path.isfile(target):
                os.remove(target)
                return f"Deleted file: {target}"
            else:
                return f"File not found: {target}"

        elif action == "delete_folder":
            if os.path.isdir(target):
                shutil.rmtree(target)
                return f"Deleted folder: {target}"
            else:
                return f"Folder not found: {target}"

        elif action == "copy_file":
            if not destination:
                return "Copy operation requires destination"
            
            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(destination)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            if os.path.isfile(target):
                shutil.copy2(target, destination)  # copy2 preserves metadata
                return f"Copied '{target}' to '{destination}'"
            else:
                return f"Source file not found: {target}"

        elif action == "move_file":
            if not destination:
                return "Move operation requires destination"
            
            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(destination)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            if os.path.isfile(target):
                shutil.move(target, destination)
                return f"Moved '{target}' to '{destination}'"
            else:
                return f"Source file not found: {target}"

        elif action == "create_folder":
            os.makedirs(target, exist_ok=True)
            return f"Created folder: {target}"

        elif action == "write_code":
            # This action is handled differently - target should contain filepath::code
            filepath, code = target.split("::", 1)
            
            # Create parent directories if they don't exist
            parent_dir = os.path.dirname(filepath)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            
            with open(filepath, "w", encoding='utf-8') as f:
                f.write(code)
            return f"Code written to {filepath}"

        else:
            return f"Unsupported action: {action}"

    except PermissionError:
        return f"Permission denied for action: {action}"
    except FileNotFoundError:
        return f"File or directory not found for action: {action}"
    except Exception as e:
        return f"Error performing {action}: {str(e)}"

def get_contextual_os_info():
    """Get current directory context for better OS operations"""
    try:
        cwd = os.getcwd()
        
        # Get folders (limit to avoid overwhelming the context)
        folders = []
        files = []
        
        for item in os.scandir(cwd):
            if item.is_dir() and not item.name.startswith('.'):
                folders.append(item.name)
            elif item.is_file() and not item.name.startswith('.'):
                files.append(item.name)
        
        # Limit the number of items to keep context manageable
        folders = folders[:10]  # First 10 folders
        files = files[:15]      # First 15 files
        
        return cwd, folders, files
        
    except Exception as e:
        print(f"Error getting OS context: {e}")
        return os.getcwd(), [], []