import asyncio
import websockets
import json
import os
from datetime import datetime
from threading import Lock

HOST = 'localhost'
PORT = 5002

file_lock = Lock()
admin_file_locks = {}  # Track which admin has locked which file
pending_requests = []  # Store user requests
requests_lock = Lock()

# Load users with roles from JSON
with open('users.json', 'r') as f:
    USERS = json.load(f)

class FileRequest:
    def __init__(self, username, action, filename, content=None):
        self.id = len(pending_requests) + 1
        self.username = username
        self.action = action
        self.filename = filename
        self.content = content
        self.status = "pending"
        self.timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_dict(self):
        return {
            "id": self.id,
            "username": self.username,
            "action": self.action,
            "filename": self.filename,
            "content": self.content,
            "status": self.status,
            "timestamp": self.timestamp
        }

def get_file_list():
    """Get list of files excluding system files"""
    return [f for f in os.listdir('.')
            if not f.startswith('.') and
            f not in ['backend.py', 'users.json', '__pycache__', 'web_server.py', 'README.md', 'static', 'templates']]

async def handle_client(websocket):
    current_user = None
    current_role = None
    
    try:
        # Handle authentication
        auth_data = await websocket.recv()
        username, password = auth_data.strip().split("::")

        if username in USERS and USERS[username]["password"] == password:
            current_user = username
            current_role = USERS[username]["role"]
            await websocket.send(f"Authentication successful::{current_role}")
        else:
            await websocket.send("Authentication failed")
            return

        # Handle commands
        async for message in websocket:
            parts = message.split("::")
            command = parts[0]

            if command == "LOGOUT":
                if current_user in admin_file_locks.values():
                    locked_files = [f for f, u in admin_file_locks.items() if u == current_user]
                    for f in locked_files:
                        del admin_file_locks[f]
                await websocket.send("Logged out successfully")
                break

            elif command == "LIST":
                files = get_file_list()
                response = {
                    "files": files,
                    "locked_files": list(admin_file_locks.keys())
                }
                await websocket.send(json.dumps(response))

            elif command == "READ":
                if len(parts) == 2:
                    filename = parts[1]
                    if os.path.exists(filename):
                        try:
                            with open(filename, 'r') as f:
                                content = f.read()
                            await websocket.send(content)
                        except Exception as e:
                            await websocket.send(f"Error reading file: {str(e)}")
                    else:
                        await websocket.send("File not found")

            elif command == "CREATE" and current_role == "admin":
                if len(parts) >= 3:
                    filename = parts[1]
                    content = "::".join(parts[2:])
                    if os.path.exists(filename):
                        await websocket.send(f"Error: File '{filename}' already exists")
                        continue
                    if not filename or filename.startswith('.') or '/' in filename or '\\' in filename:
                        await websocket.send("Error: Invalid filename")
                        continue
                    with file_lock:
                        with open(filename, 'w') as f:
                            f.write(content)
                    await websocket.send(f"File '{filename}' created successfully")
                    files = get_file_list()
                    response = {
                        "files": files,
                        "locked_files": list(admin_file_locks.keys())
                    }
                    await websocket.send(json.dumps(response))
                else:
                    await websocket.send("Error: Invalid CREATE command format")

            elif command == "MAKE_REQUEST" and current_role == "user":
                if len(parts) >= 4:
                    action = parts[1]
                    filename = parts[2]
                    content = "::".join(parts[3:]) if len(parts) > 3 else None
                    request = FileRequest(current_user, action, filename, content)
                    with requests_lock:
                        pending_requests.append(request)
                    await websocket.send(f"Request #{request.id} submitted successfully")

            elif command == "LIST_REQUESTS" and current_role == "admin":
                with requests_lock:
                    requests_data = [req.to_dict() for req in pending_requests]
                await websocket.send(json.dumps({"requests": requests_data}))

            elif command == "HANDLE_REQUEST" and current_role == "admin":
                if len(parts) == 3:
                    request_id = int(parts[1])
                    approve = parts[2].lower() == "approve"
                    with requests_lock:
                        for request in pending_requests:
                            if request.id == request_id:
                                if approve:
                                    try:
                                        if request.action == "CREATE":
                                            with file_lock:
                                                with open(request.filename, 'w') as f:
                                                    f.write(request.content)
                                        request.status = "approved"
                                        files = get_file_list()
                                        response = {
                                            "files": files,
                                            "locked_files": list(admin_file_locks.keys())
                                        }
                                        await websocket.send(json.dumps(response))
                                    except Exception as e:
                                        await websocket.send(f"Error handling request: {str(e)}")
                                        continue
                                else:
                                    request.status = "rejected"
                                await websocket.send(f"Request #{request_id} {'approved' if approve else 'rejected'}")
                                break

            elif command == "LOCK" and current_role == "admin":
                if len(parts) == 2:
                    filename = parts[1]
                    if filename not in admin_file_locks:
                        admin_file_locks[filename] = current_user
                        await websocket.send(f"File '{filename}' locked for editing")
                    else:
                        await websocket.send(f"File is already locked by {admin_file_locks[filename]}")

            elif command == "UNLOCK" and current_role == "admin":
                if len(parts) == 2:
                    filename = parts[1]
                    if filename in admin_file_locks and admin_file_locks[filename] == current_user:
                        del admin_file_locks[filename]
                        await websocket.send(f"File '{filename}' unlocked")
                    else:
                        await websocket.send("You don't have the lock for this file")

            elif command == "DELETE" and current_role == "admin":
                if len(parts) == 2:
                    filename = parts[1]
                    if filename in admin_file_locks and admin_file_locks[filename] != current_user:
                        await websocket.send(f"File is locked by {admin_file_locks[filename]}")
                        continue
                    try:
                        with file_lock:
                            if os.path.exists(filename):
                                os.remove(filename)
                                if filename in admin_file_locks:
                                    del admin_file_locks[filename]
                                await websocket.send(f"File '{filename}' deleted")
                                files = get_file_list()
                                response = {
                                    "files": files,
                                    "locked_files": list(admin_file_locks.keys())
                                }
                                await websocket.send(json.dumps(response))
                            else:
                                await websocket.send("File not found")
                    except Exception as e:
                        await websocket.send(f"Error deleting file: {str(e)}")

            elif command == "EDIT" and current_role == "admin":
                if len(parts) >= 3:
                    filename = parts[1]
                    content = "::".join(parts[2:])
                    if filename in admin_file_locks and admin_file_locks[filename] != current_user:
                        await websocket.send(f"File is locked by {admin_file_locks[filename]}")
                        continue
                    try:
                        with file_lock:
                            with open(filename, 'w') as f:
                                f.write(content)
                        await websocket.send(f"File '{filename}' edited")
                    except Exception as e:
                        await websocket.send(f"Error editing file: {str(e)}")
                else:
                    await websocket.send("Invalid EDIT command format")
            else:
                await websocket.send("Unknown command or insufficient permissions")

    except Exception as e:
        print(f"[ERROR] {e}")
    finally:
        if current_user in admin_file_locks.values():
            locked_files = [f for f, u in admin_file_locks.items() if u == current_user]
            for f in locked_files:
                del admin_file_locks[f]

async def start_server():
    async with websockets.serve(handle_client, HOST, PORT):
        print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")
        await asyncio.Future()

if __name__ == "__main__":
    asyncio.run(start_server())