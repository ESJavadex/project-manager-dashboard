document.addEventListener('DOMContentLoaded', function() {
    // Modal handling
    const modals = {
        details: document.getElementById('detailsModal'),
        logs: document.getElementById('logsModal'),
        confirmation: document.getElementById('confirmationModal')
    };
    
    // Close modals when clicking the close button
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            Object.values(modals).forEach(modal => {
                modal.classList.add('hidden');
            });
        });
    });
    
    // Close modals when clicking outside
    Object.values(modals).forEach(modal => {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                modal.classList.add('hidden');
            }
        });
    });
    
    // Toast notification system
    const toastContainer = document.getElementById('toastContainer');
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `p-4 rounded shadow-lg flex items-center justify-between ${
            type === 'success' ? 'bg-green-500' :
            type === 'error' ? 'bg-red-500' :
            type === 'warning' ? 'bg-yellow-500' : 'bg-blue-500'
        } text-white`;
        
        toast.innerHTML = `
            <div class="flex items-center">
                <i class="fas ${
                    type === 'success' ? 'fa-check-circle' :
                    type === 'error' ? 'fa-exclamation-circle' :
                    type === 'warning' ? 'fa-exclamation-triangle' : 'fa-info-circle'
                } mr-2"></i>
                <span>${message}</span>
            </div>
            <button class="ml-4 text-white hover:text-gray-200">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        toastContainer.appendChild(toast);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            toast.classList.add('opacity-0', 'transition-opacity', 'duration-500');
            setTimeout(() => {
                toast.remove();
            }, 500);
        }, 5000);
        
        // Close button
        toast.querySelector('button').addEventListener('click', () => {
            toast.remove();
        });
    }
    
    // Format bytes to human-readable
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
    
    // Format date
    function formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleString();
    }
    
    // Container action handlers
    let currentContainerId = null;
    let statsInterval = null;
    
    document.querySelectorAll('.container-actions a').forEach(link => {
        link.addEventListener('click', async function(e) {
            e.preventDefault();
            const row = this.closest('tr');
            const containerId = row.getAttribute('data-container-id');
            currentContainerId = containerId;
            const action = this.getAttribute('data-action');
            const containerName = row.querySelector('td:first-child').textContent.trim();
            
            // Handle different actions
            switch (action) {
                case 'info':
                    await showContainerDetails(containerId);
                    break;
                    
                case 'logs':
                    await showContainerLogs(containerId, containerName);
                    break;
                    
                case 'stats':
                    await showContainerDetails(containerId, true); // true = focus on stats
                    break;
                    
                case 'start':
                case 'stop':
                case 'restart':
                    showConfirmation(action, containerId, containerName);
                    break;
            }
        });
    });
    
    // Show container details
    async function showContainerDetails(containerId, focusStats = false) {
        try {
            // Show modal with loading state
            document.getElementById('detailsModalTitle').textContent = 'Loading Container Details...';
            modals.details.classList.remove('hidden');
            
            // Fetch container info
            const response = await fetch(`/container/${containerId}/info`, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            if (!data.success) {
                showToast(`Error: ${data.error}`, 'error');
                return;
            }
            
            // Update modal title
            document.getElementById('detailsModalTitle').textContent = `Container: ${data.info.name}`;
            
            // Fill in basic info
            document.getElementById('container-id').textContent = data.info.id.substring(0, 12);
            document.getElementById('container-name').textContent = data.info.name;
            document.getElementById('container-status').textContent = data.info.status;
            document.getElementById('container-image').textContent = data.info.image;
            document.getElementById('container-created').textContent = formatDate(data.info.created);
            
            // Fill in ports
            const portsContainer = document.getElementById('container-ports');
            portsContainer.innerHTML = '';
            
            if (data.info.ports && Object.keys(data.info.ports).length > 0) {
                for (const [containerPort, hostBindings] of Object.entries(data.info.ports)) {
                    if (hostBindings) {
                        hostBindings.forEach(binding => {
                            const portMapping = document.createElement('div');
                            portMapping.className = 'bg-blue-100 p-2 rounded';
                            portMapping.innerHTML = `${binding.HostIp || '0.0.0.0'}:${binding.HostPort} → ${containerPort}`;
                            portsContainer.appendChild(portMapping);
                        });
                    } else {
                        const portMapping = document.createElement('div');
                        portMapping.className = 'bg-gray-100 p-2 rounded';
                        portMapping.innerHTML = `${containerPort} (not published)`;
                        portsContainer.appendChild(portMapping);
                    }
                }
            } else {
                portsContainer.innerHTML = '<p>No ports exposed</p>';
            }
            
            // Fill in volumes
            const volumesContainer = document.getElementById('container-volumes');
            volumesContainer.innerHTML = '';
            
            if (data.info.volumes && data.info.volumes.length > 0) {
                const volumesList = document.createElement('ul');
                volumesList.className = 'list-disc pl-5';
                
                data.info.volumes.forEach(volume => {
                    const volumeItem = document.createElement('li');
                    volumeItem.textContent = volume;
                    volumesList.appendChild(volumeItem);
                });
                
                volumesContainer.appendChild(volumesList);
            } else {
                volumesContainer.innerHTML = '<p>No volumes mounted</p>';
            }
            
            // Fill in environment variables
            const envContainer = document.getElementById('container-env');
            envContainer.innerHTML = '';
            
            if (data.info.env && data.info.env.length > 0) {
                const envTable = document.createElement('table');
                envTable.className = 'min-w-full';
                
                data.info.env.forEach(env => {
                    const row = document.createElement('tr');
                    const parts = env.split('=');
                    const key = parts[0];
                    const value = parts.slice(1).join('=');
                    
                    row.innerHTML = `
                        <td class="pr-4 font-mono text-xs">${key}</td>
                        <td class="font-mono text-xs">${value}</td>
                    `;
                    
                    envTable.appendChild(row);
                });
                
                envContainer.appendChild(envTable);
            } else {
                envContainer.innerHTML = '<p>No environment variables</p>';
            }
            
            // Start fetching stats if container is running
            if (data.info.status === 'running') {
                fetchContainerStats(containerId);
                // Set up interval to update stats every 2 seconds
                clearInterval(statsInterval);
                statsInterval = setInterval(() => {
                    fetchContainerStats(containerId);
                }, 2000);
            } else {
                document.getElementById('container-cpu').textContent = 'N/A';
                document.getElementById('container-memory').textContent = 'N/A';
                document.getElementById('container-network').textContent = 'N/A';
                document.getElementById('cpu-bar').style.width = '0%';
                document.getElementById('memory-bar').style.width = '0%';
            }
            
        } catch (error) {
            showToast(`Request failed: ${error}`, 'error');
        }
    }
    
    // Fetch and update container stats
    async function fetchContainerStats(containerId) {
        try {
            const response = await fetch(`/container/${containerId}/stats`, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            if (!data.success) return;
            
            // Update CPU
            document.getElementById('container-cpu').textContent = `${data.stats.cpu_percent.toFixed(1)}%`;
            document.getElementById('cpu-bar').style.width = `${Math.min(data.stats.cpu_percent, 100)}%`;
            
            // Update Memory
            const memPercent = data.stats.mem_percent;
            const memUsage = formatBytes(data.stats.mem_usage);
            const memLimit = formatBytes(data.stats.mem_limit);
            
            document.getElementById('container-memory').textContent = 
                `${memPercent.toFixed(1)}% (${memUsage} / ${memLimit})`;
            document.getElementById('memory-bar').style.width = `${Math.min(memPercent, 100)}%`;
            
            // Update Network
            document.getElementById('container-network').textContent = 
                `↓ ${formatBytes(data.stats.rx_bytes)} / ↑ ${formatBytes(data.stats.tx_bytes)}`;
            
        } catch (error) {
            console.error('Error fetching stats:', error);
        }
    }
    
    // Show container logs
    async function showContainerLogs(containerId, containerName) {
        try {
            // Show modal with loading state
            document.getElementById('logsModalTitle').textContent = `Logs: ${containerName}`;
            document.getElementById('container-logs').textContent = 'Loading logs...';
            modals.logs.classList.remove('hidden');
            
            // Fetch logs
            const response = await fetch(`/container/${containerId}/logs`, {
                method: 'GET',
                headers: {'Content-Type': 'application/json'}
            });
            
            const data = await response.json();
            if (!data.success) {
                document.getElementById('container-logs').textContent = `Error: ${data.error}`;
                return;
            }
            
            // Update logs content
            document.getElementById('container-logs').textContent = data.logs || 'No logs available';
            
            // Scroll to bottom of logs
            const logsContent = document.getElementById('logsModalContent');
            logsContent.scrollTop = logsContent.scrollHeight;
            
        } catch (error) {
            document.getElementById('container-logs').textContent = `Request failed: ${error}`;
        }
    }
    
    // Refresh logs button
    document.getElementById('refreshLogs').addEventListener('click', async () => {
        if (currentContainerId) {
            const containerName = document.getElementById('logsModalTitle').textContent.replace('Logs: ', '');
            await showContainerLogs(currentContainerId, containerName);
        }
    });
    
    // Show confirmation modal
    function showConfirmation(action, containerId, containerName) {
        // Set confirmation message based on action
        let message = '';
        let buttonClass = '';
        
        switch (action) {
            case 'start':
                message = `Are you sure you want to start container "${containerName}"?`;
                buttonClass = 'bg-green-500 hover:bg-green-600';
                break;
            case 'stop':
                message = `Are you sure you want to stop container "${containerName}"?\nThis may disrupt services.`;
                buttonClass = 'bg-red-500 hover:bg-red-600';
                break;
            case 'restart':
                message = `Are you sure you want to restart container "${containerName}"?\nThis will cause a brief service interruption.`;
                buttonClass = 'bg-yellow-500 hover:bg-yellow-600';
                break;
        }
        
        // Update confirmation modal
        document.getElementById('confirmationMessage').textContent = message;
        const confirmButton = document.getElementById('confirmAction');
        confirmButton.className = `px-4 py-2 ${buttonClass} text-white rounded`;
        confirmButton.textContent = action.charAt(0).toUpperCase() + action.slice(1);
        
        // Set up confirmation action
        confirmButton.onclick = async () => {
            try {
                modals.confirmation.classList.add('hidden');
                showToast(`${action.charAt(0).toUpperCase() + action.slice(1)}ing container...`, 'info');
                
                const response = await fetch(`/container/${containerId}/${action}`, {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'}
                });
                
                const data = await response.json();
                if (data.success) {
                    showToast(`Container ${action}ed successfully!`, 'success');
                    setTimeout(() => window.location.reload(), 1000);
                } else {
                    showToast(`Error: ${data.error}`, 'error');
                }
            } catch (error) {
                showToast(`Request failed: ${error}`, 'error');
            }
        };
        
        // Show confirmation modal
        modals.confirmation.classList.remove('hidden');
    }
    
    // Clean up intervals when modal is closed
    document.querySelectorAll('.close-modal').forEach(btn => {
        btn.addEventListener('click', () => {
            clearInterval(statsInterval);
        });
    });
});
