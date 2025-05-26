let currentRole = null;
let currentUsername = null;

// Function to format lock information
function formatLockInfo(files, lockedFiles, readers) {
    let output = [];
    
    output.push('Files:');
    files.forEach(file => {
        let status = [];
        if (lockedFiles[file]) {
            status.push(`[Locked for ${lockedFiles[file].type} by ${lockedFiles[file].user}]`);
        }
        if (readers[file]) {
            status.push(`[Being read by ${readers[file]} users]`);
        }
        output.push(`- ${file} ${status.length ? status.join(' ') : ''}`);
    });
    
    return output.join('\n');
}

// Function to toggle input fields based on selected action
function toggleInputFields(action) {
    const filenameInput = document.getElementById('filename');
    const contentInput = document.getElementById('content');
    const lockButtons = document.getElementById('lockButtons');
    
    filenameInput.style.display = (action === 'LIST' || action === 'LIST_REQUESTS') ? 'none' : 'block';
    contentInput.style.display = (action === 'CREATE' || action === 'EDIT') ? 'block' : 'none';
    lockButtons.style.display = (action === 'EDIT' && currentRole === 'admin') ? 'block' : 'none';
}

// Function to send command to server
async function sendCommand() {
    const action = document.getElementById('action').value;
    const filename = document.getElementById('filename').value;
    const content = document.getElementById('content').value;
    
    let command = action;
    if (filename) command += `::${filename}`;
    if (content) command += `::${content}`;
    
    try {
        const response = await fetch('/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: command,
                username: currentUsername,
                role: currentRole
            })
        });
        
        const data = await response.json();
        const output = document.getElementById('output');
        
        if (data.status === 'success') {
            if (data.files) {
                output.value = formatLockInfo(data.files, data.locked_files || {}, data.readers || {});
            } else {
                output.value = data.message || 'Command executed successfully';
            }
        } else {
            output.value = `Error: ${data.message}`;
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('output').value = `Error: ${error.message}`;
    }
}

// Function to lock/unlock file
async function toggleLock(action) {
    const filename = document.getElementById('filename').value;
    if (!filename) {
        document.getElementById('output').value = 'Error: Please enter a filename';
        return;
    }

    const command = `${action}::${filename}`;
    try {
        const response = await fetch('/command', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                command: command,
                username: currentUsername,
                role: currentRole
            })
        });
        
        const data = await response.json();
        const output = document.getElementById('output');
        output.value = data.message || (data.status === 'success' ? 'Command executed successfully' : 'Operation failed');
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('output').value = `Error: ${error.message}`;
    }
}

// Function to handle login
async function login() {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/auth', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                username: username,
                password: password
            })
        });
        
        const data = await response.json();
        if (data.status === 'success') {
            document.getElementById('loginForm').style.display = 'none';
            document.getElementById('commandForm').style.display = 'block';
            currentRole = data.role;
            currentUsername = username;
            document.getElementById('output').value = `Logged in as ${username} (${data.role})`;
            
            // Show/hide admin-specific actions
            const actionSelect = document.getElementById('action');
            for (let option of actionSelect.options) {
                if (option.value === 'CREATE' || option.value === 'EDIT' || 
                    option.value === 'DELETE' || option.value === 'LIST_REQUESTS' || 
                    option.value === 'HANDLE_REQUEST') {
                    option.style.display = currentRole === 'admin' ? 'block' : 'none';
                }
            }
        } else {
            document.getElementById('output').value = `Login failed: ${data.message}`;
        }
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('output').value = `Error: ${error.message}`;
    }
}

// Event listeners
document.getElementById('action').addEventListener('change', function() {
    toggleInputFields(this.value);
});

document.getElementById('login-btn').addEventListener('click', async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    try {
        const response = await fetch('/auth', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const result = await response.json();
        
        if (result.status === 'success') {
            currentRole = result.role;
            currentUsername = username;
            document.getElementById('login-section').classList.add('hidden');
            document.getElementById('main-section').classList.remove('hidden');
            document.getElementById(result.role === 'admin' ? 'admin-controls' : 'user-controls').classList.remove('hidden');
            document.getElementById('output').textContent = `Logged in as ${result.role}`;
            // Load initial file list
            executeCommand('LIST');
        } else {
            document.getElementById('output').textContent = result.message || 'Authentication failed';
        }
    } catch (error) {
        document.getElementById('output').textContent = 'Error: ' + error.message;
    }
});

async function executeCommand(action, filename = '', content = '') {
    try {
        let command = action;
        
        if (action === 'CREATE' || action === 'EDIT') {
            command = `${action}::${filename}::${content}`;
        } else if (action === 'READ' || action === 'DELETE') {
            command = `${action}::${filename}`;
        } else if (action === 'MAKE_REQUEST') {
            const requestAction = prompt('Enter request action (CREATE/EDIT/DELETE):');
            if (!requestAction) return;
            
            if (requestAction === 'CREATE' || requestAction === 'EDIT') {
                command = `${action}::${requestAction}::${filename}::${content}`;
            } else if (requestAction === 'DELETE') {
                command = `${action}::${requestAction}::${filename}`;
            } else {
                document.getElementById('output').textContent = 'Invalid request action';
                return;
            }
        } else if (action === 'HANDLE_REQUEST') {
            const requestId = prompt('Enter request ID:');
            if (!requestId) return;
            
            const approve = confirm('Approve request?');
            command = `${action}::${requestId}::${approve ? 'approve' : 'reject'}`;
        }

        const response = await fetch('/command', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ 
                command,
                username: currentUsername,
                role: currentRole
            })
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            if (action === 'LIST') {
                document.getElementById('output').textContent = formatLockInfo(
                    result.files,
                    result.locked_files || {},
                    result.readers || {}
                );
            } else if (action === 'READ') {
                document.getElementById('output').textContent = result.content;
            } else if (action === 'LIST_REQUESTS') {
                document.getElementById('output').textContent = JSON.stringify(result.requests, null, 2);
            } else {
                document.getElementById('output').textContent = result.message;
                if (['CREATE', 'EDIT', 'DELETE'].includes(action)) {
                    // Refresh file list after modification
                    executeCommand('LIST');
                }
            }
        } else {
            document.getElementById('output').textContent = result.message || 'Operation failed';
        }
    } catch (error) {
        document.getElementById('output').textContent = 'Error: ' + error.message;
    }
}

document.getElementById('execute-btn').addEventListener('click', async () => {
    const action = currentRole === 'admin' ? 
        document.getElementById('action').value : 
        document.getElementById('user-action').value;
    const filename = document.getElementById('filename').value;
    const content = document.getElementById('content').value;
    
    if (!action) {
        document.getElementById('output').textContent = 'Please select an action';
        return;
    }
    
    if ((action === 'CREATE' || action === 'EDIT' || action === 'READ' || action === 'DELETE') && !filename) {
        document.getElementById('output').textContent = 'Please enter a filename';
        return;
    }
    
    if ((action === 'CREATE' || action === 'EDIT') && !content) {
        document.getElementById('output').textContent = 'Please enter content';
        return;
    }
    
    await executeCommand(action, filename, content);
});

document.getElementById('logout-btn').addEventListener('click', () => {
    currentRole = null;
    currentUsername = null;
    document.getElementById('output').textContent = 'Logged out successfully';
    document.getElementById('main-section').classList.add('hidden');
    document.getElementById('admin-controls').classList.add('hidden');
    document.getElementById('user-controls').classList.add('hidden');
    document.getElementById('login-section').classList.remove('hidden');
    document.getElementById('username').value = '';
    document.getElementById('password').value = '';
}); 