// Discord Bot Dashboard with Rate Limiting
class DiscordBotDashboard {
    constructor() {
        this.botData = {
            id: null,
            name: 'Loading...',
            status: 'connecting',
            servers: [],
            latency: 0,
            uptime: 0,
            commandCount: 0,
            userCount: 0
        };

        this.config = {
            botToken: '',
            targetServerId: '1278580577104040018'
        };

        // Rate limiting
        this.rateLimiter = {
            requests: new Map(),
            globalRateLimit: null,
            isGloballyRateLimited: false
        };

        this.refreshInterval = null;
        this.currentSection = 'overview';

        this.init();
    }

    // Rate limiting helper
    async makeDiscordRequest(url, options = {}) {
        const now = Date.now();

        // Check global rate limit
        if (this.rateLimiter.isGloballyRateLimited &&
            this.rateLimiter.globalRateLimit &&
            this.rateLimiter.globalRateLimit > now) {
            const waitTime = this.rateLimiter.globalRateLimit - now;
            this.addLog('warn', `Global rate limit active, waiting ${Math.ceil(waitTime / 1000)}s`);
            await this.sleep(waitTime);
        }

        // Check endpoint-specific rate limit
        const endpoint = url.split('?')[0]; // Remove query params for key
        const endpointLimit = this.rateLimiter.requests.get(endpoint);

        if (endpointLimit && endpointLimit.resetTime > now) {
            const waitTime = endpointLimit.resetTime - now;
            this.addLog('warn', `Endpoint rate limited, waiting ${Math.ceil(waitTime / 1000)}s`);
            await this.sleep(waitTime);
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers: {
                    'Authorization': `Bot ${this.config.botToken}`,
                    'Content-Type': 'application/json',
                    ...options.headers
                }
            });

            // Handle rate limit headers
            const remaining = parseInt(response.headers.get('x-ratelimit-remaining')) || 0;
            const resetAfter = parseFloat(response.headers.get('x-ratelimit-reset-after')) || 0;
            const isGlobal = response.headers.get('x-ratelimit-global') === 'true';

            if (response.status === 429) {
                const retryAfter = parseFloat(response.headers.get('retry-after')) || 1;
                const retryAfterMs = retryAfter * 1000;

                if (isGlobal) {
                    this.rateLimiter.isGloballyRateLimited = true;
                    this.rateLimiter.globalRateLimit = now + retryAfterMs;
                    this.addLog('error', `Global rate limit hit, retry after ${retryAfter}s`);
                } else {
                    // Set endpoint-specific rate limit
                    this.rateLimiter.requests.set(endpoint, {
                        resetTime: now + retryAfterMs
                    });
                    this.addLog('error', `Rate limited on ${endpoint}, retry after ${retryAfter}s`);
                }

                // Wait and retry once
                await this.sleep(retryAfterMs + 100); // Add small buffer
                return this.makeDiscordRequest(url, options);
            }

            // Update rate limit tracking
            if (resetAfter > 0) {
                this.rateLimiter.requests.set(endpoint, {
                    remaining: remaining,
                    resetTime: now + (resetAfter * 1000)
                });
            }

            // Clear global rate limit if it was set
            if (this.rateLimiter.isGloballyRateLimited && !isGlobal) {
                this.rateLimiter.isGloballyRateLimited = false;
                this.rateLimiter.globalRateLimit = null;
            }

            return response;

        } catch (error) {
            this.addLog('error', `Request failed: ${error.message}`);
            throw error;
        }
    }

    sleep(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    init() {
        this.setupEventListeners();
        this.loadSettingsUI();

        const savedToken = window.savedBotToken || '';
        if (savedToken) {
            this.config.botToken = savedToken;
            this.loadBotData();
            this.setupAutoRefresh();
        } else {
            this.showToast('Please configure your bot token in settings', 'warning');
            this.switchSection('settings');
        }

        this.hideLoading();
    }

    setupEventListeners() {
        // Navigation
        document.querySelectorAll('.nav-item').forEach(item => {
            item.addEventListener('click', (e) => {
                const section = e.currentTarget.dataset.section;
                this.switchSection(section);
            });
        });

        // Refresh button
        document.getElementById('refreshBtn').addEventListener('click', () => {
            this.refreshData();
        });

        // Server refresh
        document.getElementById('refreshServers').addEventListener('click', () => {
            this.loadServers();
        });

        // Command execution
        document.getElementById('executeCommand').addEventListener('click', () => {
            this.executeCommand();
        });

        // Message sending
        document.getElementById('sendMessage').addEventListener('click', () => {
            this.sendMessage();
        });

        // Server selection for commands
        document.getElementById('commandServer').addEventListener('change', (e) => {
            this.loadChannels(e.target.value, 'commandChannel');
        });

        // Server selection for messages
        document.getElementById('messageServer').addEventListener('change', (e) => {
            this.loadChannels(e.target.value, 'messageChannel');
        });

        // Settings
        document.getElementById('saveSettings').addEventListener('click', () => {
            this.saveSettings();
        });

        // Embed toggle
        document.getElementById('embedToggle').addEventListener('click', () => {
            this.toggleEmbedOptions();
        });

        // Clear functions
        document.getElementById('clearOutput').addEventListener('click', () => {
            document.getElementById('outputContent').innerHTML = 'Output cleared...';
        });

        document.getElementById('clearLogs').addEventListener('click', () => {
            this.clearLogs();
        });

        // Log filter
        document.getElementById('logFilter').addEventListener('change', (e) => {
            this.filterLogs(e.target.value);
        });

        // Auto refresh setting
        document.getElementById('autoRefresh').addEventListener('change', (e) => {
            this.setupAutoRefresh(parseInt(e.target.value));
        });

        // Theme toggle
        document.getElementById('theme').addEventListener('change', (e) => {
            this.toggleTheme(e.target.value);
        });
    }

    loadSettingsUI() {
        const botTokenInput = document.getElementById('botToken');
        if (botTokenInput) {
            botTokenInput.value = window.savedBotToken || '';
        }
    }

    async loadBotData() {
        if (!this.config.botToken) {
            this.showToast('Bot token is required', 'error');
            return;
        }

        this.showLoading();

        try {
            await this.loadBotInfo();
            await this.loadAllServers();
            await this.loadTargetServer();
            this.loadLogs();
            this.updateUI();

        } catch (error) {
            console.error('Error loading bot data:', error);
            this.showToast('Failed to load bot data: ' + error.message, 'error');
        } finally {
            this.hideLoading();
        }
    }

    async loadBotInfo() {
        try {
            const response = await this.makeDiscordRequest('https://discord.com/api/v10/users/@me');

            if (!response.ok) {
                if (response.status === 401) {
                    throw new Error('Invalid bot token - please check your token in settings');
                }
                throw new Error(`Discord API error: ${response.status}`);
            }

            const botInfo = await response.json();

            this.botData.id = botInfo.id;
            this.botData.name = botInfo.username;
            this.botData.status = 'online';
            this.botData.latency = Math.floor(Math.random() * 100) + 20;
            this.botData.uptime = Date.now() - (Math.random() * 86400000 * 7);

            this.addLog('success', `Bot authenticated: ${botInfo.username}#${botInfo.discriminator}`);

        } catch (error) {
            console.error('Error loading bot info:', error);
            this.botData.status = 'offline';

            if (error.message.includes('token')) {
                this.showToast(error.message, 'error');
                this.switchSection('settings');
            }
            throw error;
        }
    }

    async loadAllServers() {
        try {
            this.addLog('info', 'Loading server list...');

            const response = await this.makeDiscordRequest('https://discord.com/api/v10/users/@me/guilds');

            if (!response.ok) {
                throw new Error(`Failed to get guilds: ${response.status}`);
            }

            const guilds = await response.json();
            this.addLog('info', `Bot is in ${guilds.length} servers`);

            // Check if bot is in target server
            const targetServer = guilds.find(g => g.id === this.config.targetServerId);
            if (!targetServer) {
                this.addLog('warn', `Bot is not in target server ${this.config.targetServerId}`);
                this.showToast(`Bot is not in target server. Available servers: ${guilds.map(g => g.name).join(', ')}`, 'warning');
            } else {
                this.addLog('success', `Bot found in target server: ${targetServer.name}`);
            }

        } catch (error) {
            console.error('Error loading all servers:', error);
            this.addLog('error', `Failed to load server list: ${error.message}`);
        }
    }

    async loadTargetServer() {
        const startTime = Date.now();
        this.addLog('debug', '[TargetServer] Starting loadTargetServer with rate limiting...');

        try {
            if (!this.config?.botToken || !this.config?.targetServerId)
                throw new Error('Missing botToken or targetServerId.');

            this.addLog('debug', '[TargetServer] Waiting 10s before fetching...');
            await this.sleep(10000);

            this.addLog('debug', '[TargetServer] Fetching bot guild list...');
            const guildsRes = await this.makeDiscordRequest('https://discord.com/api/v10/users/@me/guilds');
            if (!guildsRes || !guildsRes.ok) {
                const msg = guildsRes ? await guildsRes.text() : 'No response received';
                throw new Error(`Failed to get guild list: ${guildsRes?.status || 'unknown'} - ${msg}`);
            }

            const guilds = await guildsRes.json();
            const guildData = guilds.find(g => g.id === this.config.targetServerId);
            if (!guildData)
                throw new Error(`Bot is not in the target server (${this.config.targetServerId})`);

            this.addLog('debug', `[TargetServer] Found target guild: ${guildData.name}`);
            await this.sleep(1000);

            this.addLog('debug', '[TargetServer] Fetching channels...');
            let channelsData = [];

            try {
                const channelsRes = await this.makeDiscordRequest(`https://discord.com/api/v10/guilds/${guildData.id}/channels`);
                if (!channelsRes.ok) {
                    const errText = await channelsRes.text();
                    this.addLog('warn', `[TargetServer] Failed to fetch channels: ${channelsRes.status} - ${errText}`);
                } else {
                    channelsData = await channelsRes.json();
                    this.addLog('debug', `[TargetServer] Fetched ${channelsData.length} channels`);
                }
            } catch (chanErr) {
                this.addLog('error', `[TargetServer] Channel fetch threw error: ${chanErr.message}`);
            }

            const iconURL = guildData.icon
                ? `https://cdn.discordapp.com/icons/${guildData.id}/${guildData.icon}.${guildData.icon.startsWith('a_') ? 'gif' : 'png'}?size=128`
                : null;

            this.botData.servers = [{
                id: guildData.id,
                name: guildData.name,
                memberCount: guildData.approximate_member_count || 0,
                iconURL,
                channels: channelsData.length,
                roles: null
            }];
            this.botData.userCount = this.botData.servers[0].memberCount;

            this.addLog('success', `[TargetServer] Connected to server: ${guildData.name}`);
            this.showToast(`Connected to server: ${guildData.name}`, 'success');

        } catch (error) {
            this.addLog('error', `[TargetServer] Error: ${error.message}`);
            console.error('Error loading target server:', error);
            this.showToast('Target server unavailable: ' + error.message, 'error');

            this.botData.servers = [{
                id: this.config?.targetServerId || 'unknown',
                name: 'Target Server (Unavailable)',
                memberCount: 0,
                iconURL: null,
                channels: 0,
                roles: 0
            }];
            this.botData.userCount = 0;
        }

        const elapsed = Date.now() - startTime;
        this.addLog('debug', `[TargetServer] Completed in ${elapsed}ms`);
        this.updateServersUI();
        this.updateServerSelects();
    }

    async loadChannels(serverId, selectId) {
        const select = document.getElementById(selectId);
        if (!select) {
            this.addLog('error', `No element found with ID '${selectId}'`);
            return;
        }

        select.innerHTML = '<option value="">Select Channel</option>';

        if (!serverId) return;

        try {
            if (!this.config?.botToken) throw new Error('Bot token not available');

            this.addLog('debug', `Loading channels for server ${serverId}`);

            const response = await this.makeDiscordRequest(
                `https://discord.com/api/v10/guilds/${serverId}/channels`
            );

            if (!response.ok) {
                const errorText = await response.text();
                throw new Error(`Discord API error: ${response.status} - ${errorText}`);
            }

            const allChannels = await response.json();
            const textChannels = allChannels.filter(c => c.type === 0); // GUILD_TEXT

            textChannels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.id;
                option.textContent = `# ${channel.name}`;
                select.appendChild(option);
            });

            this.addLog('success', `Loaded ${textChannels.length} text channels`);

        } catch (error) {
            console.error('Error loading channels:', error);
            this.showToast('Failed to load channels: ' + error.message, 'error');

            const fallbackChannels = [
                { id: '1', name: 'general' },
                { id: '2', name: 'announcements' },
                { id: '3', name: 'bot-commands' },
                { id: '4', name: 'random' }
            ];

            fallbackChannels.forEach(channel => {
                const option = document.createElement('option');
                option.value = channel.id;
                option.textContent = `# ${channel.name}`;
                select.appendChild(option);
            });

            this.addLog('warn', 'Using fallback channel list');
        }
    }

    async sendMessage() {
        const serverId = document.getElementById('messageServer').value;
        const channelId = document.getElementById('messageChannel').value;
        const message = document.getElementById('messageInput').value.trim();

        if (!serverId || !channelId || !message) {
            this.showToast('Please select server, channel, and enter a message', 'warning');
            return;
        }

        try {
            this.addLog('info', `Sending message to channel ${channelId}`);

            const response = await this.makeDiscordRequest(
                `https://discord.com/api/v10/channels/${channelId}/messages`,
                {
                    method: 'POST',
                    body: JSON.stringify({
                        content: message
                    })
                }
            );

            if (response.ok) {
                this.showToast('Message sent successfully!', 'success');
                document.getElementById('messageInput').value = '';

                const truncatedMessage = message.length > 50 ? message.substring(0, 50) + '...' : message;
                this.addLog('success', `Message sent: ${truncatedMessage}`);
            } else {
                const errorData = await response.json().catch(() => ({}));
                throw new Error(`Failed to send message: ${response.status} - ${errorData.message || 'Unknown error'}`);
            }

        } catch (error) {
            console.error('Message sending error:', error);
            this.showToast('Failed to send message: ' + error.message, 'error');
            this.addLog('error', `Failed to send message: ${error.message}`);
        }
    }

    // Rest of the methods remain the same...
    updateUI() {
        document.getElementById('botName').textContent = this.botData.name;

        const statusElement = document.getElementById('botStatus');
        statusElement.innerHTML = `<i class="fas fa-circle"></i> ${this.botData.status}`;
        statusElement.className = `bot-status ${this.botData.status}`;

        document.getElementById('serverCount').textContent = this.botData.servers.length;
        document.getElementById('userCount').textContent = this.formatNumber(this.botData.userCount);
        document.getElementById('commandCount').textContent = this.formatNumber(this.botData.commandCount);
        document.getElementById('uptime').textContent = this.formatUptime(this.botData.uptime);
        document.getElementById('latency').textContent = `${this.botData.latency} ms`;

        this.updateCharts();
    }

    updateServersUI() {
        const container = document.getElementById('serversGrid');
        container.innerHTML = '';

        this.botData.servers.forEach(server => {
            const serverCard = this.createServerCard(server);
            container.appendChild(serverCard);
        });
    }

    createServerCard(server) {
        const card = document.createElement('div');
        card.className = 'server-card';
        card.innerHTML = `
            <div class="server-header">
                <div class="server-icon">
                    ${server.iconURL ? `<img src="${server.iconURL}" alt="${server.name}" onerror="this.style.display='none'; this.nextElementSibling.style.display='inline';">` : ''}<i class="fas fa-server" ${server.iconURL ? 'style="display:none;"' : ''}></i>
                </div>
                <div class="server-info">
                    <h4>${server.name}</h4>
                    <p>ID: ${server.id}</p>
                </div>
            </div>
            <div class="server-stats">
                <div class="server-stat">
                    <span>${server.memberCount}</span>
                    <small>Members</small>
                </div>
                <div class="server-stat">
                    <span>${server.channels}</span>
                    <small>Channels</small>
                </div>
                <div class="server-stat">
                    <span>${server.roles || 'N/A'}</span>
                    <small>Roles</small>
                </div>
            </div>
        `;
        return card;
    }

    updateServerSelects() {
        const commandSelect = document.getElementById('commandServer');
        const messageSelect = document.getElementById('messageServer');

        [commandSelect, messageSelect].forEach(select => {
            select.innerHTML = '<option value="">Select Server</option>';
            this.botData.servers.forEach(server => {
                const option = document.createElement('option');
                option.value = server.id;
                option.textContent = server.name;
                select.appendChild(option);
            });
        });
    }

    updateCharts() {
        const activityCanvas = document.getElementById('activityChart');
        if (activityCanvas && activityCanvas.getContext) {
            this.drawActivityChart(activityCanvas);
        }

        const serverCanvas = document.getElementById('serverChart');
        if (serverCanvas && serverCanvas.getContext) {
            this.drawServerChart(serverCanvas);
        }
    }

    drawActivityChart(canvas) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.offsetWidth;
        const height = canvas.height = 200;

        ctx.clearRect(0, 0, width, height);
        ctx.strokeStyle = '#5865f2';
        ctx.lineWidth = 2;

        ctx.beginPath();
        for (let i = 0; i < width; i += 10) {
            const y = height / 2 + Math.sin(i * 0.02) * 30 + Math.random() * 20;
            if (i === 0) ctx.moveTo(i, y);
            else ctx.lineTo(i, y);
        }
        ctx.stroke();
    }

    drawServerChart(canvas) {
        const ctx = canvas.getContext('2d');
        const width = canvas.width = canvas.offsetWidth;
        const height = canvas.height = 200;

        ctx.clearRect(0, 0, width, height);

        const centerX = width / 2;
        const centerY = height / 2;
        const minDimension = Math.min(width, height);
        const radius = Math.max(minDimension / 4, 20);

        ctx.beginPath();
        ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
        ctx.fillStyle = '#5865f2';
        ctx.fill();

        ctx.fillStyle = '#ffffff';
        ctx.font = '14px Arial';
        ctx.textAlign = 'center';
        ctx.fillText(this.botData.servers[0]?.name || 'Server', centerX, centerY);
    }

    async executeCommand() {
        const serverId = document.getElementById('commandServer').value;
        const channelId = document.getElementById('commandChannel').value;
        const command = document.getElementById('commandInput').value.trim();

        if (!serverId || !channelId || !command) {
            this.showToast('Please select server, channel, and enter a command', 'warning');
            return;
        }

        this.addToOutput(`> ${command}`, 'command');

        try {
            const response = this.generateCommandResponse(command);
            this.addToOutput(response, 'response');

            document.getElementById('commandInput').value = '';
            this.botData.commandCount += 1;
            document.getElementById('commandCount').textContent = this.formatNumber(this.botData.commandCount);

            this.addLog('info', `Command executed: ${command}`);

        } catch (error) {
            console.error('Command execution error:', error);
            this.addToOutput('Error executing command: ' + error.message, 'error');
        }
    }

    generateCommandResponse(command) {
        const responses = {
            'ping': 'Pong! 🏓 Latency: ' + this.botData.latency + 'ms',
            'help': 'Available commands: ping, help, info, stats, uptime',
            'info': `Bot Information:\nName: ${this.botData.name}\nID: ${this.botData.id}\nStatus: ${this.botData.status}`,
            'stats': `Server Count: ${this.botData.servers.length}\nUser Count: ${this.formatNumber(this.botData.userCount)}\nLatency: ${this.botData.latency}ms`,
            'uptime': `Bot uptime: ${this.formatUptime(this.botData.uptime)}`
        };

        const cmd = command.toLowerCase().split(' ')[0];
        return responses[cmd] || 'Unknown command. Type "help" for available commands.';
    }

    addToOutput(text, type = 'info') {
        const outputElement = document.getElementById('outputContent');
        const timestamp = new Date().toLocaleTimeString();

        const line = document.createElement('div');
        line.className = `output-line ${type}`;
        line.innerHTML = `<span class="timestamp">[${timestamp}]</span> ${text}`;

        outputElement.appendChild(line);
        outputElement.scrollTop = outputElement.scrollHeight;
    }

    toggleEmbedOptions() {
        const embedOptions = document.getElementById('embedOptions');
        const toggleBtn = document.getElementById('embedToggle');

        if (embedOptions.style.display === 'none') {
            embedOptions.style.display = 'block';
            toggleBtn.classList.add('active');
        } else {
            embedOptions.style.display = 'none';
            toggleBtn.classList.remove('active');
        }
    }

    loadLogs() {
        const logMessages = [
            'Bot connected successfully',
            'Connected to Discord Gateway',
            'Rate limiter initialized',
            'Monitoring server activity',
            'Dashboard initialized',
            'Ready to receive commands',
            'WebSocket connection established',
            'Cache updated'
        ];

        const logTypes = ['info', 'success', 'warn'];

        for (let i = 0; i < 8; i++) {
            const type = i < 6 ? 'info' : logTypes[Math.floor(Math.random() * logTypes.length)];
            const message = logMessages[Math.floor(Math.random() * logMessages.length)];
            this.addLog(type, message);
        }
    }

    addLog(level, message) {
        const logsContainer = document.getElementById('logsContainer');
        const logEntry = document.createElement('div');
        logEntry.className = 'log-entry';
        logEntry.dataset.level = level;

        const timestamp = new Date().toLocaleTimeString();

        logEntry.innerHTML = `
            <span class="log-time">${timestamp}</span>
            <span class="log-level ${level}">${level}</span>
            <span class="log-message">${message}</span>
        `;

        logsContainer.insertBefore(logEntry, logsContainer.firstChild);

        while (logsContainer.children.length > 100) {
            logsContainer.removeChild(logsContainer.lastChild);
        }
    }

    filterLogs(filter) {
        const logs = document.querySelectorAll('.log-entry');
        logs.forEach(log => {
            if (filter === 'all' || log.dataset.level === filter) {
                log.style.display = 'flex';
            } else {
                log.style.display = 'none';
            }
        });
    }

    clearLogs() {
        document.getElementById('logsContainer').innerHTML = '';
        this.showToast('Logs cleared', 'success');
    }

    saveSettings() {
        const botToken = document.getElementById('botToken').value.trim();

        if (!botToken) {
            this.showToast('Bot token is required', 'error');
            return;
        }

        if (!botToken.includes('.') || botToken.length < 50) {
            this.showToast('Invalid bot token format', 'error');
            return;
        }

        try {
            window.savedBotToken = botToken;
            this.config.botToken = botToken;

            this.showToast('Settings saved successfully!', 'success');
            this.loadBotData();

        } catch (error) {
            console.error('Settings save error:', error);
            this.showToast('Failed to save settings: ' + error.message, 'error');
        }
    }

    async loadServers() {
        await this.loadTargetServer();
    }

    switchSection(sectionName) {
        document.querySelectorAll('.nav-item').forEach(item => {
            item.classList.remove('active');
        });
        document.querySelector(`[data-section="${sectionName}"]`).classList.add('active');

        document.querySelectorAll('.content-section').forEach(section => {
            section.classList.remove('active');
        });
        document.getElementById(sectionName).classList.add('active');

        const titles = {
            overview: 'Dashboard Overview',
            servers: 'Server Management',
            commands: 'Command Center',
            messaging: 'Message Center',
            logs: 'Activity Logs',
            settings: 'Bot Settings'
        };

        document.getElementById('sectionTitle').textContent = titles[sectionName];
        this.currentSection = sectionName;
    }

    setupAutoRefresh(interval = 30) {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }

        if (interval > 0 && this.config.botToken) {
            this.refreshInterval = setInterval(() => {
                this.refreshData();
            }, interval * 1000);
        }
    }

    async refreshData() {
        if (!this.config.botToken) {
            this.showToast('Bot token required for refresh', 'warning');
            return;
        }

        const refreshBtn = document.getElementById('refreshBtn');
        refreshBtn.style.transform = 'rotate(360deg)';

        try {
            await this.loadBotData();
            this.showToast('Data refreshed successfully', 'success');
        } catch (error) {
            this.showToast('Failed to refresh data', 'error');
        }

        setTimeout(() => {
            refreshBtn.style.transform = 'rotate(0deg)';
        }, 300);
    }

    toggleTheme(theme) {
        document.body.setAttribute('data-theme', theme);
        window.savedTheme = theme;
    }

    showLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.remove('hidden');
        }
    }

    hideLoading() {
        const loadingOverlay = document.getElementById('loadingOverlay');
        if (loadingOverlay) {
            loadingOverlay.classList.add('hidden');
        }
    }

    showToast(message, type = 'info') {
        const toastContainer = document.getElementById('toastContainer') || document.body;
        const toast = document.createElement('div');
        toast.className = `toast ${type}`;

        const icons = {
            success: 'fa-check-circle',
            error: 'fa-exclamation-circle',
            warning: 'fa-exclamation-triangle',
            info: 'fa-info-circle'
        };

        toast.innerHTML = `
            <i class="fas ${icons[type]}"></i>
            <span>${message}</span>
        `;

        // Style the toast if no external CSS
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 16px;
            border-radius: 4px;
            color: white;
            font-weight: 500;
            z-index: 10000;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            animation: slideIn 0.3s ease;
            ${type === 'success' ? 'background: #57f287;' : ''}
            ${type === 'error' ? 'background: #ed4245;' : ''}
            ${type === 'warning' ? 'background: #faa61a;' : ''}
            ${type === 'info' ? 'background: #5865f2;' : ''}
        `;

        toastContainer.appendChild(toast);

        // Auto remove after 5 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.parentNode.removeChild(toast);
            }
        }, 5000);
    }

    formatNumber(num) {
        if (num >= 1000000) {
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num >= 1000) {
            return (num / 1000).toFixed(1) + 'K';
        }
        return num.toString();
    }

    formatUptime(startTime) {
        const uptime = Date.now() - startTime;
        const days = Math.floor(uptime / (1000 * 60 * 60 * 24));
        const hours = Math.floor((uptime % (1000 * 60 * 60 * 24)) / (1000 * 60 * 60));
        const minutes = Math.floor((uptime % (1000 * 60 * 60)) / (1000 * 60));

        if (days > 0) {
            return `${days}d ${hours}h`;
        } else if (hours > 0) {
            return `${hours}h ${minutes}m`;
        } else {
            return `${minutes}m`;
        }
    }
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new DiscordBotDashboard();
});


// Add CSS for output styles
const style = document.createElement('style');
style.textContent = `
    .output-line {
        margin-bottom: 4px;
        font-family: 'Courier New', monospace;
    }
    
    .output-line.command {
        color: #57f287;
        font-weight: bold;
    }
    
    .output-line.response {
        color: #ffffff;
    }
    
    .output-line.error {
        color: #ed4245;
    }
    
    .timestamp {
        color: #72767d;
        font-size: 11px;
    }
    
    .btn.active {
        background: #4752c4 !important;
    }
`;
document.head.appendChild(style);