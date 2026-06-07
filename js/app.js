/* ════════════════════════════════════════════════════════
   ASTRO ARCHIVE — Application Logic (SpaceX Edition)
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

  // ── Stemming & Search Helpers ──────────────────────────
  function getStem(word) {
    word = word.toLowerCase().replace(/ё/g, 'е').replace(/[^а-яa-z0-9]/g, '');
    if (word.length <= 3) return word;

    // English stemming (simple)
    if (/^[a-z]+$/.test(word)) {
      if (word.endsWith('es')) return word.slice(0, -2);
      if (word.endsWith('s') && !word.endsWith('ss')) return word.slice(0, -1);
      if (word.endsWith('ing')) return word.slice(0, -3);
      if (word.endsWith('ed')) return word.slice(0, -2);
      return word;
    }

    // Russian stemming (simple rule-based)
    const endings = /(ами|ями|иями|ому|ему|уми|ыми|ими|ого|его|ой|ей|ий|ый|ая|яя|ое|ее|ые|ие|ых|их|ов|ев|ех|ах|ях|ом|ем|ам|ям|а|я|о|е|ы|и|у|ю|ь|ей)$/;
    let prev;
    let stemmed = word;
    do {
      prev = stemmed;
      if (stemmed.length > 3) {
        stemmed = stemmed.replace(endings, '');
      }
    } while (stemmed !== prev && stemmed.length > 3);

    return stemmed;
  }

  function matchSearch(post, query) {
    if (!query) return true;
    const queryWords = query.toLowerCase().split(/\s+/).filter(Boolean);
    if (queryWords.length === 0) return true;

    const author = (post.author || '').toLowerCase();
    const text = (post.text || '').toLowerCase().replace(/ё/g, 'е');
    const textWords = (text + ' ' + author).split(/[^а-яa-z0-9]+/);
    const textStems = new Set(textWords.map(getStem).filter(Boolean));

    const queryStems = queryWords.map(getStem);

    return queryStems.every((qStem, idx) => {
      if (textStems.has(qStem)) return true;
      const qWord = queryWords[idx];
      return textWords.some(tWord => tWord.startsWith(qWord));
    });
  }

  // ── Init ─────────────────────────────────────────────
  async function init() {
    try {
      const res = await fetch('posts.json');
      const data = await res.json();
      allPosts = data.posts;
      taxonomy = data.taxonomy;

      // Sort posts newest first
      allPosts.sort((a, b) => (b.dateISO || '').localeCompare(a.dateISO || ''));

      renderFilterPills();
      updateHeroStats();
      applyFilters();
      bindEvents();
      hideLoading();
    } catch (err) {
      console.error('Failed to load data', err);
      const main = $('#main-content');
      if (main) {
        main.innerHTML = `
          <div class="empty-state">
            <div class="empty-icon">⚠️</div>
            <div class="empty-title">ОШИБКА ЗАГРУЗКИ</div>
            <div class="empty-desc">Не удалось загрузить данные. Убедитесь что posts.json существует.</div>
          </div>
        `;
      }
    }
  }

  function hideLoading() {
    const l = $('#loading');
    if (l) l.remove();
  }

  // ── Hero Stats ──────────────────────────────────────
  function updateHeroStats() {
    const postCount = allPosts.length;
    const authors = new Set(allPosts.map(p => p.author)).size;
    const images = allPosts.reduce((sum, p) => sum + (p.images ? p.images.length : 0), 0);

    animateCounter('hero-stat-posts', postCount);
    animateCounter('hero-stat-authors', authors);
    animateCounter('hero-stat-images', images);
  }

  function animateCounter(id, target) {
    const el = document.getElementById(id);
    if (!el) return;
    
    const duration = 1500;
    const startTime = performance.now();
    
    function update(currentTime) {
      const elapsed = currentTime - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3); // ease-out cubic
      
      el.textContent = Math.round(eased * target);
      
      if (progress < 1) {
        requestAnimationFrame(update);
      }
    }
    
    requestAnimationFrame(update);
  }

  // ── Filter Pills ──────────────────────────────────
  function renderFilterPills() {
    const container = $('#filter-pills');
    if (!container) return;

    // Count posts per category/subcategory
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

      // Add category pill
      const label = cat.label.replace(/^[^\s]+\s/, ''); // Remove emoji prefix
      html += `<button class="filter-pill" data-cat="${cat.id}">${label}</button>`;

      // Add subcategory pills (only if category has multiple children)
      if (cat.children.length > 1) {
        cat.children.forEach(sub => {
          const subCount = counts[`${cat.id}/${sub.id}`] || 0;
          if (subCount === 0) return;
          html += `<button class="filter-pill" data-cat="${cat.id}" data-sub="${sub.id}">${sub.label}</button>`;
        });
      }
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

    // Search using smart stemming
    if (searchQuery) {
      posts = posts.filter(p => matchSearch(p, searchQuery));
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
          <div class="empty-icon">—</div>
          <div class="empty-title">НИЧЕГО НЕ НАЙДЕНО</div>
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
            ${isVideo ? `<div class="video-play-badge"></div>` : ''}
            ${isVideo && duration ? `<div class="video-duration-badge">${duration}</div>` : ''}
            ${totalMedia > 1 ? `<span class="image-count-badge">${totalMedia} ФОТО</span>` : ''}
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

    // Set up IntersectionObserver for scroll-reveal
    setupScrollReveal();
  }

  // ── Scroll Reveal (IntersectionObserver) ─────────────
  function setupScrollReveal() {
    const cards = $$('.post-card');
    
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry, i) => {
        if (entry.isIntersecting) {
          // Stagger the animation slightly
          const delay = Math.min(Array.from(entry.target.parentElement.children)
            .filter(c => !c.classList.contains('visible'))
            .indexOf(entry.target) * 80, 400);
          
          setTimeout(() => {
            entry.target.classList.add('visible');
          }, Math.max(delay, 0));
          
          observer.unobserve(entry.target);
        }
      });
    }, {
      threshold: 0.05,
      rootMargin: '0px 0px -40px 0px'
    });

    cards.forEach(card => observer.observe(card));
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
            <div class="empty-icon">—</div>
            <div class="empty-title">НЕТ ПУБЛИКАЦИЙ</div>
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
          const v = post.videos[0];
          imageHtml = `
            <div class="tiktok-video-wrap">
              <video src="${v.src}" poster="${v.thumb}" controls ${v.type === 'gif' ? 'loop muted autoplay' : ''} style="width:100%; max-height: 400px; object-fit: contain;"></video>
            </div>`;
        } else {
          const full = post.images[0].full || post.images[0].thumb;
          imageHtml = `
            <div class="tiktok-image-wrap" data-post-index="${allPosts.indexOf(post)}" data-img-index="0">
              <img src="${full}" alt="" loading="lazy">
              ${totalMedia > 1 ? `<span class="image-count-badge">${totalMedia} ФОТО</span>` : ''}
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
      $('#post-modal-content').innerHTML = '';
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
    document.body.style.overflow = 'hidden';

    updateLightboxNav();
  }

  function closeLightbox() {
    const lb = $('#lightbox');
    lb.classList.remove('active');
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

    // Update nav links
    $$('.nav-link').forEach(link => {
      link.classList.toggle('active', link.dataset.view === view);
    });

    // Toggle views
    const grid = $('#posts-grid');
    const main = $('#main-content');
    const hero = $('#hero');
    const filterBar = $('#filter-bar');
    const tiktok = $('#tiktok-feed');
    const counter = $('#tiktok-counter');
    const navHint = $('#tiktok-nav-hint');

    if (view === 'grid') {
      if (grid) grid.style.display = '';
      if (main) main.style.display = '';
      if (hero) hero.style.display = '';
      if (filterBar) filterBar.style.display = '';
      if (tiktok) tiktok.classList.remove('active');
      if (counter) counter.style.display = 'none';
      if (navHint) navHint.style.display = 'none';
      renderGrid();
    } else {
      if (grid) grid.style.display = 'none';
      if (main) main.style.display = 'none';
      if (hero) hero.style.display = 'none';
      if (filterBar) filterBar.style.display = 'none';
      if (tiktok) tiktok.classList.add('active');
      if (counter) counter.style.display = '';
      if (navHint) navHint.style.display = '';
      initTiktokFeed();
    }
  }

  // ── Events ───────────────────────────────────────────
  function bindEvents() {
    // Logo click reset
    const logo = $('#nav-logo');
    if (logo) {
      logo.addEventListener('click', (e) => {
        e.preventDefault();
        
        // Reset search
        const searchInput = $('#search-input');
        const searchClear = $('#search-clear');
        if (searchInput) searchInput.value = '';
        if (searchClear) searchClear.classList.remove('visible');
        searchQuery = '';
        
        // Reset filters
        activeFilter = null;
        $$('.filter-pill').forEach(p => p.classList.remove('active'));
        const filterAll = $('#filter-all');
        if (filterAll) filterAll.classList.add('active');
        
        // Reset view
        switchView('grid');
        
        // Apply
        applyFilters();
        
        // Scroll to top smoothly
        window.scrollTo({ top: 0, behavior: 'smooth' });
      });
    }

    // Scroll-based nav background
    const nav = $('#nav');
    window.addEventListener('scroll', () => {
      if (nav) {
        nav.classList.toggle('scrolled', window.scrollY > 80);
      }
    }, { passive: true });

    // Hero scroll hint
    const scrollHint = $('#hero-scroll-hint');
    if (scrollHint) {
      scrollHint.addEventListener('click', () => {
        const filterBar = $('#filter-bar');
        if (filterBar) {
          filterBar.scrollIntoView({ behavior: 'smooth' });
        }
      });
    }

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
    $$('.nav-link').forEach(link => {
      link.addEventListener('click', () => switchView(link.dataset.view));
    });

    // Delegation click handler
    document.addEventListener('click', (e) => {

      // Filter pills
      const pill = e.target.closest('.filter-pill');
      if (pill) {
        const catId = pill.dataset.cat;
        const subId = pill.dataset.sub;
        const filterAll = pill.dataset.filter;

        // Deselect all pills
        $$('.filter-pill').forEach(p => p.classList.remove('active'));

        if (filterAll === 'all') {
          activeFilter = null;
          pill.classList.add('active');
        } else if (activeFilter && activeFilter.category === catId && 
                   ((!subId && !activeFilter.subcategory) || activeFilter.subcategory === subId)) {
          // Clicking same filter = deselect
          activeFilter = null;
          $('#filter-all').classList.add('active');
        } else {
          activeFilter = { category: catId, subcategory: subId || null };
          pill.classList.add('active');
        }

        applyFilters();
        return;
      }
      
      // Post Card in Grid click -> opens Modal
      const postCard = e.target.closest('.post-card');
      if (postCard && !e.target.closest('.topic-badge') && !e.target.closest('a') && currentView === 'grid') {
        const postIdx = parseInt(postCard.dataset.postIndex);
        openPostModal(postIdx);
        return;
      }

      // Topic badges inside posts
      const badge = e.target.closest('.topic-badge');
      if (badge) {
        closePostModal();

        const catId = badge.dataset.cat;
        const subId = badge.dataset.sub;

        $$('.filter-pill').forEach(p => p.classList.remove('active'));
        activeFilter = { category: catId, subcategory: subId };

        // Highlight matching pill
        let matchingPill = $(`.filter-pill[data-cat="${catId}"][data-sub="${subId}"]`);
        if (!matchingPill) {
          matchingPill = $(`.filter-pill[data-cat="${catId}"]:not([data-sub])`);
        }
        if (matchingPill) matchingPill.classList.add('active');

        applyFilters();

        // Scroll to filter bar
        const filterBar = $('#filter-bar');
        if (filterBar) filterBar.scrollIntoView({ behavior: 'smooth' });
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

      // Spoiler reveal
      const spoiler = e.target.closest('.spoiler');
      if (spoiler) {
        spoiler.classList.toggle('revealed');
        return;
      }
    });

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

  // ── Helpers ──────────────────────────────────────────
  function formatDate(dateStr) {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      if (isNaN(d)) return dateStr;
      const months = ['ЯНВАРЯ', 'ФЕВРАЛЯ', 'МАРТА', 'АПРЕЛЯ', 'МАЯ', 'ИЮНЯ',
                       'ИЮЛЯ', 'АВГУСТА', 'СЕНТЯБРЯ', 'ОКТЯБРЯ', 'НОЯБРЯ', 'ДЕКАБРЯ'];
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
