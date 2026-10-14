// ============================================================
// Модуль мониторинга парка БВС (страница monitoring.html)
// ============================================================

const Monitoring = (() => {
    let map = null;
    let ws = null;
    let droneMarkers = {};   // drone_id → L.marker
    let routeLines = {};
    let reconnectTimer = null;

    function init(mapContainerId = 'monitoringMap') {
        map = L.map(mapContainerId).setView([55.7558, 37.6173], 10);
        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap'
        }).addTo(map);

        loadZones();
        loadInitialState();
        connectWebSocket();
        setInterval(refreshStatus, 5000);
    }

    // ---------- Загрузка зон ----------
    async function loadZones() {
        try {
            const resp = await fetch('/api/zones/geojson');
            const data = await resp.json();
            L.geoJSON(data, {
                style: () => ({
                    color: '#dc3545', fillColor: '#dc3545',
                    fillOpacity: 0.12, weight: 2
                })
            }).addTo(map);
        } catch (e) { console.error(e); }
    }

    // ---------- Начальные данные ----------
    async function loadInitialState() {
        try {
            const resp = await fetch('/api/monitoring/live');
            const drones = await resp.json();
            drones.forEach(updateDronePosition);
        } catch (e) { console.error(e); }
    }

    // ---------- WebSocket ----------
    function connectWebSocket() {
        const proto = location.protocol === 'https:' ? 'wss' : 'ws';
        const url = `${proto}://${location.host}/ws/monitoring`;

        ws = new WebSocket(url);

        ws.onopen = () => {
            setWsStatus('connected', 'WebSocket: подключён');
            if (reconnectTimer) { clearTimeout(reconnectTimer); reconnectTimer = null; }
            // Периодический ping, чтобы сервер отправлял телеметрию
            setInterval(() => {
                if (ws.readyState === WebSocket.OPEN) ws.send('ping');
            }, 5000);
        };

        ws.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);
                if (msg.type === 'telemetry' && Array.isArray(msg.data)) {
                    msg.data.forEach(updateDronePosition);
                } else if (msg.type === 'event') {
                    appendEvent(msg.data);
                }
            } catch (err) {
                console.error('Ошибка WebSocket:', err);
            }
        };

        ws.onclose = () => {
            setWsStatus('disconnected', 'WebSocket: отключён');
            scheduleReconnect();
        };

        ws.onerror = () => {
            setWsStatus('disconnected', 'WebSocket: ошибка');
        };
    }

    function scheduleReconnect() {
        if (reconnectTimer) return;
        reconnectTimer = setTimeout(() => {
            reconnectTimer = null;
            connectWebSocket();
        }, 3000);
    }

    function setWsStatus(cls, text) {
        const el = document.getElementById('wsStatus');
        if (!el) return;
        el.className = cls;
        el.textContent = text;
    }

    // ---------- Обновление позиции БВС ----------
    function updateDronePosition(d) {
        if (d.lat == null || d.lon == null) return;

        const pos = [d.lat, d.lon];
        const popup = `
            <b>${d.drone_name || d.drone_id}</b><br>
            Координаты: ${d.lat.toFixed(5)}, ${d.lon.toFixed(5)}<br>
            Высота: ${d.altitude ?? '—'} м<br>
            Статус: ${d.flight_status || '—'}
        `;

        if (droneMarkers[d.drone_id]) {
            droneMarkers[d.drone_id].setLatLng(pos);
            droneMarkers[d.drone_id].setPopupContent(popup);
        } else {
            const marker = L.circleMarker(pos, {
                radius: 8, color: '#0d6efd', fillColor: '#0d6efd',
                fillOpacity: 0.8, weight: 2
            }).bindPopup(popup).addTo(map);
            droneMarkers[d.drone_id] = marker;
        }
    }

    // ---------- Панель статуса ----------
    async function refreshStatus() {
        try {
            const resp = await fetch('/api/monitoring/status');
            const s = await resp.json();

            setText('statTotal', s.total_drones ?? 0);
            setText('statInFlight', s.by_status?.in_flight ?? 0);
            setText('statIdle', s.by_status?.idle ?? 0);
            setText('statMaintenance', s.by_status?.maintenance ?? 0);
            setText('statActiveFlights', s.active_flights_count ?? 0);
        } catch (e) { console.error(e); }
    }

    function setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    // ---------- Лента событий ----------
    async function refreshEvents() {
        try {
            const resp = await fetch('/api/monitoring/events?limit=30&minutes=120');
            const events = await resp.json();
            const container = document.getElementById('eventsFeed');
            if (!container) return;
            container.innerHTML = events.map(e => `
                <div class="event-item ${e.event_type}">
                    <div><b>${new Date(e.timestamp).toLocaleTimeString()}</b> · ${e.event_type}</div>
                    <div>${e.message}</div>
                </div>
            `).join('') || '<div class="text-muted">Событий пока нет</div>';
        } catch (e) { console.error(e); }
    }

    function appendEvent(evt) {
        const container = document.getElementById('eventsFeed');
        if (!container) return;
        const div = document.createElement('div');
        div.className = `event-item ${evt.event_type || ''}`;
        div.innerHTML = `<div><b>${new Date().toLocaleTimeString()}</b> · ${evt.event_type}</div>
                         <div>${evt.message}</div>`;
        container.prepend(div);
        while (container.children.length > 50) container.removeChild(container.lastChild);
    }

    return { init, refreshStatus, refreshEvents, updateDronePosition };
})();