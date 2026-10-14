// ============================================================
// Модуль журнала полётов (страница journal.html)
// ============================================================

const Journal = (() => {
    let flights = [];
    let drones = [];
    const filters = { status: '', drone_id: '', date_from: '', date_to: '', search: '' };

    async function init() {
        await loadDrones();
        await loadFlights();
        bindFilters();
    }

    async function loadDrones() {
        try {
            const resp = await fetch('/api/drones');
            drones = await resp.json();
            const select = document.getElementById('filterDrone');
            if (select) {
                select.innerHTML = '<option value="">Все БВС</option>' +
                    drones.map(d => `<option value="${d.id}">${d.name}</option>`).join('');
            }
        } catch (e) { console.error(e); }
    }

    async function loadFlights() {
        const params = new URLSearchParams();
        Object.entries(filters).forEach(([k, v]) => { if (v) params.set(k, v); });

        try {
            const resp = await fetch(`/api/flights?${params}`);
            flights = await resp.json();
            renderTable();
        } catch (e) {
            console.error('Ошибка загрузки полётов:', e);
            document.getElementById('journalBody').innerHTML =
                '<tr><td colspan="9" class="text-center text-danger">Ошибка загрузки</td></tr>';
        }
    }

    function droneName(id) {
        const d = drones.find(x => x.id === id);
        return d ? d.name : id?.slice(0, 8) + '…';
    }

    function fmtDate(s) {
        if (!s) return '—';
        return new Date(s).toLocaleString('ru-RU');
    }

    function renderTable() {
        const tbody = document.getElementById('journalBody');
        if (!tbody) return;

        if (flights.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">Полёты не найдены</td></tr>';
            updateCounter(0);
            return;
        }

        tbody.innerHTML = flights.map(f => {
            const v = f.verification_result || {};
            const valid = v.is_valid;
            const badge = f.status || 'planned';
            const statusRu = {
                planned: 'Запланирован', approved: 'Одобрен',
                in_progress: 'В полёте', completed: 'Завершён',
                rejected: 'Отклонён', cancelled: 'Отменён'
            }[badge] || badge;

            return `
                <tr>
                    <td class="text-muted small">${f.id.slice(0, 8)}…</td>
                    <td>${droneName(f.drone_id)}</td>
                    <td><span class="flight-status ${badge}">${statusRu}</span></td>
                    <td>${fmtDate(f.scheduled_start)}</td>
                    <td>${fmtDate(f.scheduled_end)}</td>
                    <td>${fmtDate(f.actual_start)}</td>
                    <td>${fmtDate(f.actual_end)}</td>
                    <td>${valid
                        ? '<span class="badge bg-success">Пройдена</span>'
                        : '<span class="badge bg-danger">Конфликт</span>'}</td>
                    <td class="text-nowrap">
                        <button class="btn btn-sm btn-outline-primary"
                                onclick="Journal.showDetails('${f.id}')">Детали</button>
                        ${badge === 'approved' ? `
                            <button class="btn btn-sm btn-outline-success"
                                    onclick="Journal.startFlight('${f.id}')">▶ Начать</button>
                        ` : ''}
                    </td>
                </tr>
            `;
        }).join('');
        updateCounter(flights.length);
    }

    function updateCounter(n) {
        const el = document.getElementById('journalCounter');
        if (el) el.textContent = `Найдено: ${n}`;
    }

    function bindFilters() {
        document.getElementById('filterStatus')?.addEventListener('change', e => {
            filters.status = e.target.value; loadFlights();
        });
        document.getElementById('filterDrone')?.addEventListener('change', e => {
            filters.drone_id = e.target.value; loadFlights();
        });
        document.getElementById('filterDateFrom')?.addEventListener('change', e => {
            filters.date_from = e.target.value ? e.target.value + 'T00:00:00' : '';
            loadFlights();
        });
        document.getElementById('filterDateTo')?.addEventListener('change', e => {
            filters.date_to = e.target.value ? e.target.value + 'T23:59:59' : '';
            loadFlights();
        });

        let searchTimer = null;
        document.getElementById('filterSearch')?.addEventListener('input', e => {
            clearTimeout(searchTimer);
            searchTimer = setTimeout(() => {
                filters.search = e.target.value;
                loadFlights();
            }, 400);
        });

        document.getElementById('btnReset')?.addEventListener('click', () => {
            Object.keys(filters).forEach(k => filters[k] = '');
            document.querySelectorAll('.filter-input').forEach(el => el.value = '');
            loadFlights();
        });
    }

    async function startFlight(flightId) {
        if (!confirm('Начать полёт? Дрон начнёт движение по маршруту в реальном времени.')) return;

        try {
            const resp = await fetch(`/api/flights/${flightId}/status`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status: 'in_progress' })
            });
            if (!resp.ok) {
                alert('Ошибка запуска: ' + resp.status);
                return;
            }
            await loadFlights();
            if (confirm('✅ Полёт запущен. Перейти на карту мониторинга?')) {
                window.location.href = '/monitoring';
            }
        } catch (e) {
            alert('Ошибка сети: ' + e.message);
        }
    }

    async function showDetails(flightId) {
        try {
            const [fResp, lResp] = await Promise.all([
                fetch(`/api/flights/${flightId}`),
                fetch(`/api/flights/${flightId}/logs`)
            ]);
            const flight = await fResp.json();
            const logs = await lResp.json();

            const v = flight.verification_result || {};
            const conflicts = (v.conflicts || []).map(c =>
                `<li class="text-${c.severity === 'critical' ? 'danger' : 'warning'}">${c.message}</li>`
            ).join('') || '<li class="text-muted">Нет</li>';

            const logHtml = logs.map(l => `
                <div class="event-item ${l.event_type}">
                    <div><b>${new Date(l.timestamp).toLocaleString('ru-RU')}</b> · ${l.event_type}</div>
                    <div>${l.message}</div>
                </div>
            `).join('') || '<div class="text-muted">Событий нет</div>';

            document.getElementById('detailsBody').innerHTML = `
                <div class="row">
                    <div class="col-md-6">
                        <h6>Информация о полёте</h6>
                        <p><b>ID:</b> ${flight.id}</p>
                        <p><b>БВС:</b> ${droneName(flight.drone_id)}</p>
                        <p><b>Статус:</b> ${flight.status}</p>
                        <p><b>Запланировано:</b> ${fmtDate(flight.scheduled_start)} — ${fmtDate(flight.scheduled_end)}</p>
                        <p><b>Фактически:</b> ${fmtDate(flight.actual_start)} — ${fmtDate(flight.actual_end)}</p>
                        <p><b>Примечания:</b> ${flight.notes || '—'}</p>
                    </div>
                    <div class="col-md-6">
                        <h6>Результат верификации</h6>
                        <p>${v.is_valid
                            ? '<span class="badge bg-success">Маршрут безопасен</span>'
                            : '<span class="badge bg-danger">Обнаружены конфликты</span>'}</p>
                        <p>Проверено зон: ${v.total_zones_checked ?? '—'}</p>
                        <p>Критических конфликтов: ${v.critical_count ?? 0}</p>
                        <ul>${conflicts}</ul>
                    </div>
                </div>
                <hr>
                <h6>Журнал событий</h6>
                <div style="max-height:300px;overflow-y:auto;">${logHtml}</div>
            `;

            const modal = new bootstrap.Modal(document.getElementById('detailsModal'));
            modal.show();
        } catch (e) {
            console.error(e);
            alert('Не удалось загрузить детали');
        }
    }

    return { init, loadFlights, showDetails, startFlight, refresh: loadFlights };
})();