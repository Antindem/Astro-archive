/* ════════════════════════════════════════════════════════
   ASTRO ARCHIVE — Application Logic
   ════════════════════════════════════════════════════════ */

(function() {
  'use strict';

  // ── State ────────────────────────────────────────────
  let allPosts = [];
  let taxonomy = [];
  let filteredPosts = [];
  let currentView = 'grid'; // 'grid' | 'tiktok'
  let activeFilter = null;  // { category, subcategory } or null
  let searchQuery = '';
  let tiktokOrder = [];
  let lightboxImages = [];
  let lightboxIndex = 0;

  // ── DOM refs ─────────────────────────────────────────
  const $ = (sel, ctx) => (ctx || document).querySelector(sel);
  const $$ = (sel, ctx) => [...(ctx || document).querySelectorAll(sel)];

  // ── Init ─────────────────────────────────────────────
  async function init() {
    try {
      const res = await fetch('posts.json');
      const data = await res.json();
      allPosts = data.posts;
      taxonomy = data.taxonomy;

      // Sort posts newest first
      allPosts.sort((a, b) => (b.dateISO || '').localeCompare(a.dateISO || ''));

      renderSidebar();
      applyFilters();
      bindEvents();
      hideLoading();
    } catch (err) {
      console.error('Failed to load data', err);
      $('#main-content').innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">⚠️</div>
          <div class="empty-title">Ошибка загрузки</div>
          <div class="empty-desc">Не удалось загрузить данные. Убедитесь что posts.json существует.</div>
        </div>
      `;
    }
  }

  function hideLoading() {
    const l = $('.loading');
    if (l) l.remove();
  }

  // ── Sidebar ──────────────────────────────────────────
  function renderSidebar() {
    const container = $('#topic-list');
    if (!container) return;

    // Count posts per topic
    const counts = {};
    allPosts.forEach(p => {
      (p.topics || []).forEach(t => {
        const catKey = t.category;
        const subKey = `${t.category}/${t.subcategory}`;
        counts[catKey] = (counts[catKey] || 0) + 1;
        counts[subKey] = (counts[subKey] || 0) + 1;
      });
    });

    let html = '';
    taxonomy.forEach(cat => {
      const catCount = counts[cat.id] || 0;
      if (catCount === 0) return;

      html += `<div class="topic-category" data-cat="${cat.id}">
        <div class="topic-category-header" data-cat="${cat.id}">
          <span>${cat.label}</span>
          <span class="topic-count">${catCount}</span>
          <span class="topic-chevron">›</span>
        </div>
        <div class="topic-children">`;

      cat.children.forEach(sub => {
        const subCount = counts[`${cat.id}/${sub.id}`] || 0;
        if (subCount === 0) return;
        html += `<div class="topic-item" data-cat="${cat.id}" data-sub="${sub.id}">
          <span>${sub.label}</span>
          <span class="topic-count">${subCount}</span>
        </div>`;
      });

      html += `</div></div>`;
    });

    container.innerHTML = html;
  }

  // ── Filtering ────────────────────────────────────────
  function applyFilters() {
    let posts = allPosts;

    // Topic filter
    if (activeFilter) {
      posts = posts.filter(p =>
        (p.topics || []).some(t => {
          if (activeFilter.subcategory) {
            return t.category === activeFilter.category && t.subcategory === activeFilter.subcategory;
          }
          return t.category === activeFilter.category;
        })
      );
    }

    // Search
    if (searchQuery) {
      const q = searchQuery.toLowerCase();
      posts = posts.filter(p =>
        (p.text || '').toLowerCase().includes(q) ||
        (p.author || '').toLowerCase().includes(q)
      );
    }

    filteredPosts = posts;
    updatePostCount();

    if (currentView === 'grid') {
      renderGrid();
    } else {
      initTiktokFeed();
    }
  }

  function updatePostCount() {
    const el = $('#post-count-num');
    if (el) el.textContent = filteredPosts.length;
  }

  // ── Post Rendering Helpers ───────────────────────────
  function generateTopicBadges(post) {
    if (!post.topics || post.topics.length === 0) return '';
    const seen = new Set();
    let badges = '';
    post.topics.forEach(t => {
      const key = `${t.category}/${t.subcategory}`;
      if (!seen.has(key)) {
        seen.add(key);
        const label = getSubcategoryLabel(t.category, t.subcategory);
        badges += `<span class="topic-badge" data-cat="${t.category}" data-sub="${t.subcategory}">${label}</span>`;
      }
    });
    return badges;
  }

  function generateReactionsHtml(post, containerClass) {
    if (!post.reactions || post.reactions.length === 0) return '';
    let html = `<div class="${containerClass}">`;
    post.reactions.forEach(r => {
      html += `<span class="reaction-pill">
        <span>${r.emoji}</span>
        <span class="reaction-count">${r.count}</span>
      </span>`;
    });
    html += '</div>';
    return html;
  }

  // ── Grid Rendering ───────────────────────────────────
  function renderGrid() {
    const container = $('#posts-grid');
    if (!container) return;

    if (filteredPosts.length === 0) {
      container.innerHTML = `
        <div class="empty-state" style="grid-column: 1/-1">
          <div class="empty-icon">🔭</div>
          <div class="empty-title">Ничего не найдено</div>
          <div class="empty-desc">Попробуйте изменить поисковый запрос или снять фильтр</div>
        </div>
      `;
      return;
    }

    const fragment = document.createDocumentFragment();

    filteredPosts.forEach((post, i) => {
      const card = document.createElement('div');
      card.className = 'post-card';
      card.dataset.postIndex = allPosts.indexOf(post);
      card.style.animationDelay = `${Math.min(i * 0.04, 0.8)}s`;

      const numImages = post.images ? post.images.length : 0;
      const numVideos = post.videos ? post.videos.length : 0;
      const totalMedia = numImages + numVideos;

      let imageHtml = '';
      if (totalMedia > 0) {
        let thumbUrl = '';
        let isVideo = false;
        let duration = '';
        
        if (numVideos > 0) {
          thumbUrl = post.videos[0].thumb;
          isVideo = true;
          duration = post.videos[0].duration;
        } else {
          thumbUrl = post.images[0].thumb || post.images[0].full;
        }

        imageHtml = `
          <div class="${isVideo ? 'card-video-wrap' : 'card-image-wrap'}">
            <img src="${thumbUrl}" alt="" loading="lazy">
            ${isVideo ? `<div class="video-play-badge">▶</div>` : ''}
            ${isVideo && duration ? `<div class="video-duration-badge">${duration}</div>` : ''}
            ${totalMedia > 1 ? `<span class="image-count-badge">📷 ${totalMedia}</span>` : ''}
          </div>`;
      }

      const initial = (post.author || '?')[0].toUpperCase();
      const dateStr = formatDate(post.dateISO || post.date);
      const topicBadges = generateTopicBadges(post);
      const reactionsHtml = generateReactionsHtml(post, 'card-reactions');

      card.innerHTML = `
        ${imageHtml}
        <div class="card-body">
          <div class="card-meta">
            <div class="card-avatar">${initial}</div>
            <div>
              <div class="card-author">${escHtml(post.author)}</div>
              <div class="card-date">${dateStr}</div>
            </div>
          </div>
          ${topicBadges ? `<div class="card-topics">${topicBadges}</div>` : ''}
          <div class="card-text">${post.html || ''}</div>
          ${reactionsHtml}
        </div>
      `;

      fragment.appendChild(card);
    });

    container.innerHTML = '';
    container.appendChild(fragment);
  }

  // ── TikTok Feed ──────────────────────────────────────
  function initTiktokFeed() {
    const container = $('#tiktok-feed');
    if (!container) return;

    // Randomize order
    tiktokOrder = [...filteredPosts].sort(() => Math.random() - 0.5);

    if (tiktokOrder.length === 0) {
      container.innerHTML = `
        <div class="tiktok-slide">
          <div class="empty-state">
            <div class="empty-icon">🔭</div>
            <div class="empty-title">Нет публикаций</div>
            <div class="empty-desc">Снимите фильтр или измените поисковый запрос</div>
          </div>
        </div>`;
      return;
    }

    let html = '';
    tiktokOrder.forEach((post, i) => {
      const numImages = post.images ? post.images.length : 0;
      const numVideos = post.videos ? post.videos.length : 0;
      const totalMedia = numImages + numVideos;

      let imageHtml = '';
      if (totalMedia > 0) {
        if (numVideos > 0) {
          // Embed the video directly in tiktok feed
          // If there are multiple we just show the first one
          const v = post.videos[0];
          imageHtml = `
            <div class="tiktok-video-wrap" style="background:#000;">
              <video src="${v.src}" poster="${v.thumb}" controls ${v.type === 'gif' ? 'loop muted autoplay' : ''} style="width:100%; max-height: 400px; object-fit: contain;"></video>
            </div>`;
        } else {
          const full = post.images[0].full || post.images[0].thumb;
          imageHtml = `
            <div class="tiktok-image-wrap" data-post-index="${allPosts.indexOf(post)}" data-img-index="0">
              <img src="${full}" alt="" loading="lazy">
              ${totalMedia > 1 ? `<span class="image-count-badge">📷 ${totalMedia}</span>` : ''}
            </div>`;
        }
      }

      const initial = (post.author || '?')[0].toUpperCase();
      const dateStr = formatDate(post.dateISO || post.date);
      const reactionsHtml = generateReactionsHtml(post, 'tiktok-reactions');
      const topicBadges = generateTopicBadges(post);

      html += `
        <div class="tiktok-slide" data-index="${i}">
          <div class="tiktok-card">
            ${imageHtml}
            <div class="tiktok-body">
              <div class="tiktok-meta">
                <div class="tiktok-avatar">${initial}</div>
                <div>
                  <div class="tiktok-author">${escHtml(post.author)}</div>
                  <div class="tiktok-date">${dateStr}</div>
                </div>
              </div>
              <div class="tiktok-text">${post.html || ''}</div>
              ${reactionsHtml}
              ${topicBadges ? `<div class="tiktok-topics">${topicBadges}</div>` : ''}
            </div>
          </div>
        </div>`;
    });

    container.innerHTML = html;
    container.scrollTop = 0;
    updateTiktokCounter();
  }

  function updateTiktokCounter() {
    const counter = $('#tiktok-counter');
    if (!counter) return;
    const feed = $('#tiktok-feed');
    if (!feed) return;
    const slideH = feed.clientHeight;
    const idx = Math.round(feed.scrollTop / slideH);
    counter.textContent = `${idx + 1} / ${tiktokOrder.length}`;
  }

  // ── Post Detail Modal ────────────────────────────────
  function openPostModal(postIndex) {
    const post = allPosts[postIndex];
    if (!post) return;

    const modal = $('#post-modal');
    const content = $('#post-modal-content');
    
    const initial = (post.author || '?')[0].toUpperCase();
    const dateStr = formatDate(post.dateISO || post.date);
    const topicBadges = generateTopicBadges(post);
    const reactionsHtml = generateReactionsHtml(post, 'modal-reactions');

    // Generate media gallery
    let mediaHtml = '';
    if (post.videos && post.videos.length > 0) {
      post.videos.forEach(v => {
        mediaHtml += `
          <div class="modal-media-item">
            <video src="${v.src}" poster="${v.thumb}" controls ${v.type === 'gif' ? 'loop muted autoplay' : ''}></video>
          </div>
        `;
      });
    }
    if (post.images && post.images.length > 0) {
      post.images.forEach((img, idx) => {
        mediaHtml += `
          <div class="modal-media-item image-item" data-post-index="${postIndex}" data-img-index="${idx}">
            <img src="${img.full || img.thumb}" alt="">
          </div>
        `;
      });
    }

    content.innerHTML = `
      ${mediaHtml ? `<div class="modal-media-gallery">${mediaHtml}</div>` : ''}
      <div class="modal-body">
        <div class="modal-meta">
          <div class="modal-avatar">${initial}</div>
          <div>
            <div class="modal-author">${escHtml(post.author)}</div>
            <div class="modal-date">${dateStr}</div>
          </div>
        </div>
        ${topicBadges ? `<div class="modal-topics">${topicBadges}</div>` : ''}
        <div class="modal-text">${post.html || ''}</div>
        ${reactionsHtml}
      </div>
    `;

    modal.classList.add('active');
    document.body.style.overflow = 'hidden';
  }

  function closePostModal() {
    const modal = $('#post-modal');
    if (modal) {
      modal.classList.remove('active');
      $('#post-modal-content').innerHTML = ''; // Clear contents to stop videos playing
      document.body.style.overflow = '';
    }
  }

  // ── Lightbox ─────────────────────────────────────────
  function openLightbox(postIndex, imgIndex) {
    const post = allPosts[postIndex];
    if (!post || !post.images) return;

    lightboxImages = post.images.map(img => img.full || img.thumb);
    lightboxIndex = imgIndex || 0;

    const lb = $('#lightbox');
    const img = $('#lightbox-img');
    img.src = lightboxImages[lightboxIndex];
    lb.classList.add('active');
    // Ensure body overflow hidden remains
    document.body.style.overflow = 'hidden';

    // Show/hide nav buttons
    updateLightboxNav();
  }

  function closeLightbox() {
    const lb = $('#lightbox');
    lb.classList.remove('active');
    // Restore overflow ONLY if modal is not open
    if (!$('#post-modal').classList.contains('active')) {
      document.body.style.overflow = '';
    }
  }

  function lightboxPrev() {
    if (lightboxIndex > 0) {
      lightboxIndex--;
      $('#lightbox-img').src = lightboxImages[lightboxIndex];
      updateLightboxNav();
    }
  }

  function lightboxNext() {
    if (lightboxIndex < lightboxImages.length - 1) {
      lightboxIndex++;
      $('#lightbox-img').src = lightboxImages[lightboxIndex];
      updateLightboxNav();
    }
  }

  function updateLightboxNav() {
    const prev = $('#lightbox-prev');
    const next = $('#lightbox-next');
    if (prev) prev.style.display = lightboxIndex > 0 ? 'flex' : 'none';
    if (next) next.style.display = lightboxIndex < lightboxImages.length - 1 ? 'flex' : 'none';
  }

  // ── View switching ───────────────────────────────────
  function switchView(view) {
    currentView = view;

    // Update tabs
    $$('.nav-tab').forEach(tab => {
      tab.classList.toggle('active', tab.dataset.view === view);
    });

    // Toggle views
    const grid = $('#posts-grid');
    const main = $('.main');
    const tiktok = $('#tiktok-feed');
    const sidebar = $('.sidebar');
    const counter = $('#tiktok-counter');
    const navHint = $('#tiktok-nav-hint');

    if (view === 'grid') {
      if (grid) grid.style.display = '';
      if (main) { main.style.display = ''; main.classList.remove('full-width'); }
      if (tiktok) tiktok.classList.remove('active');
      if (sidebar) sidebar.classList.remove('hidden');
      if (counter) counter.style.display = 'none';
      if (navHint) navHint.style.display = 'none';
      renderGrid();
    } else {
      if (grid) grid.style.display = 'none';
      if (main) { main.style.display = 'none'; }
      if (tiktok) tiktok.classList.add('active');
      if (sidebar) sidebar.classList.add('hidden');
      if (counter) counter.style.display = '';
      if (navHint) navHint.style.display = '';
      initTiktokFeed();
    }
  }

  // ── Events ───────────────────────────────────────────
  function bindEvents() {
    // Search
    const searchInput = $('#search-input');
    const searchClear = $('#search-clear');
    let searchTimeout;
    searchInput.addEventListener('input', () => {
      clearTimeout(searchTimeout);
      searchTimeout = setTimeout(() => {
        searchQuery = searchInput.value.trim();
        searchClear.classList.toggle('visible', searchQuery.length > 0);
        applyFilters();
      }, 250);
    });

    searchClear.addEventListener('click', () => {
      searchInput.value = '';
      searchQuery = '';
      searchClear.classList.remove('visible');
      applyFilters();
    });

    // View tabs
    $$('.nav-tab').forEach(tab => {
      tab.addEventListener('click', () => switchView(tab.dataset.view));
    });

    // Sidebar toggle (mobile)
    const sidebarToggle = $('#sidebar-toggle');
    const sidebar = $('.sidebar');
    if (sidebarToggle) {
      sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('visible');
      });
    }

    // Delegation click handler
    document.addEventListener('click', (e) => {
      
      // Post Card in Grid click -> opens Modal
      const postCard = e.target.closest('.post-card');
      // But avoid triggering if clicking a badge or playing video directly
      if (postCard && !e.target.closest('.topic-badge') && !e.target.closest('a') && currentView === 'grid') {
        const postIdx = parseInt(postCard.dataset.postIndex);
        openPostModal(postIdx);
        return;
      }

      // Sidebar: Topic category headers (expand/collapse + filter)
      const catHeader = e.target.closest('.topic-category-header');
      if (catHeader) {
        const catDiv = catHeader.closest('.topic-category');
        const catId = catHeader.dataset.cat;

        // Toggle open
        catDiv.classList.toggle('open');

        // Set filter to full category
        if (activeFilter && activeFilter.category === catId && !activeFilter.subcategory) {
          activeFilter = null;
          catHeader.classList.remove('active');
        } else {
          $$('.topic-category-header').forEach(h => h.classList.remove('active'));
          $$('.topic-item').forEach(h => h.classList.remove('active'));

          activeFilter = { category: catId, subcategory: null };
          catHeader.classList.add('active');
        }

        updateClearButton();
        applyFilters();
        return;
      }

      // Sidebar: Subcategory click
      const subItem = e.target.closest('.topic-item');
      if (subItem) {
        const catId = subItem.dataset.cat;
        const subId = subItem.dataset.sub;

        if (activeFilter && activeFilter.category === catId && activeFilter.subcategory === subId) {
          activeFilter = null;
          subItem.classList.remove('active');
        } else {
          $$('.topic-category-header').forEach(h => h.classList.remove('active'));
          $$('.topic-item').forEach(h => h.classList.remove('active'));
          activeFilter = { category: catId, subcategory: subId };
          subItem.classList.add('active');
        }

        updateClearButton();
        applyFilters();

        if (window.innerWidth <= 1024) {
          sidebar.classList.remove('visible');
        }
        return;
      }

      // Topic badges inside posts
      const badge = e.target.closest('.topic-badge');
      if (badge) {
        // If modal was open, close it since we are applying a filter
        closePostModal();

        const catId = badge.dataset.cat;
        const subId = badge.dataset.sub;

        $$('.topic-category-header').forEach(h => h.classList.remove('active'));
        $$('.topic-item').forEach(h => h.classList.remove('active'));

        activeFilter = { category: catId, subcategory: subId };

        const sidebarItem = $(`.topic-item[data-cat="${catId}"][data-sub="${subId}"]`);
        if (sidebarItem) {
          sidebarItem.classList.add('active');
          const catDiv = sidebarItem.closest('.topic-category');
          if (catDiv) catDiv.classList.add('open');
        }

        updateClearButton();
        applyFilters();
        return;
      }

      // Image click in Modal or TikTok -> lightbox
      const imgItem = e.target.closest('.image-item, .tiktok-image-wrap');
      if (imgItem) {
        const postIdx = parseInt(imgItem.dataset.postIndex);
        const imgIdx = parseInt(imgItem.dataset.imgIndex || 0);
        openLightbox(postIdx, imgIdx);
        return;
      }

      // Modal close
      if (e.target.closest('.post-modal-close') || (e.target.classList.contains('post-modal-overlay') && e.target.id === 'post-modal')) {
        closePostModal();
        return;
      }

      // Lightbox close
      if (e.target.closest('.lightbox-close') || (e.target.classList.contains('lightbox') && e.target.id === 'lightbox')) {
        closeLightbox();
        return;
      }

      // Lightbox nav
      if (e.target.closest('.lightbox-prev')) { lightboxPrev(); return; }
      if (e.target.closest('.lightbox-next')) { lightboxNext(); return; }
    });

    // Clear filter button
    const clearBtn = $('#sidebar-clear');
    if (clearBtn) {
      clearBtn.addEventListener('click', () => {
        activeFilter = null;
        $$('.topic-category-header').forEach(h => h.classList.remove('active'));
        $$('.topic-item').forEach(h => h.classList.remove('active'));
        updateClearButton();
        applyFilters();
      });
    }

    // Keyboard
    document.addEventListener('keydown', (e) => {
      const modalOpen = $('#post-modal').classList.contains('active');
      const lightboxOpen = $('#lightbox').classList.contains('active');

      if (e.key === 'Escape') {
        if (lightboxOpen) {
          closeLightbox();
        } else if (modalOpen) {
          closePostModal();
        }
      }
      
      if (lightboxOpen) {
        if (e.key === 'ArrowLeft') lightboxPrev();
        if (e.key === 'ArrowRight') lightboxNext();
      }
    });

    // TikTok scroll counter
    const tiktokFeed = $('#tiktok-feed');
    if (tiktokFeed) {
      tiktokFeed.addEventListener('scroll', debounce(updateTiktokCounter, 100));
    }

    // TikTok nav buttons
    const tiktokUp = $('#tiktok-up');
    const tiktokDown = $('#tiktok-down');
    if (tiktokUp) {
      tiktokUp.addEventListener('click', () => {
        const feed = $('#tiktok-feed');
        const h = feed.clientHeight;
        feed.scrollBy({ top: -h, behavior: 'smooth' });
      });
    }
    if (tiktokDown) {
      tiktokDown.addEventListener('click', () => {
        const feed = $('#tiktok-feed');
        const h = feed.clientHeight;
        feed.scrollBy({ top: h, behavior: 'smooth' });
      });
    }
  }

  function updateClearButton() {
    const btn = $('#sidebar-clear');
    if (btn) btn.classList.toggle('visible', !!activeFilter);
  }

  // ── Helpers ──────────────────────────────────────────
  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr;
      const months = ['января', 'февраля', 'марта', 'апреля', 'мая', 'июня',
                       'июля', 'августа', 'сентября', 'октября', 'ноября', 'декабря'];
      return `${d.getDate()} ${months[d.getMonth()]} ${d.getFullYear()}`;
    } catch {
      return dateStr;
    }
  }

  function getSubcategoryLabel(catId, subId) {
    const cat = taxonomy.find(c => c.id === catId);
    if (!cat) return subId;
    const sub = cat.children.find(s => s.id === subId);
    return sub ? sub.label : subId;
  }

  function escHtml(str) {
    if (!str) return '';
    return str.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  }

  function debounce(fn, ms) {
    let timer;
    return function(...args) {
      clearTimeout(timer);
      timer = setTimeout(() => fn.apply(this, args), ms);
    };
  }

  // ── Boot ─────────────────────────────────────────────
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
