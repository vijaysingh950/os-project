let currentRole = null;

document.getElementById('login-btn').addEventListener('click', async () => {
    const username = document.getElementById('username').value;
    const password = document.getElementById('password').value;
    
    const response = await fetch('/auth', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, password })
    });
    const result = await response.json();
    const [status, role] = result.response.split('::');
    
    if (status === 'Authentication successful') {
        currentRole = role;
        document.getElementById('login-section').classList.add('hidden');
        document.getElementById('main-section').classList.remove('hidden');
        document.getElementById(role === 'admin' ? 'admin-controls' : 'user-controls').classList.remove('hidden');
        document.getElementById('output').textContent = `Logged in as ${role}`;
    } else {
        document.getElementById('output').textContent = 'Authentication failed';
    }
});

document.getElementById('execute-btn').addEventListener('click', async () => {
    const action = currentRole === 'admin' ? 
        document.getElementById('action').value : 
        document.getElementById('user-action').value;
    const filename = document.getElementById('filename').value;
    const content = document.getElementById('content').value;
    
    let command = action;
    if (action === 'CREATE' || action === 'EDIT') {
        command += `::${filename}::${content}`;
    } else if (action === 'READ' || action === 'DELETE' || action === 'LOCK' || action === 'UNLOCK') {
        command += `::${filename}`;
    } else if (action === 'MAKE_REQUEST') {
        const requestAction = prompt('Enter request action (CREATE/EDIT/DELETE):');
        if (requestAction) {
            command += `::${requestAction}::${filename}`;
            if (requestAction === 'CREATE' || requestAction === 'EDIT') {
                command += `::${content}`;
            }
        }
    } else if (action === 'HANDLE_REQUEST') {
        const requestId = prompt('Enter request ID:');
        const approve = confirm('Approve request?');
        command += `::${requestId}::${approve ? 'approve' : 'reject'}`;
    }

    const response = await fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command })
    });
    const result = await response.json();
    
    if (action === 'LIST' || action === 'LIST_REQUESTS') {
        document.getElementById('output').textContent = JSON.stringify(JSON.parse(result.response), null, 2);
    } else {
        document.getElementById('output').textContent = result.response;
    }
});

document.getElementById('logout-btn').addEventListener('click', async () => {
    const response = await fetch('/command', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command: 'LOGOUT' })
    });
    const result = await response.json();
    document.getElementById('output').textContent = result.response;
    document.getElementById('main-section').classList.add('hidden');
    document.getElementById('admin-controls').classList.add('hidden');
    document.getElementById('user-controls').classList.add('hidden');
    document.getElementById('login-section').classList.remove('hidden');
});