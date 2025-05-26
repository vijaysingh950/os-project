from flask import Flask, send_from_directory, request, jsonify
import json
import os
from threading import Lock, RLock
from collections import defaultdict

app = Flask(__name__, static_folder='static', template_folder='templates')

# Load users with roles from JSON
with open('users.json', 'r') as f:
    USERS = json.load(f)

# Ensure files directory exists
FILES_DIR = 'files'
if not os.path.exists(FILES_DIR):
    os.makedirs(FILES_DIR)

# File locking mechanism
file_locks = {}  # Dictionary to store file locks
readers_count = defaultdict(int)  # Count of readers per file
lock_manager = RLock()  # Global lock for managing reader/writer access

def acquire_read_lock(filename, username):
    with lock_manager:
        if filename in file_locks and file_locks[filename]['type'] == 'write':
            return False, f"File is being edited by {file_locks[filename]['user']}"
        readers_count[filename] += 1
        return True, None

def release_read_lock(filename):
    with lock_manager:
        if readers_count[filename] > 0:
            readers_count[filename] -= 1
        if readers_count[filename] == 0:
            readers_count.pop(filename, None)

def acquire_write_lock(filename, username):
    with lock_manager:
        if filename in file_locks:
            return False, f"File is locked by {file_locks[filename]['user']}"
        if readers_count.get(filename, 0) > 0:
            return False, f"File is currently being read by {readers_count[filename]} users"
        file_locks[filename] = {'type': 'write', 'user': username}
        return True, None

def release_write_lock(filename, username):
    with lock_manager:
        if filename in file_locks and file_locks[filename]['user'] == username:
            del file_locks[filename]
            return True
        return False

@app.route('/')
def index():
    return send_from_directory('templates', 'index.html')

@app.route('/auth', methods=['POST'])
def auth():
    data = request.json
    username = data.get('username')
    password = data.get('password')
    
    if username in USERS and USERS[username]["password"] == password:
        return jsonify({
            "status": "success",
            "role": USERS[username]["role"]
        })
    return jsonify({
        "status": "error",
        "message": "Invalid credentials"
    })

@app.route('/command', methods=['POST'])
def command():
    data = request.json
    command = data.get('command', '')
    username = data.get('username', '')
    role = data.get('role', '')
    
    if not command:
        return jsonify({"status": "error", "message": "No command provided"})
        
    parts = command.split("::")
    action = parts[0]
    
    try:
        if action == "LOCK" and role == "admin":
            if len(parts) < 2:
                return jsonify({"status": "error", "message": "Filename required"})
            filename = parts[1]
            
            success, message = acquire_write_lock(filename, username)
            if success:
                return jsonify({"status": "success", "message": f"File {filename} locked"})
            return jsonify({"status": "error", "message": message})
            
        elif action == "UNLOCK" and role == "admin":
            if len(parts) < 2:
                return jsonify({"status": "error", "message": "Filename required"})
            filename = parts[1]
            
            if release_write_lock(filename, username):
                return jsonify({"status": "success", "message": f"File {filename} unlocked"})
            return jsonify({"status": "error", "message": "You don't have the lock for this file"})
            
        elif action == "LIST":
            files = [f for f in os.listdir(FILES_DIR) 
                    if os.path.isfile(os.path.join(FILES_DIR, f))]
            # Include lock information in response
            lock_info = {
                'files': files,
                'locked_files': {
                    filename: {
                        'type': info['type'],
                        'user': info['user']
                    } for filename, info in file_locks.items()
                },
                'readers': {
                    filename: count for filename, count in readers_count.items() if count > 0
                }
            }
            return jsonify({"status": "success", **lock_info})
            
        elif action == "READ":
            if len(parts) < 2:
                return jsonify({"status": "error", "message": "Filename required"})
            filename = parts[1]
            file_path = os.path.join(FILES_DIR, filename)
            
            if not os.path.exists(file_path):
                return jsonify({"status": "error", "message": "File not found"})
            
            # Check if file is locked
            if filename in file_locks:
                return jsonify({"status": "error", "message": f"File is locked by {file_locks[filename]['user']}"})
                
            # Try to acquire read lock
            success, message = acquire_read_lock(filename, username)
            if not success:
                return jsonify({"status": "error", "message": message})
                
            try:
                with open(file_path, 'r') as f:
                    content = f.read()
                return jsonify({"status": "success", "content": content})
            finally:
                release_read_lock(filename)
            
        elif action == "CREATE" and role == "admin":
            if len(parts) < 3:
                return jsonify({"status": "error", "message": "Filename and content required"})
            filename = parts[1]
            content = parts[2]
            file_path = os.path.join(FILES_DIR, filename)
            
            if os.path.exists(file_path):
                return jsonify({"status": "error", "message": "File already exists"})
            
            # Check if file is locked
            if filename in file_locks:
                return jsonify({"status": "error", "message": f"File is locked by {file_locks[filename]['user']}"})
                
            # Try to acquire write lock
            success, message = acquire_write_lock(filename, username)
            if not success:
                return jsonify({"status": "error", "message": message})
                
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                return jsonify({"status": "success", "message": f"File {filename} created"})
            finally:
                release_write_lock(filename, username)
            
        elif action == "EDIT" and role == "admin":
            if len(parts) < 3:
                return jsonify({"status": "error", "message": "Filename and content required"})
            filename = parts[1]
            content = parts[2]
            file_path = os.path.join(FILES_DIR, filename)
            
            if not os.path.exists(file_path):
                return jsonify({"status": "error", "message": "File not found"})
            
            # Check if file is locked by someone else
            if filename in file_locks and file_locks[filename]['user'] != username:
                return jsonify({"status": "error", "message": f"File is locked by {file_locks[filename]['user']}"})
            
            # If file is not locked by current user, try to acquire write lock
            if filename not in file_locks:
                success, message = acquire_write_lock(filename, username)
                if not success:
                    return jsonify({"status": "error", "message": message})
                
            try:
                with open(file_path, 'w') as f:
                    f.write(content)
                return jsonify({"status": "success", "message": f"File {filename} updated"})
            finally:
                if filename not in file_locks:
                    release_write_lock(filename, username)
            
        elif action == "DELETE" and role == "admin":
            if len(parts) < 2:
                return jsonify({"status": "error", "message": "Filename required"})
            filename = parts[1]
            file_path = os.path.join(FILES_DIR, filename)
            
            if not os.path.exists(file_path):
                return jsonify({"status": "error", "message": "File not found"})
            
            # Check if file is locked
            if filename in file_locks:
                return jsonify({"status": "error", "message": f"File is locked by {file_locks[filename]['user']}"})
                
            # Try to acquire write lock
            success, message = acquire_write_lock(filename, username)
            if not success:
                return jsonify({"status": "error", "message": message})
                
            try:
                os.remove(file_path)
                return jsonify({"status": "success", "message": f"File {filename} deleted"})
            finally:
                release_write_lock(filename, username)
            
        elif action == "MAKE_REQUEST" and role == "user":
            if len(parts) < 4:
                return jsonify({"status": "error", "message": "Invalid request format"})
            request_type = parts[1]
            filename = parts[2]
            content = parts[3] if len(parts) > 3 else ""
            
            # Store request in a JSON file
            requests_file = 'requests.json'
            requests_data = []
            if os.path.exists(requests_file):
                with open(requests_file, 'r') as f:
                    requests_data = json.load(f)
            
            new_request = {
                "id": len(requests_data) + 1,
                "username": username,
                "type": request_type,
                "filename": filename,
                "content": content,
                "status": "pending"
            }
            requests_data.append(new_request)
            
            with open(requests_file, 'w') as f:
                json.dump(requests_data, f, indent=2)
            
            return jsonify({"status": "success", "message": f"Request #{new_request['id']} submitted"})
            
        elif action == "LIST_REQUESTS" and role == "admin":
            if not os.path.exists('requests.json'):
                return jsonify({"status": "success", "requests": []})
            with open('requests.json', 'r') as f:
                requests_data = json.load(f)
            return jsonify({"status": "success", "requests": requests_data})
            
        elif action == "HANDLE_REQUEST" and role == "admin":
            if len(parts) < 3:
                return jsonify({"status": "error", "message": "Request ID and decision required"})
            request_id = int(parts[1])
            decision = parts[2]
            
            if not os.path.exists('requests.json'):
                return jsonify({"status": "error", "message": "No requests found"})
                
            with open('requests.json', 'r') as f:
                requests_data = json.load(f)
            
            for req in requests_data:
                if req['id'] == request_id:
                    req['status'] = 'approved' if decision == 'approve' else 'rejected'
                    if decision == 'approve':
                        file_path = os.path.join(FILES_DIR, req['filename'])
                        if req['type'] == 'CREATE':
                            with open(file_path, 'w') as f:
                                f.write(req['content'])
                        elif req['type'] == 'EDIT':
                            with open(file_path, 'w') as f:
                                f.write(req['content'])
                        elif req['type'] == 'DELETE':
                            if os.path.exists(file_path):
                                os.remove(file_path)
                    break
            
            with open('requests.json', 'w') as f:
                json.dump(requests_data, f, indent=2)
            
            return jsonify({
                "status": "success", 
                "message": f"Request #{request_id} {decision}d"
            })
            
        return jsonify({"status": "error", "message": "Invalid command or insufficient permissions"})
        
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

if __name__ == '__main__':
    # Create requests.json if it doesn't exist
    if not os.path.exists('requests.json'):
        with open('requests.json', 'w') as f:
            json.dump([], f)
    app.run(host='0.0.0.0', port=8000, debug=True)