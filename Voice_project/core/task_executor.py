import os
import shutil
import subprocess
import webbrowser

# Dictionary of search platforms with URL templates
SEARCH_PLATFORMS = {
    "youtube": "https://www.youtube.com/results?search_query={query}",
    "google": "https://www.google.com/search?q={query}",
    "amazon": "https://www.amazon.com/s?k={query}",
    # Add more platforms here as needed, e.g., "ebay": "https://www.ebay.com/sch/i.html?_nkw={query}"
}
def perform_os_action(parsed):
    action = parsed.get("action")
    try:
        if action == "create_file":
            target = parsed.get("target")
            if not target:
                return "Target not provided"
            parent_dir = os.path.dirname(target)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            with open(target, 'w') as f:
                f.write("")
            return f"Created file: {target}"

        elif action == "delete_file":
            target = parsed.get("target")
            if os.path.isfile(target):
                os.remove(target)
                return f"Deleted file: {target}"
            else:
                return f"File not found: {target}"

        elif action == "delete_folder":
            target = parsed.get("target")
            if os.path.isdir(target):
                shutil.rmtree(target)
                return f"Deleted folder: {target}"
            else:
                return f"Folder not found: {target}"

        elif action == "copy_file":
            source = parsed.get("source")
            destination = parsed.get("destination")
            if not source or not destination:
                return "Copy operation requires source and destination"
            parent_dir = os.path.dirname(destination)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            if os.path.isfile(source):
                shutil.copy2(source, destination)
                return f"Copied '{source}' to '{destination}'"
            else:
                return f"Source file not found: {source}"

        elif action == "move_file":
            source = parsed.get("source")
            destination = parsed.get("destination")
            if not source or not destination:
                return "Move operation requires source and destination"
            parent_dir = os.path.dirname(destination)
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)
            if os.path.isfile(source):
                shutil.move(source, destination)
                return f"Moved '{source}' to '{destination}'"
            else:
                return f"Source file not found: {source}"

        elif action == "create_folder":
            target = parsed.get("target")
            os.makedirs(target, exist_ok=True)
            return f"Created folder: {target}"

        elif action == "open_application":
            app_name = parsed.get("app_name")
            if not app_name:
                return "Application name not provided"
            try:
                subprocess.Popen(app_name, shell=True)
                return f"Opening {app_name}"
            except FileNotFoundError:
                return f"Application not found: {app_name}"
            except Exception as e:
                return f"Error opening {app_name}: {str(e)}"

        elif action == "open_website":
            url = parsed.get("url")
            if not url:
                return "URL not provided"
            webbrowser.open(url)
            return f"Opening {url}"

        elif action == "open_file":
            file_path = parsed.get("file_path")
            if not file_path:
                return "File path not provided"
            if not os.path.exists(file_path):
                return f"File not found: {file_path}"
            os.startfile(file_path)
            return f"Opening {file_path}"

        elif action == "system_command":
            command = parsed.get("command")
            if command == "shutdown":
                os.system("shutdown /s /t 0")
                return "Shutting down the computer"
            elif command == "restart":
                os.system("shutdown /r /t 0")
                return "Restarting the computer"
            else:
                return f"Unsupported system command: {command}"

        elif action == "play_media":
            platform = parsed.get("platform")
            query = parsed.get("query")
            if platform and query:
                if platform.lower() == "youtube":
                    url = f"https://www.youtube.com/results?search_query={query}"
                    webbrowser.open(url)
                    return f"Opening YouTube search for {query}"
                else:
                    return f"Unsupported platform: {platform}"
            else:
                return "Insufficient parameters for play_media"

        elif action == "search_platform":
            platform = parsed.get("platform")
            query = parsed.get("query")
            if not platform or not query:
                return "Platform and query are required for search_platform"
            platform = platform.lower()
            if platform in SEARCH_PLATFORMS:
                url = SEARCH_PLATFORMS[platform].format(query=query)
                webbrowser.open(url)
                return f"Searching {platform} for {query}"
            else:
                return f"Unsupported platform: {platform}"
            
        elif action == "play_local_media":
            file_path = parsed.get("file_path")
            if not file_path:
                return "File path not provided"
            if not os.path.exists(file_path):
                return f"File not found: {file_path}"
            os.startfile(file_path)
            return f"Playing {file_path}"

        else:
            return f"Unsupported action: {action}"

    except PermissionError:
        return f"Permission denied for action: {action}"
    except FileNotFoundError:
        return f"File or directory not found for action: {action}"
    except Exception as e:
        return f"Error performing {action}: {str(e)}"

def get_contextual_os_info():
    try:
        cwd = os.getcwd()
        folders = [item.name for item in os.scandir(cwd) if item.is_dir() and not item.name.startswith('.')][:10]
        files = [item.name for item in os.scandir(cwd) if item.is_file() and not item.name.startswith('.')][:15]
        return cwd, folders, files
    except Exception as e:
        print(f"Error getting OS context: {e}")
        return os.getcwd(), [], []

def execute_os_action(parsed):
    return perform_os_action(parsed)