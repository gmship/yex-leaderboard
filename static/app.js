const dialog = document.querySelector('#submit-dialog');
const form = document.querySelector('#submission-form');
const formError = document.querySelector('#form-error');
const checkoutButton = document.querySelector('#checkout-button');
const projectList = document.querySelector('#project-list');
const noResults = document.querySelector('#no-results');
const sortSelect = document.querySelector('#sort-projects');
const onlineCount = document.querySelector('#online-count');
const totalVisits = document.querySelector('#total-visits');
const fetchDetailsButton = document.querySelector('#fetch-details');
const fetchStatus = document.querySelector('#fetch-status');
const connectXButton = document.querySelector('#connect-x');
const connectXStatus = document.querySelector('#x-connect-status');
const bidInput = document.querySelector('#bid-dollars');
const estimatedRank = document.querySelector('#estimated-rank');
const quickBidButtons = [...document.querySelectorAll('[data-bid]')];
const faviconInput = form?.elements.favicon_url;

const showError = (message) => {
  formError.textContent = message;
  formError.hidden = false;
};

const clearError = () => {
  formError.hidden = true;
  formError.textContent = '';
};

const setFetchStatus = (message, state = '') => {
  if (!fetchStatus) return;
  fetchStatus.textContent = message;
  fetchStatus.dataset.state = state;
};

const openSubmit = (trigger) => {
  clearError();
  const data = trigger?.dataset || {};
  form.reset();
  form.dataset.existingBidCents = '0';
  const baseMin = Number(bidInput.dataset.baseMin || 1);
  const initialBid = Math.max(Number(data.nextBid || baseMin), baseMin);
  bidInput.min = String(data.nextBid || baseMin);
  bidInput.value = String(initialBid);
  quickBidButtons.forEach((button) => {
    button.disabled = Number(button.dataset.bid) < Number(bidInput.min);
  });
  setFetchStatus('');
  if (connectXStatus) connectXStatus.textContent = 'Your X username will appear here after connecting.';
  if (connectXButton) connectXButton.textContent = 'Connect 𝕏';
  updateBidPreview();
  dialog.showModal();
  window.setTimeout(() => {
    form.elements.url.focus();
    bidInput.value = String(initialBid);
    updateBidPreview();
  }, 80);
};

document.querySelectorAll('.js-open-submit').forEach((button) => {
  button.addEventListener('click', () => openSubmit(button));
});

document.querySelector('#dialog-close')?.addEventListener('click', () => dialog.close());
dialog?.addEventListener('click', (event) => {
  if (event.target === dialog) dialog.close();
});

const fetchSiteDetails = async () => {
  const urlInput = form?.elements.url;
  if (!urlInput || !urlInput.reportValidity()) return;
  clearError();
  fetchDetailsButton.disabled = true;
  fetchDetailsButton.textContent = 'Fetching…';
  setFetchStatus('Reading the public page…', 'loading');
  try {
    const response = await fetch('/api/site-preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ url: urlInput.value }),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Site details could not be fetched.');
    form.elements.name.value = result.name || '';
    form.elements.tagline.value = result.description || '';
    faviconInput.value = result.favicon_url || '';
    form.dataset.existingBidCents = String(result.existing_bid_cents || 0);
    setFetchStatus('Details added. Review or edit them below.', 'success');
    (result.name ? form.elements.name : form.elements.tagline).focus();
  } catch (error) {
    setFetchStatus(error.message, 'error');
  } finally {
    fetchDetailsButton.disabled = false;
    fetchDetailsButton.textContent = 'Fetch details';
  }
};

fetchDetailsButton?.addEventListener('click', fetchSiteDetails);
form?.elements.url?.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    fetchSiteDetails();
  }
});
form?.elements.url?.addEventListener('input', () => {
  faviconInput.value = '';
  form.dataset.existingBidCents = '0';
});

connectXButton?.addEventListener('click', () => {
  connectXStatus.textContent = 'X connection is coming soon. This button is ready for the OAuth flow.';
  connectXButton.textContent = 'X · Coming soon';
});

function updateBidPreview() {
  if (!bidInput || !estimatedRank) return;
  const dollars = Math.max(Number(bidInput.value) || 1, Number(bidInput.min) || 1);
  const bidCents = dollars * 100;
  const existingBidCents = Number(form.dataset.existingBidCents || 0);
  const resultingBidCents = bidCents + existingBidCents;
  const rows = [...document.querySelectorAll('.project-row')];
  const position = 1 + rows.filter((row) => Number(row.dataset.bid) >= resultingBidCents).length;
  estimatedRank.textContent = existingBidCents
    ? `Add $${dollars} → $${resultingBidCents / 100} total · estimated #${String(position).padStart(2, '0')}`
    : `Estimated starting position #${String(position).padStart(2, '0')}`;
  quickBidButtons.forEach((button) => {
    button.classList.toggle('is-active', Number(button.dataset.bid) === dollars);
  });
}

bidInput?.addEventListener('input', updateBidPreview);
quickBidButtons.forEach((button) => {
  button.addEventListener('click', () => {
    bidInput.value = button.dataset.bid;
    updateBidPreview();
  });
});

form?.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearError();

  const categories = [...form.querySelectorAll('input[name="categories"]:checked')].map((input) => input.value);
  const tools = [...form.querySelectorAll('input[name="built_with"]:checked')].map((input) => input.value);
  if (!form.reportValidity()) return;
  if (categories.length === 0) {
    showError('Choose at least one category.');
    return;
  }
  if (categories.length > 2) {
    showError('Choose no more than two categories.');
    return;
  }
  if (tools.length === 0) {
    showError('Choose at least one AI tool.');
    return;
  }
  if (tools.length > 5) {
    showError('Choose no more than five AI tools.');
    return;
  }

  const payload = Object.fromEntries(new FormData(form).entries());
  payload.categories = categories;
  payload.built_with = tools;
  checkoutButton.disabled = true;
  const originalLabel = checkoutButton.textContent;
  checkoutButton.textContent = 'Opening secure checkout…';

  try {
    const response = await fetch('/api/checkout', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Checkout could not be started.');
    window.location.assign(result.url);
  } catch (error) {
    showError(error.message);
    checkoutButton.disabled = false;
    checkoutButton.textContent = originalLabel;
  }
});

const applyBoardView = () => {
  if (!projectList) return;
  const rows = [...projectList.querySelectorAll('.project-row')];
  const pageOffset = Number(projectList.dataset.pageOffset || 0);
  const sortBy = sortSelect?.value || 'bid';
  rows.sort((a, b) => {
    if (sortBy === 'fastest') return Number(a.dataset.minutes) - Number(b.dataset.minutes);
    if (sortBy === 'newest') return b.dataset.created.localeCompare(a.dataset.created);
    return Number(b.dataset.bid) - Number(a.dataset.bid);
  });
  projectList.querySelector('.top-ten-divider')?.remove();
  rows.forEach((row, index) => {
    const absoluteRank = pageOffset + index + 1;
    const rank = row.querySelector('.rank-number');
    if (rank) rank.textContent = `#${String(absoluteRank).padStart(2, '0')}`;
    row.classList.remove('project-row--top', 'project-row--top-1', 'project-row--top-2', 'project-row--top-3');
    if (absoluteRank <= 3) row.classList.add('project-row--top', `project-row--top-${absoluteRank}`);
    projectList.appendChild(row);
    if (absoluteRank === 10 && index < rows.length - 1) {
      const divider = document.createElement('div');
      divider.className = 'top-ten-divider';
      divider.innerHTML = '<span>Top 10</span><em>More builds</em>';
      projectList.appendChild(divider);
    }
  });
  if (noResults) noResults.hidden = rows.length !== 0;
};

sortSelect?.addEventListener('change', applyBoardView);

form?.querySelectorAll('input[name="categories"]').forEach((input) => {
  input.addEventListener('change', () => {
    const selected = form.querySelectorAll('input[name="categories"]:checked');
    if (selected.length > 2) {
      input.checked = false;
      showError('Choose no more than two categories.');
    }
  });
});

const refreshPresence = async () => {
  if (!onlineCount || !totalVisits || document.hidden) return;
  try {
    const response = await fetch('/api/presence', { method: 'POST' });
    if (!response.ok) return;
    const traffic = await response.json();
    onlineCount.textContent = Number(traffic.online || 0).toLocaleString('en-US');
    totalVisits.textContent = Number(traffic.total_visits || 0).toLocaleString('en-US');
  } catch (_) {
    // Keep the server-rendered values when a heartbeat cannot be delivered.
  }
};

window.setInterval(refreshPresence, 60_000);
document.addEventListener('visibilitychange', refreshPresence);

document.querySelectorAll('.project-favicon').forEach((image) => {
  const hideFailedImage = () => { image.hidden = true; };
  if (image.complete && image.naturalWidth === 0) hideFailedImage();
  image.addEventListener('error', hideFailedImage);
});

document.querySelectorAll('a[data-click-slug]').forEach((link) => {
  link.addEventListener('click', () => {
    const endpoint = `/api/click/${encodeURIComponent(link.dataset.clickSlug)}`;
    if (navigator.sendBeacon) navigator.sendBeacon(endpoint);
    else fetch(endpoint, { method: 'POST', keepalive: true }).catch(() => {});
  });
});
