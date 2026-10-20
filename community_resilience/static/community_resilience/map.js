import * as L from 'leaflet';
import { maplibreGL } from 'https://unpkg.com/@maplibre/maplibre-gl-leaflet@0.1.4/dist/leaflet-maplibre-gl.mjs';

(() => {
    const philippinesCenter = [12.8797, 121.774];
    const mapStyle = 'https://tiles.openfreemap.org/styles/positron';
    const attribution = '&copy; <a href="https://openfreemap.org">OpenFreeMap</a> · <a href="https://www.openmaptiles.org/">© OpenMapTiles</a> · Data from <a href="https://www.openstreetmap.org/copyright">OpenStreetMap contributors</a>';
    const initializedMaps = new WeakMap();
    const colors = {
        task: '#347d63',
        resource: '#d19a31',
        need: '#c45d4e',
    };
    const markerKinds = {
        task: 'Task',
        resource: 'Resource',
        need: 'Community need',
    };

    function createMap(element, center, zoom) {
        const map = L.map(element, {scrollWheelZoom: false}).setView(center, zoom);
        maplibreGL({
            style: mapStyle,
            attributionControl: false,
        }).addTo(map);
        map.attributionControl.setPrefix(false);
        map.attributionControl.addAttribution(attribution);
        requestAnimationFrame(() => map.invalidateSize());
        initializedMaps.set(element, map);
        return map;
    }

    function addDashboardMarkers(map) {
        const markerData = JSON.parse(document.getElementById('community-map-markers').textContent);
        const dialog = document.getElementById('activity-dialog');
        const dialogKind = document.getElementById('activity-dialog-kind');
        const dialogTitle = document.getElementById('activity-dialog-title');
        const dialogDetails = document.getElementById('activity-dialog-details');
        const dialogMapLink = document.getElementById('activity-dialog-map-link');
        const closeDialog = dialog.querySelector('[data-close-activity-dialog]');
        closeDialog.addEventListener('click', () => dialog.close());

        const formatTimestamp = (value) => {
            if (!value) {
                return '';
            }
            const date = new Date(value);
            return Number.isNaN(date.getTime())
                ? value
                : date.toLocaleDateString(undefined, {dateStyle: 'medium'});
        };
        const showActivityDetails = (item) => {
            const latitude = Number(item.latitude);
            const longitude = Number(item.longitude);
            dialogKind.textContent = markerKinds[item.kind] || 'Community activity';
            dialogTitle.textContent = item.title;
            dialogDetails.replaceChildren();
            dialogMapLink.href = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(`${latitude},${longitude}`)}`;
            dialogMapLink.setAttribute('aria-label', `Open ${item.title} in Google Maps (opens in a new tab)`);

            const rows = [
                {label: 'Posted by', value: item.posted_by || 'Not recorded'},
                {label: 'Role', value: item.posted_by_role || 'Not available'},
            ];
            const timestamp = formatTimestamp(item.timestamp);
            if (timestamp) {
                rows.push({label: item.timestamp_label || 'Posted', value: timestamp});
            }
            rows.push(...item.details);

            rows.forEach((row) => {
                const term = document.createElement('dt');
                term.textContent = row.label;
                const description = document.createElement('dd');
                description.textContent = row.value;
                dialogDetails.append(term, description);
            });
            dialog.showModal();
        };

        const bounds = [];
        markerData.forEach((item) => {
            const latitude = Number(item.latitude);
            const longitude = Number(item.longitude);
            if (!Number.isFinite(latitude) || !Number.isFinite(longitude)) {
                return;
            }

            const point = [latitude, longitude];
            bounds.push(point);
            const marker = L.circleMarker(point, {
                color: '#fff',
                fillColor: colors[item.kind] || colors.task,
                fillOpacity: 1,
                opacity: 1,
                radius: 8,
                weight: 2,
            }).addTo(map);
            marker.on('click', () => showActivityDetails(item));
        });

        const count = document.getElementById('map-record-count');
        count.textContent = markerData.length === 1 ? '1 mapped location' : `${markerData.length} mapped locations`;
        if (bounds.length) {
            map.fitBounds(bounds, {padding: [32, 32], maxZoom: 13});
        }
    }

    function addLocationPicker(map) {
        const latitudeInput = document.getElementById('id_latitude');
        const longitudeInput = document.getElementById('id_longitude');
        const status = document.getElementById('map-selection-status');
        const clearButton = document.getElementById('clear-map-location');
        let pin;

        const updatePosition = (point) => {
            const latitude = point.lat.toFixed(6);
            const longitude = point.lng.toFixed(6);
            latitudeInput.value = latitude;
            longitudeInput.value = longitude;
            status.textContent = `Pinned at ${latitude}, ${longitude}`;
        };
        const placePin = (point) => {
            if (pin) {
                pin.setLatLng(point);
            } else {
                pin = L.marker(point, {draggable: true}).addTo(map);
                pin.on('dragend', (event) => updatePosition(event.target.getLatLng()));
            }
            updatePosition(point);
        };

        const initialLatitude = Number(latitudeInput.value);
        const initialLongitude = Number(longitudeInput.value);
        if (latitudeInput.value && longitudeInput.value
            && Number.isFinite(initialLatitude) && Number.isFinite(initialLongitude)) {
            placePin(L.latLng(initialLatitude, initialLongitude));
            map.setView([initialLatitude, initialLongitude], 15);
        }

        map.on('click', (event) => placePin(event.latlng));
        clearButton.addEventListener('click', () => {
            if (pin) {
                map.removeLayer(pin);
                pin = undefined;
            }
            latitudeInput.value = '';
            longitudeInput.value = '';
            status.textContent = 'No map pin selected.';
        });
    }

    window.initializeCommunityLocationPicker = (element) => {
        const latitudeInput = element.querySelector('#id_latitude');
        const longitudeInput = element.querySelector('#id_longitude');
        const hasPosition = latitudeInput.value && longitudeInput.value;
        const center = hasPosition
            ? [Number(latitudeInput.value), Number(longitudeInput.value)]
            : philippinesCenter;
        const map = createMap(element.querySelector('#location-picker-map'), center, hasPosition ? 15 : 6);
        addLocationPicker(map);
    };

    window.destroyCommunityLocationPicker = (element) => {
        const mapElement = element.querySelector('#location-picker-map');
        const map = mapElement && initializedMaps.get(mapElement);
        if (map) {
            map.remove();
            initializedMaps.delete(mapElement);
        }
    };

    const dashboardElement = document.getElementById('community-map');
    if (dashboardElement) {
        const map = createMap(dashboardElement, philippinesCenter, 6);
        addDashboardMarkers(map);
    }

    const pickerElement = document.getElementById('location-picker-map');
    if (pickerElement && !pickerElement.closest('dialog')) {
        const mapContainer = pickerElement.closest('.panel') || pickerElement.parentElement;
        window.initializeCommunityLocationPicker(mapContainer);
    }

    const detailElement = document.getElementById('need-detail-map');
    if (detailElement) {
        const latitude = Number(detailElement.dataset.latitude);
        const longitude = Number(detailElement.dataset.longitude);
        const map = createMap(detailElement, [latitude, longitude], 15);
        const popup = document.createElement('div');
        popup.className = 'map-popup';
        const title = document.createElement('strong');
        title.textContent = detailElement.dataset.title;
        popup.append(title);
        L.marker([latitude, longitude]).addTo(map).bindPopup(popup).openPopup();
        map.setView([latitude, longitude], 15);
    }
})();
