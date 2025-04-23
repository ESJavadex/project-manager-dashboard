document.addEventListener('DOMContentLoaded', function() {
    // Fetch global stats on page load
    fetchGlobalStats();
    
    // Set up refresh button
    document.getElementById('refresh-stats').addEventListener('click', fetchGlobalStats);
    
    // Fetch global stats every 10 seconds
    setInterval(fetchGlobalStats, 10000);
    
    async function fetchGlobalStats() {
        try {
            const response = await fetch('/api/stats/global');
            const data = await response.json();
            
            if (data.success) {
                updateDashboardStats(data.stats);
            } else {
                console.error('Error fetching stats:', data.error);
            }
        } catch (error) {
            console.error('Request failed:', error);
        }
    }
    
    function updateDashboardStats(stats) {
        // Update container counts
        document.getElementById('total-containers').textContent = stats.containers.total;
        document.getElementById('running-containers').textContent = stats.containers.running;
        document.getElementById('stopped-containers').textContent = stats.containers.stopped;
        
        // Update resource usage
        document.getElementById('cpu-usage').textContent = `${stats.system.cpu_percent.toFixed(1)}%`;
        document.getElementById('memory-usage').textContent = formatBytes(stats.system.memory_used);
        document.getElementById('memory-total').textContent = formatBytes(stats.system.memory_total);
        document.getElementById('disk-usage').textContent = formatBytes(stats.system.disk_used);
        document.getElementById('disk-total').textContent = formatBytes(stats.system.disk_total);
        
        // Update CPU usage bar
        const cpuBar = document.getElementById('cpu-usage-bar');
        cpuBar.style.width = `${stats.system.cpu_percent}%`;
        
        // Update memory usage bar
        const memoryPercent = (stats.system.memory_used / stats.system.memory_total) * 100;
        const memoryBar = document.getElementById('memory-usage-bar');
        memoryBar.style.width = `${memoryPercent}%`;
        
        // Update disk usage bar
        const diskPercent = (stats.system.disk_used / stats.system.disk_total) * 100;
        const diskBar = document.getElementById('disk-usage-bar');
        diskBar.style.width = `${diskPercent}%`;
        
        // Update network stats
        document.getElementById('network-rx').textContent = formatBytes(stats.system.network_rx);
        document.getElementById('network-tx').textContent = formatBytes(stats.system.network_tx);
        
        // Update last updated time
        document.getElementById('last-updated').textContent = new Date().toLocaleTimeString();
    }
    
    function formatBytes(bytes, decimals = 2) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const dm = decimals < 0 ? 0 : decimals;
        const sizes = ['Bytes', 'KB', 'MB', 'GB', 'TB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + ' ' + sizes[i];
    }
});
