// ============================================================
// Модуль планирования маршрута на карте (страница index.html)
// ============================================================

const PlannerMap = (() => {
    const state = {
        map: null,
        waypoints: [],
        markers: [],
        routeLine: null,
        zonesLayer: null,
        dronesLayer: null,
    };

    const ZONE_STYLE = {
        permanent: { color: '#dc3545', fillColor: '#dc3545', fillOpacity: 0.15, weight: 2 },
        temporary: { color: '#fd7e14', fillColor: '#fd7e14', fillOpacity: 0.15, weight: 2 },
        reserved:  { color: '#6f42c1', fillColor: '#6f42c1', fillOpacity: 0.15, weight: 2 },
    };

    function init(containerId = 'map') {
        state.map = L.map(containerId).setView([55.7558, 37.6173], 10);

        L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
            attribution: '© OpenStreetMap',
            maxZoom: 19,
        }).addTo(state.map);

        state.zonesLayer = L.layerGroup().addTo(state.map);
        state.dronesLayer = L.layerGroup().addTo(state.map);

        state.map.on('click', (e) => addWaypoint(e.latlng.lat, e.latlng.lng));
        loadZones();
        loadDrones();
        return state.map;
    }

    // ---------- Путевые точки ----------
    function addWaypoint(lat, lon) {
        const alt = parseFloat(document.getElementById('altitude')?.value || 100);
        const wp = { lat: +lat.toFixed(6), lon: +lon.toFixed(6), alt };

        const icon = L.divIcon({
            className: '',
            html: `<div style="background:#0d6efd;color:white;width:24px;height:24px;
                              border-radius:50%;display:flex;align-items:center;
                              justify-content:center;font-weight:600;
                              border:2px solid white;box-shadow:0 0 4px rgba(0,0,0,0.3);
                              font-size:12px;">${state.waypoints.length + 1}</div>`,
            iconSize: [24, 24],
            iconAnchor: [12, 12],
        });

        const marker = L.marker([lat, lon], { draggable: true, icon }).addTo(state.map);
        marker.on('dragend', () => {
            const pos = marker.getLatLng();
            const idx = state.markers.indexOf(marker);
            if (idx >= 0) {
                state.waypoints[idx].lat = +pos.lat.toFixed(6);
                state.waypoints[idx].lon = +pos.lng.toFixed(6);
                redrawRoute();
            }
        });

        state.markers.push(marker);
        state.waypoints.push(wp);
        redrawRoute();
        renderWaypointsList();
    }

    function removeWaypoint(index) {
        state.map.removeLayer(state.markers[index]);
        state.markers.splice(index, 1);
        state.waypoints.splice(index, 1);
        redrawRoute();
        renderWaypointsList();
    }

    function clearAll() {
        state.markers.forEach(m => state.map.removeLayer(m));
        state.markers = [];
        state.waypoints = [];
        if (state.routeLine) {
            state.map.removeLayer(state.routeLine);
            state.routeLine = null;
        }
        renderWaypointsList();
    }

    function redrawRoute() {
        if (state.routeLine) state.map.removeLayer(state.routeLine);
        if (state.waypoints.length >= 2) {
            const coords = state.waypoints.map(wp => [wp.lat, wp.lon]);
            state.routeLine = L.polyline(coords, {
                color: '#0d6efd', weight: 3, opacity: 0.8,
                dashArray: '8,6'
            }).addTo(state.map);
        }
    }

    function renderWaypointsList() {
        const list = document.getElementById('waypointsList');
        if (!list) return;
        if (state.waypoints.length === 0) {
            list.innerHTML = '<small class="text-muted">Кликайте по карте для добавления точек</small>';
            return;
        }
        list.innerHTML = state.waypoints.map((wp, i) => `
            <div class="waypoint-item">
                <span><b>${i + 1}.</b> ${wp.lat}, ${wp.lon} · ${wp.alt} м</span>
                <button class="btn btn-sm btn-outline-danger py-0 px-2"
                        onclick="PlannerMap.removeWaypoint(${i})">×</button>
            </div>
        `).join('');
    }

    // ---------- Зоны ограничения ----------
    async function loadZones() {
        try {
            const resp = await fetch('/api/zones/geojson');
            const data = await resp.json();
            state.zonesLayer.clearLayers();

            L.geoJSON(data, {
                style: (feature) => ZONE_STYLE[feature.properties.zone_type] || ZONE_STYLE.temporary,
                onEachFeature: (feature, layer) => {
                    const p = feature.properties;
                    layer.bindPopup(`
                        <b>${p.name}</b><br>
                        Тип: ${p.zone_type}<br>
                        Высоты: ${p.lower_limit_m}–${p.upper_limit_m} м
                        ${p.description ? `<br><small>${p.description}</small>` : ''}
                    `);
                }
            }).addTo(state.zonesLayer);
        } catch (err) {
            console.error('Ошибка загрузки зон:', err);
        }
    }

    // ---------- БВС ----------
    async function loadDrones() {
        try {
            const resp = await fetch('/api/drones');
            const drones = await resp.json();
            state.dronesLayer.clearLayers();

            drones.forEach(d => {
                if (d.last_lat == null || d.last_lon == null) return;
                const color = d.status === 'in_flight' ? '#198754'
                            : d.status === 'maintenance' ? '#ffc107'
                            : '#6c757d';
                L.circleMarker([d.last_lat, d.last_lon], {
                    radius: 7, color, fillColor: color, fillOpacity: 0.8, weight: 2
                })
                .bindPopup(`<b>${d.name}</b><br>Статус: ${d.status}`)
                .addTo(state.dronesLayer);
            });
        } catch (err) {
            console.error('Ошибка загрузки БВС:', err);
        }
    }

    // ---------- Заполнение select дронов ----------
    async function loadDronesForSelect() {
        const select = document.getElementById('droneSelect');
        const hint = document.getElementById('droneHint');
        if (!select) return;

        try {
            const resp = await fetch('/api/drones');
            const drones = await resp.json();

            const available = drones.filter(d => d.status !== 'maintenance');

            if (available.length === 0) {
                select.innerHTML = '<option value="">Нет доступных БВС</option>';
                if (hint) hint.textContent = 'Все БВС на обслуживании';
                return;
            }

            select.innerHTML =
                '<option value="">— выберите БВС —</option>' +
                available.map(d => {
                    const statusRu = {
                        idle: 'на базе',
                        in_flight: 'в полёте',
                        maintenance: 'обслуживание',
                    }[d.status] || d.status;
                    const busy = d.status === 'in_flight' ? ' ⚠' : '';
                    return `<option value="${d.id}">${d.name} — ${statusRu}${busy}</option>`;
                }).join('');

            if (hint) {
                hint.textContent = `Доступно БВС: ${available.length}`;
            }
        } catch (err) {
            console.error('Ошибка загрузки БВС:', err);
            select.innerHTML = '<option value="">Ошибка загрузки</option>';
        }
    }

    return {
        init,
        addWaypoint,
        removeWaypoint,
        clearAll,
        getWaypoints: () => [...state.waypoints],
        loadZones,
        loadDrones,
        loadDronesForSelect,
        getMap: () => state.map,
    };
})();