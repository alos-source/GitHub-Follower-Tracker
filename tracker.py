import requests
import tkinter as tk
from tkinter import ttk
from tkinter import messagebox
import json

import os
import webbrowser

import datetime
# Stores previously fetched results: {'username': {'followers': set(), 'following': set(), 'not_following_back': set(), 'follower_timestamps': {user: timestamp}}}
previous_results = {}
DATA_FILE = "github_tracker_data.json"

def fetch_github_data(username, endpoint_type):
    """Fetches data from a GitHub API endpoint (followers or following).
    Returns a list of logins on success, None on failure."""
    # Paginierung: alle Seiten laden
    all_logins = []
    page = 1
    per_page = 100
    try:
        while True:
            url = f"https://api.github.com/users/{username}/{endpoint_type}?per_page={per_page}&page={page}"
            response = requests.get(url)
            if response.status_code in (403, 429):
                # Rate limit exceeded or too many requests
                messagebox.showwarning(
                    "Rate Limit",
                    "GitHub API rate limit reached or too many requests. Only locally/offline stored data will be shown."
                )
                return None
            response.raise_for_status()
            data = response.json()
            logins = [item["login"] for item in data]
            all_logins.extend(logins)
            if len(data) < per_page:
                break
            page += 1
        return all_logins
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


def get_last_update(username, category):
    return previous_results.get(username, {}).get('last_update', {}).get(category)

def update_result_display(username, category_key, current_data_list, full_title, empty_list_message):
    # Zähler aktualisieren
    followers_count = len(previous_results.get(username, {}).get("followers", []))
    following_count = len(previous_results.get(username, {}).get("following", []))
    followers_count_label.config(text=f"Followers: {followers_count}")
    following_count_label.config(text=f"Following: {following_count}")
    # Show last update timestamp for current category
    last_update = previous_results.get(username, {}).get('last_update', {}).get(category_key)
    if last_update:
        last_update_label.config(text=f"Last update: {last_update}")
    else:
        last_update_label.config(text="Last update: -")
    """Clears the result_text, displays the title, and lists users, highlighting new ones. For followers, also show and store first-seen timestamp."""
    # Clear previous content
    for item in result_tree.get_children():
        result_tree.delete(item)

    # Remove any existing title label before creating a new one
    if hasattr(update_result_display, "title_label") and update_result_display.title_label:
        update_result_display.title_label.destroy()
        update_result_display.title_label = None
    update_result_display.title_label = ttk.Label(result_frame, text=full_title, font=("Arial", 11, "bold"))
    update_result_display.title_label.pack(fill=tk.X, pady=(0, 5), before=result_tree)

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
        # For 'following', get the current followers list (for 'Follows back?' column)
        followers_set = None
        if category_key == "following":
            followers = get_user_followers(username)
            if followers is None:
                followers_set = None  # Mark as unknown
            else:
                followers_set = set(followers)

        for user_login in current_data_list:
            # Set timestamp if new (for followers and following)
            timestamp_str = ""
            if category_key in ("followers", "following"):
                if user_login not in timestamps:
                    timestamps[user_login] = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
                timestamp_str = timestamps[user_login]
            # Mark new users (not in old_data_set) with a tag
            tags = ("new_user_tag",) if user_login not in old_data_set else ()

            if category_key == "following":
                if followers_set is None:
                    follows_back = "?"
                else:
                    follows_back = "Yes" if user_login in followers_set else "No"
                result_tree.insert("", tk.END, values=(user_login, timestamp_str, follows_back), tags=tags)
            elif category_key == "followers":
                result_tree.insert("", tk.END, values=(user_login, timestamp_str, ""), tags=tags)
            else:
                result_tree.insert("", tk.END, values=(user_login, "", ""), tags=tags)
    else:
        # Show empty message as a single row
        if category_key == "following":
            result_tree.insert("", tk.END, values=(empty_list_message, "", ""))
        else:
            result_tree.insert("", tk.END, values=(empty_list_message, "", ""))

    # Tag config for new users (yellow background)
    result_tree.tag_configure("new_user_tag", background="yellow", foreground="black")

    # Update previous_results with the new successfully fetched data
    if username not in previous_results:
        previous_results[username] = {}
    previous_results[username][category_key] = set(current_data_list)
    save_previous_results() # Save after updating

def display_followers(force_refresh=False):
    username = entry.get()
    if not username:
        messagebox.showwarning("Warning", "Please enter your GitHub username.")
        return

    followers_list = None
    if force_refresh or not previous_results.get(username, {}).get("followers"):
        followers_list = get_user_followers(username)
        if followers_list is not None:
            if username not in previous_results:
                previous_results[username] = {}
            if 'last_update' not in previous_results[username]:
                previous_results[username]['last_update'] = {}
            previous_results[username]['last_update']['followers'] = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    if followers_list is None:
        followers_list = list(previous_results.get(username, {}).get("followers", []))
        if not followers_list:
            messagebox.showwarning("Warning", "No current or saved follower data available.")
    update_result_display(
        username,
        "followers",
        followers_list,
        f"Followers of {username}:",
        "(No followers found for this user.)"
    )

def display_following(force_refresh=False):
    username = entry.get()
    if not username:
        messagebox.showwarning("Warning", "Please enter your GitHub username.")
        return

    following_list = None
    if force_refresh or not previous_results.get(username, {}).get("following"):
        following_list = get_user_following(username)
        if following_list is not None:
            if username not in previous_results:
                previous_results[username] = {}
            if 'last_update' not in previous_results[username]:
                previous_results[username]['last_update'] = {}
            previous_results[username]['last_update']['following'] = datetime.datetime.now().isoformat(sep=' ', timespec='seconds')
    if following_list is None:
        following_list = list(previous_results.get(username, {}).get("following", []))
        if not following_list:
            messagebox.showwarning("Warning", "No current or saved following data available.")
    update_result_display(
        username,
        "following",
        following_list,
        f"Users {username} is following:",
        "(This user is not following anyone.)"
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
followers_button = ttk.Button(button_frame, text="Show Followers", command=lambda: display_followers(False))
followers_button.pack(side=tk.LEFT, padx=5)

following_button = ttk.Button(button_frame, text="Show Following", command=lambda: display_following(False))
following_button.pack(side=tk.LEFT, padx=5)

refresh_followers_button = ttk.Button(button_frame, text="Refresh Followers", command=lambda: display_followers(True))
refresh_followers_button.pack(side=tk.LEFT, padx=5)

refresh_following_button = ttk.Button(button_frame, text="Refresh Following", command=lambda: display_following(True))
refresh_following_button.pack(side=tk.LEFT, padx=5)


# Create a Treeview to display the result in columns
result_frame = ttk.Frame(window)
result_frame.pack(fill=tk.BOTH, expand=True)


# --- Treeview mit sortierbaren Spalten ---
def treeview_sort_column(treeview, col, reverse):
    # Get all items and their values for the given column
    data = [(treeview.set(k, col), k) for k in treeview.get_children("")]
    # Try to convert to datetime for timestamp, or to string otherwise
    if col == "timestamp":
        from datetime import datetime
        def parse_dt(val):
            try:
                return datetime.fromisoformat(val)
            except Exception:
                return val
        data.sort(key=lambda t: parse_dt(t[0]), reverse=reverse)
    else:
        data.sort(key=lambda t: t[0].lower() if isinstance(t[0], str) else t[0], reverse=reverse)
    # Rearrange items in sorted positions
    for index, (val, k) in enumerate(data):
        treeview.move(k, '', index)
    # Reverse sort next time
    treeview.heading(col, command=lambda: treeview_sort_column(treeview, col, not reverse))



# --- Treeview with sortable columns (all English) ---
result_tree = ttk.Treeview(result_frame, columns=("username", "timestamp", "follows_back"), show="headings", height=15)
result_tree.heading("username", text="Username", command=lambda: treeview_sort_column(result_tree, "username", False))
result_tree.heading("timestamp", text="First seen / following since", command=lambda: treeview_sort_column(result_tree, "timestamp", False))
result_tree.heading("follows_back", text="Follows back?", command=lambda: treeview_sort_column(result_tree, "follows_back", False))
result_tree.column("username", width=180)
result_tree.column("timestamp", width=180)
result_tree.column("follows_back", width=100, anchor="center")
result_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

# --- Double-click to open user profile in browser ---
def on_treeview_double_click(event):
    item_id = result_tree.identify_row(event.y)
    if not item_id:
        return
    values = result_tree.item(item_id, "values")
    if not values or not values[0] or values[0].startswith("("):
        return  # Ignore empty/placeholder rows
    username = values[0]
    url = f"https://github.com/{username}"
    webbrowser.open_new_tab(url)

result_tree.bind("<Double-1>", on_treeview_double_click)


# Add vertical scrollbar
scrollbar = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=result_tree.yview)
result_tree.configure(yscrollcommand=scrollbar.set)
scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

# Labels for follower and following count and last update
count_frame = ttk.Frame(window)
count_frame.pack(fill=tk.X, padx=10, pady=(5, 10))
followers_count_label = ttk.Label(count_frame, text="Followers: 0")
followers_count_label.pack(side=tk.LEFT, padx=10)
following_count_label = ttk.Label(count_frame, text="Following: 0")
following_count_label.pack(side=tk.LEFT, padx=10)
last_update_label = ttk.Label(count_frame, text="Last update: -")
last_update_label.pack(side=tk.LEFT, padx=10)

# Start the UI main loop
window.mainloop()
