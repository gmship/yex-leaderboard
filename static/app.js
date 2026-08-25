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
const bidInput = document.querySelector('#bid-dollars');
const estimatedRank = document.querySelector('#estimated-rank');
const quickBidButtons = [...(form?.querySelectorAll('[data-bid]') || [])];
const faviconInput = form?.elements.favicon_url;
const outbidDialog = document.querySelector('#outbid-dialog');
const outbidForm = document.querySelector('#outbid-form');
const outbidError = document.querySelector('#outbid-error');
const outbidButton = document.querySelector('#outbid-checkout-button');
const outbidInput = document.querySelector('#outbid-dollars');
const outbidResult = document.querySelector('#outbid-result');
const outbidProjectName = document.querySelector('#outbid-project-name');
const outbidCurrentPosition = document.querySelector('#outbid-current-position');
const outbidQuickButtons = [...document.querySelectorAll('[data-outbid-amount]')];

const showError = (message) => {
  if (!formError) return;
  formError.textContent = message;
  formError.hidden = false;
};

const clearError = () => {
  if (!formError) return;
  formError.hidden = true;
  formError.textContent = '';
};

const setFetchStatus = (message, state = '') => {
  if (!fetchStatus) return;
  fetchStatus.textContent = message;
  fetchStatus.dataset.state = state;
};

const openSubmit = () => {
  clearError();
  form.reset();
  const baseMin = Number(bidInput.dataset.baseMin || 1);
  bidInput.min = String(baseMin);
  bidInput.value = String(baseMin);
  setFetchStatus('');
  updateBidPreview();
  dialog.showModal();
  window.setTimeout(() => {
    form.elements.url.focus();
    bidInput.value = String(baseMin);
    updateBidPreview();
  }, 80);
};

document.querySelectorAll('.js-open-submit').forEach((button) => {
  button.addEventListener('click', openSubmit);
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
    if (result.existing_slug) {
      dialog.close();
      openOutbid({
        projectSlug: result.existing_slug,
        projectName: result.existing_name || result.name || 'This listing',
        currentBidCents: String(result.existing_bid_cents || 0),
        currentRank: '',
      });
      return;
    }
    form.elements.name.value = result.name || '';
    faviconInput.value = result.favicon_url || '';
    setFetchStatus('Name added. Review or edit it below.', 'success');
    form.elements.name.focus();
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
});

function updateBidPreview() {
  if (!bidInput || !estimatedRank) return;
  const dollars = Math.max(Number(bidInput.value) || 1, Number(bidInput.min) || 1);
  const bidCents = dollars * 100;
  const rows = [...document.querySelectorAll('.project-row')];
  const position = 1 + rows.filter((row) => Number(row.dataset.bid) >= bidCents).length;
  estimatedRank.textContent = `Estimated starting position #${String(position).padStart(2, '0')}`;
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
  if (tools.length !== 1) {
    showError('Choose one main build tool.');
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
    if (response.status === 409 && result.code === 'existing_listing' && result.slug) {
      dialog.close();
      window.location.assign(`/product/${encodeURIComponent(result.slug)}`);
      return;
    }
    if (!response.ok) throw new Error(result.error || 'Checkout could not be started.');
    window.location.assign(result.url);
  } catch (error) {
    showError(error.message);
    checkoutButton.disabled = false;
    checkoutButton.textContent = originalLabel;
  }
});

const showOutbidError = (message) => {
  if (!outbidError) return;
  outbidError.textContent = message;
  outbidError.hidden = false;
};

const clearOutbidError = () => {
  if (!outbidError) return;
  outbidError.textContent = '';
  outbidError.hidden = true;
};

function updateOutbidPreview() {
  if (!outbidForm || !outbidInput || !outbidResult) return;
  const dollars = Math.max(Number(outbidInput.value) || 1, Number(outbidInput.min) || 1);
  const currentBidCents = Number(outbidForm.dataset.currentBidCents || 0);
  const newTotal = currentBidCents / 100 + dollars;
  const currentRank = outbidForm.dataset.currentRank;
  outbidResult.textContent = `Add $${dollars} → $${newTotal} total${currentRank ? ` · currently #${currentRank}` : ''}`;
  outbidQuickButtons.forEach((button) => {
    button.classList.toggle('is-active', Number(button.dataset.outbidAmount) === dollars);
  });
}

function openOutbid(source) {
  if (!outbidDialog || !outbidForm || !outbidInput) return;
  const data = source?.dataset || source || {};
  clearOutbidError();
  outbidForm.reset();
  outbidForm.dataset.projectSlug = data.projectSlug || '';
  outbidForm.dataset.currentBidCents = data.currentBidCents || '0';
  outbidForm.dataset.currentRank = data.currentRank || '';
  outbidProjectName.textContent = data.projectName || 'This listing';
  const currentDollars = Number(data.currentBidCents || 0) / 100;
  outbidCurrentPosition.textContent = `$${currentDollars} current bid${data.currentRank ? ` · rank #${data.currentRank}` : ''}`;
  outbidInput.value = outbidInput.dataset.baseMin || '1';
  updateOutbidPreview();
  outbidDialog.showModal();
  window.setTimeout(() => outbidInput.focus(), 80);
}

document.querySelectorAll('.js-open-outbid').forEach((button) => {
  button.addEventListener('click', () => openOutbid(button));
});

document.querySelector('#outbid-dialog-close')?.addEventListener('click', () => outbidDialog.close());
outbidDialog?.addEventListener('click', (event) => {
  if (event.target === outbidDialog) outbidDialog.close();
});
outbidInput?.addEventListener('input', updateOutbidPreview);
outbidQuickButtons.forEach((button) => {
  button.addEventListener('click', () => {
    outbidInput.value = button.dataset.outbidAmount;
    updateOutbidPreview();
  });
});

outbidForm?.addEventListener('submit', async (event) => {
  event.preventDefault();
  clearOutbidError();
  if (!outbidForm.reportValidity()) return;
  const slug = outbidForm.dataset.projectSlug;
  if (!slug) {
    showOutbidError('This listing is unavailable. Refresh the page and try again.');
    return;
  }
  const payload = Object.fromEntries(new FormData(outbidForm).entries());
  outbidButton.disabled = true;
  const originalLabel = outbidButton.textContent;
  outbidButton.textContent = 'Opening secure checkout…';
  try {
    const response = await fetch(`/api/outbid/${encodeURIComponent(slug)}`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.error || 'Checkout could not be started.');
    window.location.assign(result.url);
  } catch (error) {
    showOutbidError(error.message);
    outbidButton.disabled = false;
    outbidButton.textContent = originalLabel;
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

const copyDetailLink = document.querySelector('#copy-detail-link');
const copyDetailStatus = document.querySelector('#copy-detail-status');
const nativeShareButton = document.querySelector('#native-share');

const copyShareUrl = async (url) => {
  await navigator.clipboard.writeText(url);
  if (copyDetailStatus) copyDetailStatus.textContent = 'Link copied.';
};

copyDetailLink?.addEventListener('click', async () => {
  try {
    await copyShareUrl(copyDetailLink.dataset.copyUrl);
    copyDetailLink.textContent = 'Copied';
  } catch (_) {
    if (copyDetailStatus) copyDetailStatus.textContent = 'Copy failed. Use your browser address bar.';
  }
});

nativeShareButton?.addEventListener('click', async () => {
  const shareData = {
    title: nativeShareButton.dataset.shareTitle,
    text: nativeShareButton.dataset.shareText,
    url: nativeShareButton.dataset.shareUrl,
  };
  try {
    if (navigator.share) await navigator.share(shareData);
    else {
      await copyShareUrl(shareData.url);
      nativeShareButton.textContent = 'Copied';
    }
  } catch (error) {
    if (error.name !== 'AbortError' && copyDetailStatus) {
      copyDetailStatus.textContent = 'Sharing was unavailable. Try Copy link.';
    }
  }
});
