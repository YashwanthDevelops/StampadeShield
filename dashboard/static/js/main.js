/* ========================================
   STAMPEDE SHIELD - Dashboard JavaScript
   ======================================== */

// Configuration
const CONFIG = {
    refreshRate: 2000,  // 2 seconds
    apiEndpoint: '/api/data',
    soundEnabled: true,
    lastLevel: 'SAFE'
};

// DOM Elements
const elements = {
    // Header
    timestamp: document.getElementById('timestamp'),
    themeToggle: document.getElementById('themeToggle'),
    fullscreenBtn: document.getElementById('fullscreenBtn'),
    
    // Risk Card
    riskCard: document.getElementById('riskCard'),
    riskEmoji: document.getElementById('riskEmoji'),
    riskLevel: document.getElementById('riskLevel'),
    riskScore: document.getElementById('riskScore'),
    riskProgress: document.getElementById('riskProgress'),
    riskConfidence: document.getElementById('riskConfidence'),
    riskConfidenceBar: document.getElementById('riskConfidenceBar'),
    
    // CPI Card
    cpiValue: document.getElementById('cpiValue'),
    cpiConfidence: document.getElementById('cpiConfidence'),
    cpiConfidenceBar: document.getElementById('cpiConfidenceBar'),
    densityBar: document.getElementById('densityBar'),
    densityValue: document.getElementById('densityValue'),
    motionBar: document.getElementById('motionBar'),
    motionValue: document.getElementById('motionValue'),
    audioBar: document.getElementById('audioBar'),
    audioValue: document.getElementById('audioValue'),
    trendBar: document.getElementById('trendBar'),
    trendValue: document.getElementById('trendValue'),
    
    // Time Card
    timeToCritical: document.getElementById('timeToCritical'),
    
    // Node Status
    nodeAStatus: document.getElementById('nodeAStatus'),
    nodeBStatus: document.getElementById('nodeBStatus'),
    nodeCStatus: document.getElementById('nodeCStatus'),
    
    // Zones
    entryZone: document.getElementById('entryZone'),
    centerZone: document.getElementById('centerZone'),
    exitZone: document.getElementById('exitZone'),
    entryDist: document.getElementById('entryDist'),
    centerDist: document.getElementById('centerDist'),
    exitDist: document.getElementById('exitDist'),
    entryDensity: document.getElementById('entryDensity'),
    centerDensity: document.getElementById('centerDensity'),
    exitDensity: document.getElementById('exitDensity'),
    
    // Timeline
    timelineNow: document.getElementById('timelineNow'),
    timeline30: document.getElementById('timeline30'),
    timeline60: document.getElementById('timeline60'),
    timeline120: document.getElementById('timeline120'),
    
    // Audio
    audioLevel: document.getElementById('audioLevel'),
    audioState: document.getElementById('audioState'),
    audioBarFill: document.getElementById('audioBarFill'),
    
    // Actions
    actionsList: document.getElementById('actionsList'),
    
    // Factors
    factorsList: document.getElementById('factorsList'),
    
    // Alert Bar
    alertBar: document.getElementById('alertBar'),
    recommendation: document.getElementById('recommendation'),
    
    // Sound
    alertSound: document.getElementById('alertSound')
};

// Level configurations
const LEVELS = {
    'SAFE': { emoji: '🟢', color: 'safe' },
    'LOW': { emoji: '🟡', color: 'low' },
    'MODERATE': { emoji: '🟠', color: 'moderate' },
    'HIGH': { emoji: '🔴', color: 'high' },
    'CRITICAL': { emoji: '🚨', color: 'critical' }
};

// Status to class mapping
const STATUS_CLASS = {
    'GREEN': 'safe',
    'YELLOW': 'low',
    'ORANGE': 'moderate',
    'RED': 'high',
    'BLACK': 'critical'
};

/* ========================================
   THEME TOGGLE
   ======================================== */

function initTheme() {
    const savedTheme = localStorage.getItem('theme') || 'dark';
    document.body.classList.remove('dark', 'light');
    document.body.classList.add(savedTheme);
    elements.themeToggle.textContent = savedTheme === 'dark' ? '🌙' : '☀️';
}

elements.themeToggle.addEventListener('click', () => {
    const isDark = document.body.classList.contains('dark');
    document.body.classList.remove('dark', 'light');
    document.body.classList.add(isDark ? 'light' : 'dark');
    elements.themeToggle.textContent = isDark ? '☀️' : '🌙';
    localStorage.setItem('theme', isDark ? 'light' : 'dark');
});

/* ========================================
   FULLSCREEN TOGGLE
   ======================================== */

elements.fullscreenBtn.addEventListener('click', () => {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
        document.body.classList.add('fullscreen');
    } else {
        document.exitFullscreen();
        document.body.classList.remove('fullscreen');
    }
});

/* ========================================
   DATA FETCHING
   ======================================== */

async function fetchData() {
    try {
        const response = await fetch(CONFIG.apiEndpoint);
        if (!response.ok) throw new Error('Network error');
        const data = await response.json();
        updateDashboard(data);
    } catch (error) {
        console.error('Fetch error:', error);
    }
}

/* ========================================
   UPDATE DASHBOARD
   ======================================== */

function updateDashboard(data) {
    // Update timestamp
    elements.timestamp.textContent = data.timestamp;
    
    // Update Risk Card
    updateRiskCard(data.risk);
    
    // Update CPI Card
    updateCPICard(data.cpi);
    
    // Update Time to Critical
    updateTimeToCritical(data.time_to_critical);
    
    // Update Node Status
    updateNodeStatus(data.nodes);
    
    // Update Zones
    updateZones(data.zones);
    
    // Update Timeline
    updateTimeline(data.timeline);
    
    // Update Audio
    updateAudio(data.audio);
    
    // Update Actions
    updateActions(data.actions);
    
    // Update Factors
    updateFactors(data.factors);
    
    // Update Alert Bar
    updateAlertBar(data.risk.level, data.recommendation);
    
    // Handle sound alert
    handleSoundAlert(data.risk.level);
    
    // Handle emergency mode
    handleEmergencyMode(data.risk.level);
}

/* ========================================
   UPDATE FUNCTIONS
   ======================================== */

function updateRiskCard(risk) {
    const level = risk.level;
    const config = LEVELS[level] || LEVELS['SAFE'];
    
    elements.riskEmoji.textContent = config.emoji;
    elements.riskLevel.textContent = level;
    elements.riskScore.textContent = risk.score;
    elements.riskProgress.style.width = `${risk.score}%`;
    elements.riskConfidence.textContent = risk.confidence;
    elements.riskConfidenceBar.style.width = `${risk.confidence}%`;
    
    // Update progress bar color
    elements.riskProgress.style.background = getColorForLevel(level);
    
    // Update card class
    elements.riskCard.className = `card risk-card ${config.color}`;
}

function updateCPICard(cpi) {
    elements.cpiValue.textContent = cpi.value.toFixed(1);
    elements.cpiConfidence.textContent = cpi.confidence;
    elements.cpiConfidenceBar.style.width = `${cpi.confidence}%`;
    
    if (cpi.breakdown) {
        const b = cpi.breakdown;
        
        elements.densityBar.style.width = `${b.density || 0}%`;
        elements.densityValue.textContent = `${(b.density || 0).toFixed(0)}%`;
        
        elements.motionBar.style.width = `${b.motion || 0}%`;
        elements.motionValue.textContent = `${(b.motion || 0).toFixed(0)}%`;
        
        elements.audioBar.style.width = `${b.audio || 0}%`;
        elements.audioValue.textContent = `${(b.audio || 0).toFixed(0)}%`;
        
        elements.trendBar.style.width = `${b.trend || 0}%`;
        elements.trendValue.textContent = `${(b.trend || 0).toFixed(0)}%`;
    }
}

function updateTimeToCritical(time) {
    if (time === null || time === undefined) {
        elements.timeToCritical.textContent = '--';
    } else if (time === 0) {
        elements.timeToCritical.textContent = 'NOW!';
    } else {
        elements.timeToCritical.textContent = `${time}s`;
    }
}

function updateNodeStatus(nodes) {
    elements.nodeAStatus.textContent = nodes.NODE_A.online ? '🟢' : '🔴';
    elements.nodeBStatus.textContent = nodes.NODE_B.online ? '🟢' : '🔴';
    elements.nodeCStatus.textContent = nodes.NODE_C.online ? '🟢' : '🔴';
}

function updateZones(zones) {
    // Entry Zone
    const entryClass = STATUS_CLASS[zones.ENTRY.status] || 'safe';
    elements.entryZone.className = `zone ${entryClass}`;
    elements.entryDist.textContent = zones.ENTRY.distance.toFixed(1);
    elements.entryDensity.textContent = zones.ENTRY.density.toFixed(1);
    
    // Center Zone
    const centerClass = STATUS_CLASS[zones.CENTER.status] || 'safe';
    elements.centerZone.className = `zone ${centerClass}`;
    elements.centerDist.textContent = zones.CENTER.distance.toFixed(1);
    elements.centerDensity.textContent = zones.CENTER.density.toFixed(1);
    
    // Exit Zone
    const exitClass = STATUS_CLASS[zones.EXIT.status] || 'safe';
    elements.exitZone.className = `zone ${exitClass}`;
    elements.exitDist.textContent = zones.EXIT.distance.toFixed(1);
    elements.exitDensity.textContent = zones.EXIT.density.toFixed(1);
}

function updateTimeline(timeline) {
    updateTimelineBox(elements.timelineNow, timeline.now);
    updateTimelineBox(elements.timeline30, timeline['30s']);
    updateTimelineBox(elements.timeline60, timeline['60s']);
    updateTimelineBox(elements.timeline120, timeline['120s']);
}

function updateTimelineBox(element, level) {
    const config = LEVELS[level] || LEVELS['SAFE'];
    element.textContent = level.substring(0, 4);
    element.className = `timeline-box ${config.color}`;
}

function updateAudio(audio) {
    elements.audioLevel.textContent = audio.level;
    elements.audioState.textContent = audio.state;
    elements.audioState.className = `audio-state ${audio.state.toLowerCase()}`;
    
    // Audio bar (max 1000)
    const percentage = Math.min(100, (audio.level / 1000) * 100);
    elements.audioBarFill.style.width = `${percentage}%`;
}

function updateActions(actions) {
    const priorityEmojis = ['1️⃣', '2️⃣', '3️⃣', '4️⃣', '5️⃣'];
    
    elements.actionsList.innerHTML = actions.map((action, index) => `
        <div class="action-item">
            <span class="action-priority">${priorityEmojis[index] || '▪️'}</span>
            <div class="action-content">
                <div class="action-text">${action.action}</div>
                <div class="action-reason">${action.reason}</div>
            </div>
        </div>
    `).join('');
}

function updateFactors(factors) {
    elements.factorsList.innerHTML = factors.map(factor => 
        `<li>${factor}</li>`
    ).join('');
}

function updateAlertBar(level, recommendation) {
    elements.recommendation.textContent = recommendation;
    
    elements.alertBar.classList.remove('high', 'critical');
    
    if (level === 'HIGH') {
        elements.alertBar.classList.add('high');
    } else if (level === 'CRITICAL') {
        elements.alertBar.classList.add('critical');
    }
}

/* ========================================
   HELPER FUNCTIONS
   ======================================== */

function getColorForLevel(level) {
    const colors = {
        'SAFE': '#22c55e',
        'LOW': '#eab308',
        'MODERATE': '#f97316',
        'HIGH': '#ef4444',
        'CRITICAL': '#dc2626'
    };
    return colors[level] || colors['SAFE'];
}

/* ========================================
   SOUND ALERT
   ======================================== */

function handleSoundAlert(level) {
    // Play sound only on transition to CRITICAL
    if (level === 'CRITICAL' && CONFIG.lastLevel !== 'CRITICAL') {
        if (CONFIG.soundEnabled && elements.alertSound) {
            elements.alertSound.play().catch(e => console.log('Audio play failed:', e));
        }
    }
    CONFIG.lastLevel = level;
}

/* ========================================
   EMERGENCY MODE
   ======================================== */

function handleEmergencyMode(level) {
    if (level === 'CRITICAL') {
        document.body.classList.add('emergency');
    } else {
        document.body.classList.remove('emergency');
    }
}

/* ========================================
   INITIALIZATION
   ======================================== */

function init() {
    console.log('🚨 Stampede Shield Dashboard Initializing...');
    
    // Initialize theme
    initTheme();
    
    // Fetch data immediately
    fetchData();
    
    // Set up refresh interval
    setInterval(fetchData, CONFIG.refreshRate);
    
    console.log('✅ Dashboard Ready');
}

// Start when DOM is loaded
document.addEventListener('DOMContentLoaded', init);