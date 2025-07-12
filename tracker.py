import requests
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json
import os

import datetime
# Stores previously fetched results: {'username': {'followers': set(), 'following': set(), 'not_following_back': set(), 'follower_timestamps': {user: timestamp}}}
previous_results = {}
DATA_FILE = "github_tracker_data.json"

def fetch_github_data(username, endpoint_type):
    """Fetches data from a GitHub API endpoint (followers or following).
    Returns a list of logins on success, None on failure."""
    url = f"https://api.github.com/users/{username}/{endpoint_type}"
    try:
        response = requests.get(url)
        response.raise_for_status()  # Raises an HTTPError for bad responses (4XX or 5XX)
        return [item["login"] for item in response.json()]
    except requests.exceptions.RequestException as e:
        messagebox.showerror("Error", f"Failed to retrieve {endpoint_type} for {username}.\n{e}")
        return None

def get_user_followers(username):
    return fetch_github_data(username, "followers")

def get_user_following(username):
    return fetch_github_data(username, "following")

def load_previous_results():
    global previous_results
    if os.path.exists(DATA_FILE):
        try:
            with open(DATA_FILE, 'r') as f:
                loaded_data = json.load(f)

                # Load last username if available
                metadata = loaded_data.get("_metadata", {})
                last_username = metadata.get("last_username")
                if last_username and entry: # Check if entry widget exists
                    entry.delete(0, tk.END)
                    entry.insert(0, last_username)

                # Load user tracking data and convert lists back to sets/dicts
                user_data_loaded = loaded_data.get("users", {})
                for username, categories in user_data_loaded.items():
                    previous_results[username] = {}
                    for category, user_list in categories.items():
                        if category in ("follower_timestamps", "following_timestamps"):
                            previous_results[username][category] = dict(user_list)
                        else:
                            previous_results[username][category] = set(user_list)
        except (json.JSONDecodeError, IOError) as e:
            messagebox.showerror("Load Error", f"Could not load previous data: {e}")
            previous_results = {} # Reset to empty if file is corrupt
            if entry:
                entry.delete(0, tk.END) # Clear entry field on load error


def save_previous_results():
    users_data_to_save = {}
    for username, categories in previous_results.items():
        users_data_to_save[username] = {}
        for category, user_set in categories.items():
            if category in ("follower_timestamps", "following_timestamps"):
                users_data_to_save[username][category] = dict(user_set)
            else:
                users_data_to_save[username][category] = list(user_set)

    data_to_save = {
        "_metadata": {"last_username": entry.get() if entry else ""}, # Get current username from entry
        "users": users_data_to_save
    }
    try:
        with open(DATA_FILE, 'w') as f:
            json.dump(data_to_save, f, indent=4)
    except IOError as e:
        messagebox.showerror("Save Error", f"Could not save data: {e}")


def update_result_display(username, category_key, current_data_list, full_title, empty_list_message):
    """Clears the result_text, displays the title, and lists users, highlighting new ones. For followers, also show and store first-seen timestamp."""
    # Clear previous content
    for item in result_tree.get_children():
        result_tree.delete(item)

    # Show title as a label above the treeview
    if hasattr(update_result_display, "title_label") and update_result_display.title_label:
        update_result_display.title_label.config(text=full_title)
    else:
        update_result_display.title_label = ttk.Label(result_frame, text=full_title, font=("Arial", 11, "bold"))
        update_result_display.title_label.pack(side=tk.TOP, anchor="w", pady=(0, 5))

    old_data_set = previous_results.get(username, {}).get(category_key, set())
    # Prepare timestamps dict for followers and following
    if username not in previous_results:
        previous_results[username] = {}
    if category_key == "followers":
        if "follower_timestamps" not in previous_results[username]:
            previous_results[username]["follower_timestamps"] = {}
        timestamps = previous_results[username]["follower_timestamps"]
    elif category_key == "following":
        if "following_timestamps" not in previous_results[username]:
            previous_results[username]["following_timestamps"] = {}
        timestamps = previous_results[username]["following_timestamps"]
    else:
        timestamps = None

    if current_data_list:
        for user_login in current_data_list:
            # Zeitstempel setzen, falls neu (für followers und following)
            timestamp_str = ""
            if category_key in ("followers", "following"):
                if user_login not in timestamps:
                    timestamps[user_login] = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
                timestamp_str = timestamps[user_login]
            # Mark new users (not in old_data_set) with a tag
            tags = ("new_user_tag",) if user_login not in old_data_set else ()
            if category_key in ("followers", "following"):
                result_tree.insert("", tk.END, values=(user_login, timestamp_str), tags=tags)
            else:
                result_tree.insert("", tk.END, values=(user_login, ""), tags=tags)
    else:
        # Show empty message as a single row
        result_tree.insert("", tk.END, values=(empty_list_message, ""))

    # Tag config for new users (yellow background)
    result_tree.tag_configure("new_user_tag", background="yellow", foreground="black")

    # Update previous_results with the new successfully fetched data
    if username not in previous_results:
        previous_results[username] = {}
    previous_results[username][category_key] = set(current_data_list)
    save_previous_results() # Save after updating

def display_followers():
    username = entry.get()
    if not username:
        messagebox.showwarning("Warning", "Please enter your GitHub username.")
        return

    followers_list = get_user_followers(username)
    if followers_list is None: # API call failed, messagebox already shown by fetch_github_data
        return

    update_result_display(
        username,
        "followers",
        followers_list,
        f"Followers of {username}:",
        "(No followers found for this user.)"
    )

def display_following():
    username = entry.get()
    if not username:
        messagebox.showwarning("Warning", "Please enter your GitHub username.")
        return

    following_list = get_user_following(username)
    if following_list is None: # API call failed
        return

    update_result_display(
        username,
        "following",
        following_list,
        f"Users {username} is following:",
        "(This user is not following anyone.)"
    )

def find_users_not_following_back():
    username = entry.get()
    if not username:
        messagebox.showwarning("Warning", "Please enter your GitHub username.")
        return

    followers_list = get_user_followers(username)
    if followers_list is None:
        return # Error already shown, cannot proceed

    following_list = get_user_following(username)
    if following_list is None:
        return # Error already shown, cannot proceed

    not_following_back_list = [user for user in following_list if user not in followers_list]

    update_result_display(
        username,
        "not_following_back",
        not_following_back_list,
        f"Users not following {username} back:",
        "(No users found who are not following you back.)"
    )

# Create the main window
window = tk.Tk()
window.title("GitHub Follower Analyzer")
window.geometry("500x450") # Increased window size

# Create a label and an entry field for the username
label = ttk.Label(window, text="Enter your GitHub username:")
label.pack(pady=10)

entry = ttk.Entry(window, width=30)
entry.pack()

# Load previous results at startup, after entry widget is created
load_previous_results()

# Create a frame for the buttons
button_frame = ttk.Frame(window)
button_frame.pack(pady=10)

# Create buttons for different actions
followers_button = ttk.Button(button_frame, text="Show Followers", command=display_followers)
followers_button.pack(side=tk.LEFT, padx=5)

following_button = ttk.Button(button_frame, text="Show Following", command=display_following)
following_button.pack(side=tk.LEFT, padx=5)

not_following_back_button = ttk.Button(button_frame, text="Not Following Back", command=find_users_not_following_back)
not_following_back_button.pack(side=tk.LEFT, padx=5)

# Create a Treeview to display the result in columns
result_frame = ttk.Frame(window)
result_frame.pack(fill=tk.BOTH, expand=True)

result_tree = ttk.Treeview(result_frame, columns=("username", "timestamp"), show="headings", height=15)
result_tree.heading("username", text="Username")
result_tree.heading("timestamp", text="Erstmals entdeckt/folgt seit")
result_tree.column("username", width=200)
result_tree.column("timestamp", width=200)
result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# Add vertical scrollbar
scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_tree.yview)
result_tree.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Start the UI main loop
window.mainloop()
