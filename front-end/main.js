const API_KEY = 'MeQQY8QcUP9gyX2L2IELl3kyUJYFUsZ6mw0dTjPi';
const API_BASE_URL = 'https://59l6vq12c4.execute-api.us-east-1.amazonaws.com/v1';

// Initialize the API Gateway SDK Client
let apigClient = null;
try {
  apigClient = apigClientFactory.newClient({
    apiKey: API_KEY
  });
} catch (e) {
  console.warn("Could not initialize apigClient, using direct fetch fallback", e);
}

// Elements
const searchInput = document.getElementById('searchInput');
const searchBtn = document.getElementById('searchBtn');
const searchSpinner = document.getElementById('searchSpinner');
const micBtn = document.getElementById('micBtn');
const galleryContainer = document.getElementById('galleryContainer');
const resultsCount = document.getElementById('resultsCount');
const uploadForm = document.getElementById('uploadForm');
const fileInput = document.getElementById('fileInput');
const customLabelsInput = document.getElementById('customLabelsInput');
const uploadBtn = document.getElementById('uploadBtn');
const uploadSpinner = document.getElementById('uploadSpinner');
const uploadAlert = document.getElementById('uploadAlert');

// Search Function
async function performSearch(query) {
  if (!query || !query.trim()) return;
  query = query.trim();

  searchSpinner.classList.remove('d-none');
  searchBtn.disabled = true;

  try {
    let photos = [];
    if (apigClient && typeof apigClient.searchGet === 'function') {
      const params = { q: query };
      const additionalParams = {
        headers: {
          'x-api-key': API_KEY
        }
      };
      const response = await apigClient.searchGet(params, {}, additionalParams);
      photos = (response.data && response.data.results) ? response.data.results : (Array.isArray(response.data) ? response.data : []);
    } else {
      // Fallback direct fetch
      const resp = await fetch(`${API_BASE_URL}/search?q=${encodeURIComponent(query)}`, {
        headers: { 'x-api-key': API_KEY }
      });
      const data = await resp.json();
      photos = data.results || (Array.isArray(data) ? data : []);
    }

    renderGallery(photos, query);
  } catch (err) {
    console.error("Search error: ", err);
    galleryContainer.innerHTML = `
      <div class="col-12 text-center text-danger py-4">
        <i class="bi bi-exclamation-triangle fs-3 d-block mb-2"></i>
        Search request failed. Please check the console logs.
      </div>
    `;
    resultsCount.textContent = '0 photos';
  } finally {
    searchSpinner.classList.add('d-none');
    searchBtn.disabled = false;
  }
}

// Render Gallery
function renderGallery(photos, query) {
  galleryContainer.innerHTML = '';
  resultsCount.textContent = `${photos.length} photos`;

  if (!photos || photos.length === 0) {
    galleryContainer.innerHTML = `
      <div class="col-12 text-center text-muted py-5">
        <i class="bi bi-emoji-neutral fs-2 d-block mb-2"></i>
        No photos found matching "<strong>${escapeHtml(query)}</strong>".
      </div>
    `;
    return;
  }

  photos.forEach(item => {
    const url = typeof item === 'string' ? item : item.url;
    const labels = (item.labels && Array.isArray(item.labels)) ? item.labels : [];

    const col = document.createElement('div');
    col.className = 'col-md-4 col-sm-6';

    const badgesHtml = labels.map(l => `<span class="badge bg-light text-dark border tag-badge">${escapeHtml(l)}</span>`).join('');

    col.innerHTML = `
      <div class="card photo-card shadow-sm h-100">
        <a href="${url}" target="_blank">
          <img src="${url}" class="card-img-top photo-img" alt="Photo" loading="lazy" onerror="this.src='https://via.placeholder.com/300x220?text=Image+Load+Error'">
        </a>
        <div class="card-body p-3">
          <div class="d-flex flex-wrap">${badgesHtml || '<span class="text-muted small">No labels</span>'}</div>
        </div>
      </div>
    `;
    galleryContainer.appendChild(col);
  });
}

// Helper to escape HTML
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Upload Function
uploadForm.addEventListener('submit', async (e) => {
  e.preventDefault();
  const file = fileInput.files[0];
  if (!file) return;

  const customLabels = customLabelsInput.value.trim();
  uploadBtn.disabled = true;
  uploadSpinner.classList.remove('d-none');
  showAlert('', 'd-none');

  try {
    const cleanFileName = encodeURIComponent(file.name.replace(/[^a-zA-Z0-9._-]/g, '_'));
    const uploadUrl = `${API_BASE_URL}/photos/${cleanFileName}`;

    const headers = {
      'Content-Type': file.type || 'image/jpeg',
      'x-api-key': API_KEY
    };

    if (customLabels) {
      headers['x-amz-meta-customLabels'] = customLabels;
    }

    const response = await fetch(uploadUrl, {
      method: 'PUT',
      headers: headers,
      body: file
    });

    if (response.ok) {
      showAlert(`Photo "${cleanFileName}" uploaded successfully! Indexing in progress...`, 'alert-success');
      fileInput.value = '';
      customLabelsInput.value = '';

      // Auto search for uploaded custom label or trigger search after short delay
      if (customLabels) {
        const firstLabel = customLabels.split(',')[0].trim();
        setTimeout(() => {
          searchInput.value = firstLabel;
          performSearch(firstLabel);
        }, 3500);
      }
    } else {
      const errText = await response.text();
      showAlert(`Upload failed (${response.status}): ${errText || response.statusText}`, 'alert-danger');
    }
  } catch (err) {
    console.error("Upload error: ", err);
    showAlert(`Upload failed: ${err.message}. If CORS issue persists, please try refreshing the page.`, 'alert-danger');
  } finally {
    uploadBtn.disabled = false;
    uploadSpinner.classList.add('d-none');
  }
});

function showAlert(msg, typeClass) {
  uploadAlert.className = `alert mt-3 mb-0 py-2 small ${typeClass}`;
  uploadAlert.textContent = msg;
}

// Search Button and Enter key
searchBtn.addEventListener('click', () => performSearch(searchInput.value));
searchInput.addEventListener('keydown', (e) => {
  if (e.key === 'Enter') performSearch(searchInput.value);
});

// Suggestions click
document.querySelectorAll('.suggestion-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    searchInput.value = btn.textContent;
    performSearch(btn.textContent);
  });
});

// Voice Search (Web Speech API)
if ('webkitSpeechRecognition' in window || 'SpeechRecognition' in window) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  const recognition = new SpeechRecognition();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = 'en-US';

  micBtn.addEventListener('click', () => {
    recognition.start();
    micBtn.classList.add('btn-danger');
    micBtn.innerHTML = '<i class="bi bi-mic-mute-fill"></i>';
  });

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    searchInput.value = transcript;
    performSearch(transcript);
  };

  recognition.onend = () => {
    micBtn.classList.remove('btn-danger');
    micBtn.innerHTML = '<i class="bi bi-mic-fill"></i>';
  };
} else {
  micBtn.style.display = 'none';
}
