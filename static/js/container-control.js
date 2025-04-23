document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.container-actions a').forEach(link => {
        link.addEventListener('click', async function(e) {
            e.preventDefault();
            const containerId = this.closest('tr').dataset.containerId;
            const action = this.querySelector('i').className.split(' ')[1];
            
            let endpoint = '';
            let method = 'POST';
            if (action === 'fa-play') endpoint = 'start';
            else if (action === 'fa-stop') endpoint = 'stop';
            else if (action === 'fa-redo') endpoint = 'restart';
            else if (action === 'fa-info-circle') {
                endpoint = 'info';
                method = 'GET';
            }
            
            try {
                const response = await fetch(`/container/${containerId}/${endpoint}`, {
                    method: method,
                    headers: {'Content-Type': 'application/json'}
                });
                const data = await response.json();
                if (endpoint === 'info') {
                    if (data.success) {
                        alert(JSON.stringify(data.info, null, 2));
                    } else {
                        alert(`Error: ${data.error}`);
                    }
                } else {
                    if (data.success) {
                        window.location.reload();
                    } else {
                        alert(`Error: ${data.error}`);
                    }
                }
            } catch (error) {
                alert(`Request failed: ${error}`);
            }
        });
    });
});
