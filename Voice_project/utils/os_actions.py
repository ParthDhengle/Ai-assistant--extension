import os, shutil

def perform_os_action(action, target, extra=None):
    try:
        if action == "create_file":
            with open(target, 'w'): pass
            return f"Created file: {target}"

        elif action == "delete_file":
            if os.path.isfile(target):
                os.remove(target)
                return f"Deleted file: {target}"
            elif os.path.isdir(target):
                shutil.rmtree(target)
                return f"Deleted folder: {target}"
            else:
                return "Target not found."

        elif action == "copy_file":
            shutil.copy(target, extra)
            return f"Copied from {target} to {extra}"

        elif action == "create_folder":
            os.makedirs(target, exist_ok=True)
            return f"Created folder: {target}"

        elif action == "write_code":
            filepath, code = target.split("::", 1)
            with open(filepath, "w") as f:
                f.write(code)
            return f"Code written to {filepath}"

        else:
            return "Unsupported action."

    except Exception as e:
        return f"Error: {str(e)}"

def get_contextual_os_info():
    cwd = os.getcwd()
    folders = [f.name for f in os.scandir(cwd) if f.is_dir()]
    files = [f.name for f in os.scandir(cwd) if f.is_file()]
    return cwd, folders, files
