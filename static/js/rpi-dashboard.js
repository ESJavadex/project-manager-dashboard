// Raspberry Pi Dashboard JavaScript

class RpiDashboard {
    constructor() {
        this.refreshInterval = null;
        this.currentTab = 'containers';
        this.init();
    }

    init() {
        this.setupTabNavigation();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    setupTabNavigation() {
        const tabButtons = document.querySelectorAll('.tab-btn');
        const tabContents = document.querySelectorAll('.tab-content');

        tabButtons.forEach(button => {
            button.addEventListener('click', () => {
                const tabName = button.dataset.tab;
                
                // Update button states
                tabButtons.forEach(btn => {
                    btn.classList.remove('active', 'border-blue-500', 'text-blue-600');
                    btn.classList.add('border-transparent', 'text-gray-500');
                });
                button.classList.add('active', 'border-blue-500', 'text-blue-600');
                button.classList.remove('border-transparent', 'text-gray-500');

                // Update tab content visibility
                tabContents.forEach(content => {
                    content.classList.add('hidden');
                });
                document.getElementById(`${tabName}-tab`).classList.remove('hidden');

                this.currentTab = tabName;
                this.loadTabData(tabName);
            });
        });
    }

    setupEventListeners() {
        // GPIO pin controls
        document.addEventListener('click', (e) => {
            if (e.target.classList.contains('gpio-toggle')) {
                this.toggleGpioPin(e.target.dataset.pin);
            }
        });

        // Project management
        const refreshProjectsBtn = document.getElementById('refresh-projects');
        if (refreshProjectsBtn) {
            refreshProjectsBtn.addEventListener('click', () => this.loadProjects());
        }

        // Network scanning
        const scanNetworkBtn = document.getElementById('scan-network');
        if (scanNetworkBtn) {
            scanNetworkBtn.addEventListener('click', () => this.scanNetwork());
        }

        // Services refresh
        const refreshServicesBtn = document.getElementById('refresh-services');
        if (refreshServicesBtn) {
            refreshServicesBtn.addEventListener('click', () => this.loadServices());
        }
    }

    startAutoRefresh() {
        this.refreshInterval = setInterval(() => {
            if (this.currentTab === 'system') {
                this.loadSystemStats();
                this.loadRpiStats();
            }
        }, 5000); // Refresh every 5 seconds for system tab

        // Initial load
        this.loadSystemStats();
        this.loadRpiStats();
    }

    loadTabData(tabName) {
        switch (tabName) {
            case 'system':
                this.loadSystemStats();
                this.loadRpiStats();
                break;
            case 'gpio':
                this.loadGpioStatus();
                break;
            case 'projects':
                this.loadProjects();
                break;
            case 'network':
                this.loadNetworkStatus();
                break;
            case 'services':
                this.loadServices();
                break;
        }
    }

    async loadSystemStats() {
        try {
            const response = await fetch('/api/stats/global');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats;
                
                // Update system stats
                document.getElementById('cpu-usage').textContent = `${stats.system.cpu_percent}%`;
                
                const memPercent = (stats.system.memory_used / stats.system.memory_total * 100).toFixed(1);
                document.getElementById('memory-usage').textContent = `${memPercent}%`;
                
                const diskPercent = (stats.system.disk_used / stats.system.disk_total * 100).toFixed(1);
                document.getElementById('disk-usage').textContent = `${diskPercent}%`;
                
                // Update container stats
                document.getElementById('running-containers').textContent = stats.containers.running;
                document.getElementById('stopped-containers').textContent = stats.containers.stopped;
                document.getElementById('total-containers').textContent = stats.containers.total;
            }
        } catch (error) {
            console.error('Failed to load system stats:', error);
        }
    }

    async loadRpiStats() {
        try {
            const response = await fetch('/api/stats/rpi');
            const data = await response.json();
            
            if (data.success) {
                const stats = data.stats;
                
                // Update Pi hardware stats
                document.getElementById('cpu-temp').textContent = `${stats.cpu_temperature}°C`;
                document.getElementById('gpu-temp').textContent = stats.gpu_temperature ? `${stats.gpu_temperature}°C` : 'N/A';
                document.getElementById('cpu-freq').textContent = `${stats.cpu_frequency_mhz} MHz`;
                document.getElementById('core-voltage').textContent = `${stats.core_voltage}V`;
                
                // Handle throttling warnings
                this.updateThrottlingWarnings(stats.throttling);
            }
        } catch (error) {
            console.error('Failed to load Pi stats:', error);
        }
    }

    updateThrottlingWarnings(throttling) {
        const warningsDiv = document.getElementById('throttling-warnings');
        const warningsList = document.getElementById('throttling-list');
        
        const warnings = [];
        if (throttling.under_voltage) warnings.push('Under-voltage detected');
        if (throttling.frequency_capped) warnings.push('ARM frequency capped');
        if (throttling.currently_throttled) warnings.push('Currently being throttled');
        if (throttling.temperature_limit) warnings.push('Soft temperature limit active');
        
        if (warnings.length > 0) {
            warningsList.innerHTML = warnings.map(w => `<li>${w}</li>`).join('');
            warningsDiv.classList.remove('hidden');
        } else {
            warningsDiv.classList.add('hidden');
        }
    }

    async loadGpioStatus() {
        try {
            const response = await fetch('/api/gpio/status');
            const data = await response.json();
            
            if (data.success) {
                this.renderGpioPins(data.pins);
            } else {
                document.getElementById('gpio-pins').innerHTML = `
                    <div class="col-span-full text-center text-gray-500 py-8">
                        <i class="fas fa-exclamation-circle text-3xl mb-2"></i>
                        <p>GPIO not available on this system</p>
                    </div>
                `;
            }
        } catch (error) {
            console.error('Failed to load GPIO status:', error);
        }
    }

    renderGpioPins(pins) {
        const container = document.getElementById('gpio-pins');
        const pinNumbers = Object.keys(pins).sort((a, b) => parseInt(a) - parseInt(b));
        
        container.innerHTML = pinNumbers.map(pinNum => {
            const pin = pins[pinNum];
            const isHigh = pin.value === 1;
            const statusColor = isHigh ? 'bg-green-500' : 'bg-gray-400';
            
            return `
                <div class="border rounded-lg p-3 text-center">
                    <div class="text-sm font-semibold mb-2">GPIO ${pinNum}</div>
                    <div class="w-6 h-6 rounded-full mx-auto mb-2 ${statusColor}"></div>
                    <div class="text-xs text-gray-600">${pin.mode}</div>
                    <div class="text-xs font-mono">${isHigh ? 'HIGH' : 'LOW'}</div>
                    ${pin.mode === 'output' ? `
                        <button class="gpio-toggle mt-2 px-2 py-1 text-xs bg-blue-500 text-white rounded" 
                                data-pin="${pinNum}">Toggle</button>
                    ` : ''}
                </div>
            `;
        }).join('');
    }

    async toggleGpioPin(pin) {
        try {
            const response = await fetch(`/api/gpio/pin/${pin}/set`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ value: 1, mode: 'output' }) // Toggle logic would be more complex
            });
            
            if (response.ok) {
                this.loadGpioStatus(); // Refresh GPIO status
            }
        } catch (error) {
            console.error('Failed to toggle GPIO pin:', error);
        }
    }

    async loadProjects() {
        try {
            const response = await fetch('/api/projects');
            const data = await response.json();
            
            if (data.success) {
                this.renderProjects(data.projects);
            }
        } catch (error) {
            console.error('Failed to load projects:', error);
        }
    }

    renderProjects(projects) {
        const container = document.getElementById('projects-list');
        
        if (projects.length === 0) {
            container.innerHTML = `
                <div class="text-center text-gray-500 py-8">
                    <i class="fas fa-folder-open text-3xl mb-2"></i>
                    <p>No projects found in ~/projects directory</p>
                </div>
            `;
            return;
        }
        
        container.innerHTML = projects.map(project => `
            <div class="border rounded-lg p-4 mb-4">
                <div class="flex justify-between items-start">
                    <div>
                        <h4 class="font-semibold flex items-center">
                            <i class="fas fa-folder mr-2"></i>${project.name}
                            ${project.is_git ? '<i class="fab fa-git-alt ml-2 text-orange-500"></i>' : ''}
                        </h4>
                        <p class="text-sm text-gray-600">${project.path}</p>
                        ${project.git_info ? `
                            <div class="mt-2 text-xs">
                                <span class="bg-blue-100 text-blue-800 px-2 py-1 rounded mr-2">${project.git_info.branch}</span>
                                <span class="bg-gray-100 text-gray-800 px-2 py-1 rounded">${project.git_info.commit}</span>
                                ${project.git_info.dirty ? '<span class="bg-yellow-100 text-yellow-800 px-2 py-1 rounded ml-2">Modified</span>' : ''}
                            </div>
                        ` : ''}
                    </div>
                    ${project.is_git ? `
                        <div class="flex space-x-2">
                            <button class="git-action px-3 py-1 text-sm bg-green-500 text-white rounded hover:bg-green-600" 
                                    data-project="${project.name}" data-action="pull">Pull</button>
                            <button class="git-action px-3 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600" 
                                    data-project="${project.name}" data-action="status">Status</button>
                        </div>
                    ` : ''}
                </div>
            </div>
        `).join('');
        
        // Add event listeners for git actions
        document.querySelectorAll('.git-action').forEach(btn => {
            btn.addEventListener('click', () => {
                this.performGitAction(btn.dataset.project, btn.dataset.action);
            });
        });
    }

    async performGitAction(project, action) {
        try {
            const response = await fetch(`/api/projects/${project}/git/${action}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Git ${action} completed successfully`, 'success');
                this.loadProjects(); // Refresh projects list
            } else {
                this.showNotification(`Git ${action} failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error(`Failed to perform git ${action}:`, error);
            this.showNotification(`Git ${action} failed`, 'error');
        }
    }

    async loadNetworkStatus() {
        try {
            const response = await fetch('/api/network/status');
            const data = await response.json();
            
            if (data.success) {
                this.renderNetworkInfo(data.network);
            }
        } catch (error) {
            console.error('Failed to load network status:', error);
        }
    }

    renderNetworkInfo(network) {
        const container = document.getElementById('network-info');
        
        const interfacesList = Object.entries(network.interfaces).map(([name, info]) => `
            <div class="mb-4 p-3 border rounded">
                <div class="font-semibold flex items-center">
                    <i class="fas fa-network-wired mr-2"></i>${name}
                    <span class="ml-2 px-2 py-1 text-xs rounded ${info.is_up ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'}">
                        ${info.is_up ? 'UP' : 'DOWN'}
                    </span>
                </div>
                <div class="text-sm text-gray-600 mt-1">
                    ${info.addresses.join(', ')}
                </div>
            </div>
        `).join('');
        
        container.innerHTML = `
            <div class="space-y-4">
                ${interfacesList}
                ${network.wifi_signal ? `
                    <div class="p-3 border rounded">
                        <div class="font-semibold flex items-center">
                            <i class="fas fa-wifi mr-2"></i>WiFi Signal
                        </div>
                        <div class="text-sm text-gray-600">${network.wifi_signal}</div>
                    </div>
                ` : ''}
                <div class="p-3 border rounded">
                    <div class="font-semibold mb-2">Network Statistics</div>
                    <div class="grid grid-cols-2 gap-2 text-sm">
                        <div>Bytes Sent: ${this.formatBytes(network.stats.bytes_sent)}</div>
                        <div>Bytes Received: ${this.formatBytes(network.stats.bytes_recv)}</div>
                        <div>Packets Sent: ${network.stats.packets_sent.toLocaleString()}</div>
                        <div>Packets Received: ${network.stats.packets_recv.toLocaleString()}</div>
                    </div>
                </div>
            </div>
        `;
    }

    async scanNetwork() {
        const button = document.getElementById('scan-network');
        const originalText = button.innerHTML;
        button.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Scanning...';
        button.disabled = true;
        
        try {
            const response = await fetch('/api/network/scan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ target: '192.168.1.0/24' })
            });
            const data = await response.json();
            
            if (data.success) {
                this.renderScanResults(data.hosts);
            }
        } catch (error) {
            console.error('Failed to scan network:', error);
        } finally {
            button.innerHTML = originalText;
            button.disabled = false;
        }
    }

    renderScanResults(hosts) {
        const container = document.getElementById('network-scan-results');
        
        if (hosts.length === 0) {
            container.innerHTML = '<div class="text-gray-500 text-center py-4">No active hosts found</div>';
            return;
        }
        
        container.innerHTML = `
            <div class="mt-4">
                <h4 class="font-semibold mb-2">Active Hosts (${hosts.length})</h4>
                <div class="space-y-2">
                    ${hosts.map(host => `
                        <div class="flex items-center p-2 border rounded">
                            <i class="fas fa-desktop mr-2 text-green-500"></i>
                            <span class="font-mono">${host}</span>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }

    async loadServices() {
        try {
            const response = await fetch('/api/services');
            const data = await response.json();
            
            if (data.success) {
                this.renderServices(data.services);
            }
        } catch (error) {
            console.error('Failed to load services:', error);
        }
    }

    renderServices(services) {
        const container = document.getElementById('services-list');
        
        container.innerHTML = `
            <div class="overflow-x-auto">
                <table class="min-w-full divide-y divide-gray-200">
                    <thead class="bg-gray-50">
                        <tr>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Service</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Description</th>
                            <th class="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Actions</th>
                        </tr>
                    </thead>
                    <tbody class="divide-y divide-gray-200">
                        ${services.map(service => `
                            <tr>
                                <td class="px-6 py-4 text-sm font-medium text-gray-900">${service.name}</td>
                                <td class="px-6 py-4 text-sm">
                                    <span class="px-2 py-1 text-xs rounded-full ${
                                        service.active === 'active' ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                                    }">
                                        ${service.active}
                                    </span>
                                </td>
                                <td class="px-6 py-4 text-sm text-gray-500 max-w-xs truncate">${service.description}</td>
                                <td class="px-6 py-4 text-sm space-x-2">
                                    <button class="service-action text-green-600 hover:text-green-800" 
                                            data-service="${service.name}" data-action="start">Start</button>
                                    <button class="service-action text-red-600 hover:text-red-800" 
                                            data-service="${service.name}" data-action="stop">Stop</button>
                                    <button class="service-action text-blue-600 hover:text-blue-800" 
                                            data-service="${service.name}" data-action="restart">Restart</button>
                                </td>
                            </tr>
                        `).join('')}
                    </tbody>
                </table>
            </div>
        `;
        
        // Add event listeners for service actions
        document.querySelectorAll('.service-action').forEach(btn => {
            btn.addEventListener('click', () => {
                this.performServiceAction(btn.dataset.service, btn.dataset.action);
            });
        });
    }

    async performServiceAction(service, action) {
        try {
            const response = await fetch(`/api/services/${service}/${action}`, {
                method: 'POST'
            });
            const data = await response.json();
            
            if (data.success) {
                this.showNotification(`Service ${action} completed successfully`, 'success');
                this.loadServices(); // Refresh services list
            } else {
                this.showNotification(`Service ${action} failed: ${data.error}`, 'error');
            }
        } catch (error) {
            console.error(`Failed to perform service ${action}:`, error);
            this.showNotification(`Service ${action} failed`, 'error');
        }
    }

    formatBytes(bytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let size = bytes;
        let unitIndex = 0;
        
        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }
        
        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    showNotification(message, type) {
        // Simple notification system
        const notification = document.createElement('div');
        notification.className = `fixed top-4 right-4 px-4 py-2 rounded shadow-lg z-50 ${
            type === 'success' ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
        }`;
        notification.textContent = message;
        
        document.body.appendChild(notification);
        
        setTimeout(() => {
            notification.remove();
        }, 3000);
    }
}

// Initialize dashboard when page loads
document.addEventListener('DOMContentLoaded', () => {
    new RpiDashboard();
});