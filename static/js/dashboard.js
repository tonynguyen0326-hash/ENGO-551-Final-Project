// 1. Initialize Map
const map = L.map('map', {
    zoomControl: false
}).setView([51.0782, -114.1305], 15);

L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    attribution: '© OpenStreetMap'
}).addTo(map);

let markerLayer = L.layerGroup().addTo(map);

// 2. Form Logic
const filterForm = document.getElementById('filter-form');
const checkOnCampus = document.getElementById('check-on-campus');
const checkOffCampus = document.getElementById('check-off-campus');
const onCampusTypes = document.getElementById('on-campus-types');
const offCampusTypes = document.getElementById('off-campus-types');
const clearBtn = document.getElementById('clear-filters');

// Toggle sub-menus
function toggleTypeVisibility() {
    if (onCampusTypes) onCampusTypes.style.display = checkOnCampus.checked ? 'block' : 'none';
    if (offCampusTypes) offCampusTypes.style.display = checkOffCampus.checked ? 'block' : 'none';
}

if (checkOnCampus) checkOnCampus.addEventListener('change', toggleTypeVisibility);
if (checkOffCampus) checkOffCampus.addEventListener('change', toggleTypeVisibility);

// Apply Filters
filterForm.addEventListener('submit', function(e) {
    e.preventDefault();
    const userLocation = map.getCenter(); 
    const formData = new FormData(this);
    const params = new URLSearchParams(formData);
    
    params.append('lat', userLocation.lat);
    params.append('lng', userLocation.lng);
    params.set('on-campus', checkOnCampus.checked);
    params.set('off-campus', checkOffCampus.checked);

    fetch(`/api/search?${params.toString()}`)
        .then(res => res.json())
        .then(data => renderMarkers(data))
        .catch(err => console.error("Search error:", err));
});

// Clear Filters
clearBtn.addEventListener('click', function() {
    filterForm.reset();
    toggleTypeVisibility();
    markerLayer.clearLayers();
    map.setView([51.0782, -114.1305], 15);
});

// 3. User Location
map.on('locationfound', (e) => {
    L.marker(e.latlng).addTo(map).bindPopup("You are here").openPopup();
    L.circle(e.latlng, e.accuracy / 2).addTo(map);
    map.setView(e.latlng, 16);
});

map.locate({setView: true, maxZoom: 16});

// 4. Rendering Logic
function renderMarkers(data) {
    markerLayer.clearLayers(); 

    if (data.length === 0) {
        alert("No spots found with these filters.");
        return;
    }

    data.forEach(spot => {
        const safeName = spot.name.replace(/[^a-z0-9]/gi, '-');
        const summaryId = `summary-${safeName}`;

        let popupContent = `
            <div style="min-width: 200px;">
                <h3 style="margin:0 0 5px 0;">${spot.name}</h3>
                <span style="background:#eee; padding:2px 5px; border-radius:3px; font-size:0.8em;">${spot.type}</span>
                
                <div id="${summaryId}" style="margin-top: 10px;">
                    <button onclick="fetchSummary('${spot.name.replace(/'/g, "\\'")}', '${summaryId}')" 
                            style="background: #007bff; color: white; border: none; padding: 5px 10px; border-radius: 4px; cursor: pointer; font-size: 0.8em;">
                        Generate AI Summary ✨
                    </button>
                </div>

                ${spot.tip ? `
                    <hr style="margin: 10px 0;">
                    <p style="font-style: italic; font-size: 0.9em;">"${spot.tip}"</p>
                    <div style="text-align: right; color: #ff4500; font-weight: bold; font-size: 0.75em;">via ${spot.source}</div>
                ` : ''}
            </div>
        `;

        L.marker([spot.lat, spot.lon])
            .bindPopup(popupContent, { maxWidth: 300 })
            .addTo(markerLayer);
    });

    const bounds = L.latLngBounds(data.map(d => [d.lat, d.lon]));
    map.fitBounds(bounds, { padding: [50, 50] });
}

// 5. Global Summary Function (Attached to window so onclick works)
window.fetchSummary = function(locationName, containerId) {
    const container = document.getElementById(containerId);
    container.innerHTML = `<span style="font-size:0.8em; color:#666;">🤖 AI Analyzing...</span>`;

    fetch(`/api/summarize/${encodeURIComponent(locationName)}`)
        .then(res => res.json())
        .then(data => {
            container.innerHTML = `
                <div style="background: #f8f9fa; border-left: 3px solid #007bff; padding: 8px; font-size: 0.85em;">
                    <strong>AI Verdict:</strong> ${data.summary}
                </div>`;
        })
        .catch(() => {
            container.innerHTML = `<span style="color:red; font-size:0.8em;">Summary unavailable.</span>`;
        });
};