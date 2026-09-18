document.addEventListener('DOMContentLoaded', () => {

  // ── Auth + Watchlist State ──────────────────────────────────────────────────
  const getToken = () => localStorage.getItem('movierec_jwt');
  const getEmail = () => localStorage.getItem('movierec_email');
  const getName = () => localStorage.getItem('movierec_name');
  const getPicture = () => localStorage.getItem('movierec_picture');
  const authHeaders = () => ({ 'Authorization': 'Bearer ' + getToken(), 'Content-Type': 'application/json' });

  let watchlistMovieIds = new Set();
  let watchlistModeActive = false;
  let pendingWatchlistMovie = null;

  function handleTokenExpired() {
    localStorage.removeItem('movierec_jwt');
    localStorage.removeItem('movierec_email');
    localStorage.removeItem('movierec_name');
    localStorage.removeItem('movierec_picture');
    watchlistMovieIds.clear();
    updateAuthUI();
    updateModeUI();
    refreshBookmarkIcons();
    const authModal = document.getElementById('authModal');
    if (authModal) authModal.classList.remove('hidden');
  }

  // Load watchlist IDs if logged in
  function loadWatchlistIds() {
    const token = getToken();
    if (!token) { watchlistMovieIds.clear(); return Promise.resolve(); }
    return fetch('/watchlist/ids', { headers: authHeaders() })
      .then(r => {
        if (r.status === 401) {
          handleTokenExpired();
          return Promise.reject('Token expired');
        }
        return r.ok ? r.json() : Promise.reject('Failed to load watchlist');
      })
      .then(data => { watchlistMovieIds = new Set((data.ids || []).map(String)); })
      .catch(() => { watchlistMovieIds.clear(); });
  }

  function updateAuthUI() {
    const loggedOutNav = document.getElementById('loggedOutNav');
    const loggedInNav = document.getElementById('loggedInNav');
    const navUserEmail = document.getElementById('navUserEmail');
    const navUserAvatar = document.getElementById('navUserAvatar');
    const btnWatchlistMode = document.getElementById('btnWatchlistMode');

    if (getToken()) {
      if (loggedOutNav) loggedOutNav.style.display = 'none';
      if (loggedInNav) loggedInNav.style.display = 'flex';
      const displayName = getName() || getEmail() || '';
      if (navUserEmail) navUserEmail.textContent = displayName;
      if (navUserAvatar) {
        const pic = getPicture();
        if (pic) {
          navUserAvatar.src = pic;
          navUserAvatar.style.display = 'block';
        } else {
          navUserAvatar.style.display = 'none';
        }
      }
      if (btnWatchlistMode) btnWatchlistMode.style.display = '';
    } else {
      if (loggedOutNav) loggedOutNav.style.display = '';
      if (loggedInNav) loggedInNav.style.display = 'none';
      if (navUserAvatar) navUserAvatar.style.display = 'none';
      if (btnWatchlistMode) btnWatchlistMode.style.display = 'none';
      // If watchlist mode was active, switch back to search
      if (watchlistModeActive) {
        watchlistModeActive = false;
        poolModeActive = false;
      }
    }
  }

  // ── Google Identity Services (GIS) ──────────────────────────────────────────
  async function handleGoogleCredentialResponse(response) {
    if (!response || !response.credential) return;
    const authError = document.getElementById('authError');
    if (authError) authError.textContent = '';

    try {
      const res = await fetch('/auth/google', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ credential: response.credential })
      });
      const data = await res.json();
      if (!res.ok) {
        if (authError) authError.textContent = data.error || 'Google sign-in failed.';
        return;
      }

      localStorage.setItem('movierec_jwt', data.token);
      if (data.email) localStorage.setItem('movierec_email', data.email);
      if (data.name) localStorage.setItem('movierec_name', data.name);
      if (data.picture) localStorage.setItem('movierec_picture', data.picture);

      const authModal = document.getElementById('authModal');
      if (authModal) authModal.classList.add('hidden');

      await loadWatchlistIds();
      updateAuthUI();
      updateModeUI();

      if (pendingWatchlistMovie) {
        const p = pendingWatchlistMovie;
        pendingWatchlistMovie = null;
        try {
          await fetch('/watchlist', {
            method: 'POST',
            headers: authHeaders(),
            body: JSON.stringify({ movie_id: p.id, movie_title: p.title, poster_path: p.poster })
          });
          watchlistMovieIds.add(p.id);
        } catch (e) {
          console.error('Auto-add watchlist error:', e);
        }
      }

      refreshBookmarkIcons();
      if (watchlistModeActive) {
        renderWatchlistView();
      }
    } catch (err) {
      console.error('Google Sign-In Error:', err);
      if (authError) authError.textContent = 'Google sign-in network error.';
    }
  }

  function initGoogleSignIn() {
    const googleClient = window.GOOGLE_CLIENT_ID;
    const googleBtnDiv = document.getElementById('googleSignInDiv');
    const googleConfigHint = document.getElementById('googleConfigHint');

    if (!googleClient) {
      if (googleConfigHint) googleConfigHint.style.display = 'block';
      if (googleBtnDiv) googleBtnDiv.style.display = 'none';
      return;
    }

    if (googleConfigHint) googleConfigHint.style.display = 'none';
    if (googleBtnDiv) googleBtnDiv.style.display = 'block';

    let attempts = 0;
    const renderGIS = () => {
      attempts++;
      if (window.google && window.google.accounts && window.google.accounts.id) {
        try {
          window.google.accounts.id.initialize({
            client_id: googleClient,
            callback: handleGoogleCredentialResponse,
            auto_select: false,
            cancel_on_tap_outside: true
          });
          window.google.accounts.id.renderButton(
            googleBtnDiv,
            {
              theme: 'outline',
              size: 'large',
              type: 'standard',
              text: 'continue_with',
              shape: 'pill',
              logo_alignment: 'left',
              width: 280
            }
          );
        } catch (e) {
          console.warn('Could not render Google Sign-In button:', e);
        }
      } else if (attempts < 20) {
        setTimeout(renderGIS, 150);
      }
    };
    renderGIS();
  }

  // Auth Modal Handlers
  const authModal = document.getElementById('authModal');
  if (authModal) {
    authModal.addEventListener('click', (e) => {
      if (e.target === authModal) authModal.classList.add('hidden');
    });
  }

  // Logout
  const btnLogout = document.getElementById('btnLogout');
  if (btnLogout) btnLogout.addEventListener('click', () => {
    localStorage.removeItem('movierec_jwt');
    localStorage.removeItem('movierec_email');
    localStorage.removeItem('movierec_name');
    localStorage.removeItem('movierec_picture');
    watchlistMovieIds.clear();
    updateAuthUI();
    updateModeUI();
    refreshBookmarkIcons();
  });

  function refreshBookmarkIcons() {
    document.querySelectorAll('.watchlist-btn').forEach(btn => {
      const mid = btn.dataset.movieId;
      btn.style.display = '';
      const icon = btn.querySelector('.material-symbols-outlined');
      const isBookmarked = watchlistMovieIds.has(mid);
      if (icon) icon.textContent = isBookmarked ? 'bookmark' : 'bookmark_border';
      btn.classList.toggle('watchlist-active', isBookmarked);
      btn.title = isBookmarked ? 'Remove from Watchlist' : 'Add to Watchlist';
    });
  }

  async function toggleWatchlist(movieId, movieTitle, posterPath, btn) {
    if (!getToken()) {
      pendingWatchlistMovie = { id: String(movieId), title: movieTitle, poster: posterPath };
      const authModal = document.getElementById('authModal');
      if (authModal) authModal.classList.remove('hidden');
      return;
    }
    const mid = String(movieId);
    if (watchlistMovieIds.has(mid)) {
      try {
        const res = await fetch(`/watchlist/${mid}`, { method: 'DELETE', headers: authHeaders() });
        if (res.status === 401) {
          handleTokenExpired();
          return;
        }
        watchlistMovieIds.delete(mid);
        if (watchlistModeActive && btn) {
          const card = btn.closest('.movie-card');
          if (card) {
            card.style.transition = 'all 0.25s ease';
            card.style.opacity = '0';
            card.style.transform = 'scale(0.85)';
            setTimeout(() => {
              card.remove();
              const container = document.getElementById('watchlistResults') || document.getElementById('results');
              const remaining = container.querySelectorAll('.movie-card');
              if (remaining.length === 0) {
                container.innerHTML = '<div class="empty-watchlist" style="grid-column: 1 / -1;"><h2>Your watchlist is empty</h2><p>Search for movies and click the bookmark icon to add them here.</p></div>';
              }
            }, 250);
          }
        }
      } catch (err) {
        console.error('Watchlist delete error:', err);
      }
    } else {
      try {
        const res = await fetch('/watchlist', {
          method: 'POST',
          headers: authHeaders(),
          body: JSON.stringify({ movie_id: mid, movie_title: movieTitle, poster_path: posterPath })
        });
        if (res.status === 401) {
          handleTokenExpired();
          return;
        }
        watchlistMovieIds.add(mid);
      } catch (err) {
        console.error('Watchlist add error:', err);
      }
    }
    refreshBookmarkIcons();
  }

  // Watchlist View
  function renderWatchlistView() {
    const container = document.getElementById('watchlistResults') || document.getElementById('results');
    const sortControls = document.getElementById('sortControls');
    if (sortControls) sortControls.classList.add('hidden');

    if (!getToken()) {
      container.innerHTML = '<div class="empty-watchlist" style="grid-column: 1 / -1;"><h2>Sign in to view your Watchlist</h2><p>Save movies and sync across your devices.</p><button class="user-nav-btn" style="margin-top:16px;" onclick="document.getElementById(\'authModal\').classList.remove(\'hidden\')"><span class="material-symbols-outlined" style="font-size:1.2rem;">person</span>Login with Google</button></div>';
      return;
    }

    container.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding:2rem;"><div class="spinner"></div></div>';

    fetch('/watchlist', { headers: authHeaders() })
      .then(r => {
        if (r.status === 401) {
          handleTokenExpired();
          return Promise.reject('Token expired');
        }
        return r.ok ? r.json() : Promise.reject('Failed to load');
      })
      .then(data => {
        const items = data.watchlist || [];
        if (items.length === 0) {
          container.innerHTML = '<div class="empty-watchlist" style="grid-column: 1 / -1;"><h2>Your watchlist is empty</h2><p>Search for movies and click the bookmark icon to add them here.</p></div>';
          return;
        }
        // Convert watchlist items to the format renderMovieCards expects
        const movies = items.map(item => ({
          id: item.movie_id,
          title: item.movie_title,
          poster_path: item.poster_path,
          overview: '',
          similarity: '',
          adult: 'FALSE'
        }));
        renderMovieCards(movies, false, container, true); // Explicitly render into watchlistResults container!
      })
      .catch((err) => {
        if (err !== 'Token expired') {
          container.innerHTML = '<div class="empty-watchlist" style="grid-column: 1 / -1;"><p>Failed to load watchlist. Try again.</p></div>';
        }
      });
  }

  // Global state for Pool Mode
  let poolModeActive = false;
  let moviePool = JSON.parse(localStorage.getItem('moviePool'));
  if (!Array.isArray(moviePool) || moviePool.length !== 5) {
      moviePool = [null, null, null, null, null];
  }
  let activeModalSlotIndex = null;

  // Handle search button click
  const searchInput = document.querySelector('.searchInput');
  const searchBtn = document.querySelector('.okbtn');
  const loadingOverlay = document.getElementById('loadingOverlay');

  // Pool Mode Elements
  const btnSearchMode = document.getElementById('btnSearchMode');
  const btnPoolMode = document.getElementById('btnPoolMode');
  const searchBarContainer = document.getElementById('searchBarContainer');
  const poolContainer = document.getElementById('poolContainer');
  const poolSlotsContainer = document.getElementById('poolSlotsContainer');
  const findMyMixBtn = document.getElementById('findMyMixBtn');
  const poolWarning = document.getElementById('poolWarning');

  // Modal Elements
  const selectionModal = document.getElementById('selectionModal');
  const modalClose = document.getElementById('modalClose');
  const modalSearchInput = document.getElementById('modalSearchInput');
  const modalSearchBtn = document.getElementById('modalSearchBtn');
  const modalResultsContainer = document.getElementById('modalResults');
  const modalLoadingOverlay = document.getElementById('modalLoadingOverlay');

  function updateModeUI() {
    const btnSearchMode = document.getElementById('btnSearchMode');
    const btnPoolMode = document.getElementById('btnPoolMode');
    const btnWatchlistMode = document.getElementById('btnWatchlistMode');
    const resultsContainer = document.getElementById('results');
    const poolResultsContainer = document.getElementById('poolResults');
    const watchlistResultsContainer = document.getElementById('watchlistResults');
    const sortControls = document.getElementById('sortControls');

    if (watchlistModeActive) {
      if (btnWatchlistMode) btnWatchlistMode.classList.add('active');
      if (btnSearchMode) btnSearchMode.classList.remove('active');
      if (btnPoolMode) btnPoolMode.classList.remove('active');
      if (searchBarContainer) { searchBarContainer.classList.add('hidden'); searchBarContainer.style.display = 'none'; }
      if (poolContainer) { poolContainer.classList.add('hidden'); poolContainer.style.display = 'none'; }
      if (resultsContainer) { resultsContainer.classList.add('hidden'); resultsContainer.style.display = 'none'; }
      if (poolResultsContainer) { poolResultsContainer.classList.add('hidden'); poolResultsContainer.style.display = 'none'; }
      if (watchlistResultsContainer) { watchlistResultsContainer.classList.remove('hidden'); watchlistResultsContainer.style.display = ''; }
      if (sortControls) sortControls.classList.add('hidden');
      renderWatchlistView();
    } else if (poolModeActive) {
      if (btnPoolMode) btnPoolMode.classList.add('active');
      if (btnSearchMode) btnSearchMode.classList.remove('active');
      if (btnWatchlistMode) btnWatchlistMode.classList.remove('active');
      if (searchBarContainer) { searchBarContainer.classList.add('hidden'); searchBarContainer.style.display = 'none'; }
      if (poolContainer) { poolContainer.classList.remove('hidden'); poolContainer.style.display = ''; }
      if (resultsContainer) { resultsContainer.classList.add('hidden'); resultsContainer.style.display = 'none'; }
      if (watchlistResultsContainer) { watchlistResultsContainer.classList.add('hidden'); watchlistResultsContainer.style.display = 'none'; }
      if (poolResultsContainer) { poolResultsContainer.classList.remove('hidden'); poolResultsContainer.style.display = ''; }
      renderPool();
      if (sortControls && poolResultsContainer && poolResultsContainer.innerHTML.trim() !== '') {
        sortControls.classList.remove('hidden');
        const tmdbToggle = document.getElementById('tmdbApiToggle');
        if (tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = 'none';
      } else if (sortControls) {
        sortControls.classList.add('hidden');
      }
    } else {
      if (btnSearchMode) btnSearchMode.classList.add('active');
      if (btnPoolMode) btnPoolMode.classList.remove('active');
      if (btnWatchlistMode) btnWatchlistMode.classList.remove('active');
      if (poolContainer) { poolContainer.classList.add('hidden'); poolContainer.style.display = 'none'; }
      if (poolResultsContainer) { poolResultsContainer.classList.add('hidden'); poolResultsContainer.style.display = 'none'; }
      if (watchlistResultsContainer) { watchlistResultsContainer.classList.add('hidden'); watchlistResultsContainer.style.display = 'none'; }
      if (searchBarContainer) { searchBarContainer.classList.remove('hidden'); searchBarContainer.style.display = ''; }
      if (resultsContainer) { resultsContainer.classList.remove('hidden'); resultsContainer.style.display = ''; }
      if (sortControls && resultsContainer && resultsContainer.innerHTML.trim() !== '' && !resultsContainer.querySelector('.similar-banner')) {
        sortControls.classList.remove('hidden');
        const tmdbToggle = document.getElementById('tmdbApiToggle');
        if (tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = 'flex';
      } else if (sortControls) {
        sortControls.classList.add('hidden');
      }
    }
  }

  if (btnSearchMode) {
    btnSearchMode.addEventListener('click', () => {
      poolModeActive = false;
      watchlistModeActive = false;
      const newUrl = new URL(window.location);
      newUrl.searchParams.delete('mode');
      window.history.pushState({}, '', newUrl);
      updateModeUI();
    });
  }

  if (btnPoolMode) {
    btnPoolMode.addEventListener('click', () => {
      poolModeActive = true;
      watchlistModeActive = false;
      const newUrl = new URL(window.location);
      newUrl.searchParams.set('mode', 'pool');
      newUrl.searchParams.delete('q');
      newUrl.searchParams.delete('recommend_id');
      newUrl.searchParams.delete('recommend_title');
      window.history.pushState({ mode: 'pool' }, '', newUrl);
      updateModeUI();
    });
  }

  const btnWatchlistMode = document.getElementById('btnWatchlistMode');
  if (btnWatchlistMode) {
    btnWatchlistMode.addEventListener('click', () => {
      watchlistModeActive = true;
      poolModeActive = false;
      const newUrl = new URL(window.location);
      newUrl.searchParams.set('mode', 'watchlist');
      newUrl.searchParams.delete('q');
      newUrl.searchParams.delete('recommend_id');
      newUrl.searchParams.delete('recommend_title');
      window.history.pushState({ mode: 'watchlist' }, '', newUrl);
      updateModeUI();
    });
  }

  // Init auth state and load watchlist IDs
  loadWatchlistIds().then(() => {
    updateAuthUI();
    updateModeUI();
    initGoogleSignIn();
  });

  function showLoadingOverlay() {
    if (loadingOverlay) loadingOverlay.style.display = 'flex';
  }

  function hideLoadingOverlay() {
    if (loadingOverlay) loadingOverlay.style.display = 'none';
  }

  function resetToHomePage() {
    searchInput.value = '';
    const resultsContainer = document.getElementById('results');
    if (resultsContainer) resultsContainer.innerHTML = '';
    hideLoadingOverlay();
    const sortControls = document.getElementById('sortControls');
    if (sortControls) sortControls.classList.add('hidden');
    const newUrl = new URL(window.location);
    newUrl.searchParams.delete('q');
    newUrl.searchParams.delete('recommend_id');
    newUrl.searchParams.delete('recommend_title');
    newUrl.searchParams.delete('mode');
    window.history.pushState({}, '', newUrl);
  }

  function performSearch() {
    const title = searchInput.value.trim();
    if (!title) {
      resetToHomePage();
      return;
    }

    showLoadingOverlay();

    // Update URL so the Back button works
    const newUrl = new URL(window.location);
    newUrl.searchParams.set('q', title);
    newUrl.searchParams.delete('recommend_id');
    newUrl.searchParams.delete('recommend_title');
    newUrl.searchParams.delete('mode');
    window.history.pushState({ query: title }, '', newUrl);

    fetchAndRender(title);
  }

  // Helper function to render cards (used by search results, recommendations, and watchlist)
  function renderMovieCards(movies, isSearchResult = false, targetContainer = null, isWatchlist = false) {
    const isModal = targetContainer === modalResultsContainer;
    const container = targetContainer || document.getElementById('results');

    if (isModal) {
      document.getElementById('modalScrollWrapper').style.display = 'block';
    }

    if (!isModal) hideLoadingOverlay();
    if (isModal && modalLoadingOverlay) modalLoadingOverlay.style.display = 'none';

    container.innerHTML = '';

    const sortControls = document.getElementById('sortControls');
    if (sortControls && !isModal) {
      if (isSearchResult || isWatchlist) {
        sortControls.classList.add('hidden');
      } else {
        sortControls.classList.remove('hidden');
        const tmdbToggle = document.getElementById('tmdbApiToggle');
        if (tmdbToggle) {
          if (poolModeActive) {
            tmdbToggle.parentElement.style.display = 'none';
          } else {
            tmdbToggle.parentElement.style.display = 'flex';
          }
        }
      }
    }

    movies.forEach((movie, index) => {
      renderSingleCard(movie, index, container, isSearchResult, isWatchlist, isModal);
    });
  }

  // Builds and appends a single movie card to container
  function renderSingleCard(movie, index, container, isSearchResult, isWatchlist, isModal = false) {
      const card = document.createElement('div');
      card.className = 'movie-card';

      let img = document.createElement('img');
      if (movie.adult === 'TRUE') {
        img.src = '/static/icons/18_up_rating_24dp_8B1A10_FILL0_wght400_GRAD0_opsz24.svg';
        img.alt = '18+ Poster';
        img.classList.add('fallback');
      } else {
        img.src = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '/static/icons/fallback.svg';
        img.alt = 'Poster';
        if (!movie.poster_path) img.classList.add('fallback');
        img.onerror = function () {
          this.onerror = null;
          this.src = '/static/icons/fallback.svg';
          this.classList.add('fallback');
        };
      }
      card.appendChild(img);

      const overlay = document.createElement('div');
      overlay.className = 'hover-overlay';
      const hoverContent = document.createElement('div');
      hoverContent.className = 'hover-content';
      const hoverTitle = document.createElement('h3');
      hoverTitle.className = 'hover-title';
      hoverTitle.textContent = movie.title || 'Untitled Movie';
      const hoverRating = document.createElement('div');
      hoverRating.className = 'hover-rating';
      hoverRating.innerHTML = `<span class="tmdb-star">★</span> <span class="rating-value">--</span>`;
      const hoverOverview = document.createElement('p');
      hoverOverview.className = 'hover-overview';
      hoverOverview.textContent = movie.overview || 'No description available.';
      hoverContent.appendChild(hoverTitle);
      hoverContent.appendChild(hoverRating);
      hoverContent.appendChild(hoverOverview);
      overlay.appendChild(hoverContent);
      card.appendChild(overlay);

      // Similarity badge
      if (!isSearchResult && !isWatchlist && movie.similarity) {
        if (index !== 0 || poolModeActive) {
          const simBadge = document.createElement('div');
          simBadge.className = 'similarity-badge';
          simBadge.textContent = String(movie.similarity).includes('%') ? movie.similarity : `${movie.similarity}%`;
          card.appendChild(simBadge);
        }
      }

      // "Selected" badge on first result
      if (!isSearchResult && !isWatchlist && index === 0 && !poolModeActive) {
        card.classList.add('selected');
        const badge = document.createElement('div');
        badge.className = 'selected-badge';
        badge.textContent = 'Selected';
        card.appendChild(badge);
      }

      // Live TMDB metadata fetch
      const targetId = movie.id || movie.tmdb_id;
      if (targetId) {
        const apiKey = window.TMDB_API_KEY || '';
        const apiBase = window.TMDB_API_BASE || 'https://api.tmdb.org/3';
        fetch(`${apiBase}/movie/${targetId}?api_key=${apiKey}`)
          .then(res => res.json())
          .then(data => {
            if (data.adult === true) {
              img.src = '/static/icons/18_up_rating_24dp_8B1A10_FILL0_wght400_GRAD0_opsz24.svg';
              img.classList.add('fallback');
            } else if (data.poster_path && img.src.includes('fallback.svg') && !img.src.includes('18_up')) {
              img.src = `https://image.tmdb.org/t/p/w500${data.poster_path}`;
              img.classList.remove('fallback');
            }
            hoverRating.querySelector('.rating-value').textContent = data.vote_average ? data.vote_average.toFixed(1) : 'NR';
            if (data.title) hoverTitle.textContent = data.title;
            if (data.overview) hoverOverview.textContent = data.overview;
          })
          .catch(() => {
            if (hoverRating.querySelector('.rating-value').textContent === '--') {
              hoverRating.querySelector('.rating-value').textContent = 'NR';
            }
          });
      }

      if (isModal) {
        const alreadySelected = moviePool.some(m => m && String(m.id) === String(targetId));
        if (alreadySelected) card.classList.add('disabled');
      }

      card.onclick = () => {
        if (card.classList.contains('disabled')) return;
        if (isModal) {
          moviePool[activeModalSlotIndex] = {
            id: String(movie.id || movie.tmdb_id),
            title: movie.title || movie.display_title || 'Unknown Title',
            poster_path: movie.poster_path || ''
          };
          savePool();
          closeModal();
          const poolRes = document.getElementById('poolResults');
          if (poolRes) poolRes.innerHTML = '';
          const sc = document.getElementById('sortControls');
          if (sc) sc.classList.add('hidden');
          renderPool();
        } else if (isWatchlist) {
          const urlTargetId = movie.id || movie.tmdb_id;
          if (urlTargetId) window.location.href = `/movie/${urlTargetId}`;
        } else if (isSearchResult) {
          const newUrl = new URL(window.location);
          newUrl.searchParams.set('recommend_id', movie.id);
          newUrl.searchParams.set('recommend_title', movie.title);
          newUrl.searchParams.delete('mode');
          window.history.pushState({ recommend_id: movie.id, recommend_title: movie.title }, '', newUrl);
          searchInput.value = movie.title;
          fetchRecommendations(movie.title, movie.id, false);
        } else {
          const urlTargetId = movie.id || movie.tmdb_id;
          if (!urlTargetId) { alert('Error: Movie ID not found.'); return; }
          window.location.href = `/movie/${urlTargetId}`;
        }
      };

      // Watchlist bookmark button
      if (!isModal) {
        const bookmarkBtn = document.createElement('button');
        bookmarkBtn.className = 'watchlist-btn';
        bookmarkBtn.dataset.movieId = String(targetId);
        const isBookmarked = watchlistMovieIds.has(String(targetId));
        bookmarkBtn.title = isBookmarked ? 'Remove from Watchlist' : 'Add to Watchlist';
        const bookmarkIcon = document.createElement('span');
        bookmarkIcon.className = 'material-symbols-outlined';
        bookmarkIcon.textContent = isBookmarked ? 'bookmark' : 'bookmark_border';
        bookmarkBtn.appendChild(bookmarkIcon);
        if (isBookmarked) bookmarkBtn.classList.add('watchlist-active');
        bookmarkBtn.addEventListener('click', (e) => {
          e.stopPropagation();
          toggleWatchlist(targetId, movie.title || '', movie.poster_path || '', bookmarkBtn);
        });
        card.appendChild(bookmarkBtn);
      }

      container.appendChild(card);
  }


  // Function to actually trigger the AI Recommendations
  function fetchRecommendations(title, id, showLoading = true) {
    if (showLoading) showLoadingOverlay();

    // Check TMDB API Override
    const tmdbToggle = document.getElementById('tmdbApiToggle');
    if (tmdbToggle && tmdbToggle.checked) {
      if (id) {
        fetchTMDBRecommendations(id, title).then(data => {
          if (data && data.results && data.results.length > 0) {
            renderMovieCards(data.results, false);
          }
        });
      } else {
        showSimilarMovies(title);
      }
      return;
    }

    const sortToggle = document.getElementById('qualitySortToggle');
    const sortMode = (sortToggle && sortToggle.checked) ? 'quality' : 'similarity';

    const strictGenreToggle = document.getElementById('strictGenreToggle');
    const strictGenre = (strictGenreToggle && strictGenreToggle.checked) ? 'true' : 'false';

    // Fetch up to 100 results; render 25 at a time
    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=100&id=${id || ''}&sort=${sortMode}&strict_genre=${strictGenre}`;

    fetch(url)
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            if (res.status === 404) {
              if (id) {
                return fetchTMDBRecommendations(id, title);
              } else {
                showSimilarMovies(title);
                throw new Error("");
              }
            }
            throw new Error(err.error || "An unexpected error occurred.");
          });
        }
        return res.json();
      })
      .then(data => {
        if (data && data.results && data.results.length > 0) {
          renderMovieCardsPaginated(data.results, false);
        }
      })
      .catch(err => {
        if (err.message === "") return;
        console.error("Fetch errors:", err);
      });
  }

  // Render results in batches of 25 with a Load More button (max 100)
  function renderMovieCardsPaginated(allMovies, isSearchResult = false, targetContainer = null) {
    const PAGE_SIZE = 25;
    const container = targetContainer || document.getElementById('results');
    hideLoadingOverlay();
    container.innerHTML = '';

    const sortControls = document.getElementById('sortControls');
    if (sortControls) {
      sortControls.classList.remove('hidden');
      const tmdbToggle = document.getElementById('tmdbApiToggle');
      if (tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = poolModeActive ? 'none' : 'flex';
    }

    let rendered = 0;

    function renderNextBatch() {
      // Remove existing Load More button if present
      const existingBtn = document.getElementById('loadMoreBtn');
      if (existingBtn) existingBtn.remove();

      const batch = allMovies.slice(rendered, rendered + PAGE_SIZE);
      batch.forEach((movie, batchIndex) => {
        renderSingleCard(movie, rendered + batchIndex, container, isSearchResult, false);
      });
      rendered += batch.length;

      if (rendered < allMovies.length) {
        const loadMoreBtn = document.createElement('button');
        loadMoreBtn.id = 'loadMoreBtn';
        loadMoreBtn.className = 'load-more-btn';
        loadMoreBtn.textContent = `Load more (${rendered} / ${allMovies.length})`;
        loadMoreBtn.style.gridColumn = '1 / -1';
        loadMoreBtn.addEventListener('click', renderNextBatch);
        container.appendChild(loadMoreBtn);
      }
    }

    renderNextBatch();
  }

  function fetchTMDBRecommendations(id, title) {
    const apiKey = window.TMDB_API_KEY || '';
    const apiBase = window.TMDB_API_BASE || 'https://api.tmdb.org/3';
    const url = `${apiBase}/movie/${id}/recommendations?api_key=${apiKey}&language=en-US&page=1`;
    return fetch(url)
      .then(res => {
        if (!res.ok) {
          showSimilarMovies(title);
          throw new Error("");
        }
        return res.json();
      })
      .then(data => {
        if (data.results && data.results.length > 0) {
          // Mock the expected backend structure
          const mockedResults = [{
            'id': id.toString(),
            'title': title,
            'overview': 'Showing TMDB Recommendations',
            'similarity': '100%'
          }]; // The exact movie as the first element like local backend does

          data.results.forEach(movie => {
            mockedResults.push({
              'id': movie.id.toString(),
              'title': movie.title,
              'overview': movie.overview,
              'vote_average': movie.vote_average,
              'popularity': movie.popularity,
              'poster_path': movie.poster_path,
              'similarity': 'TMDB', // Badge
              'adult': movie.adult ? 'TRUE' : 'FALSE'
            });
          });
          let similarMovies = mockedResults.slice(1);

          const sortToggle = document.getElementById('qualitySortToggle');
          if (sortToggle && sortToggle.checked) {
            similarMovies.sort((a, b) => b.vote_average - a.vote_average);
          }

          return { results: [mockedResults[0], ...similarMovies].slice(0, 26) }; // top item + 25 related
        } else {
          showSimilarMovies(title);
          throw new Error("");
        }
      });
  }

  function showSimilarMovies(query, targetContainer = null) {
    const isModal = targetContainer === modalResultsContainer;
    const container = targetContainer || document.getElementById('results');

    if (isModal) {
      document.getElementById('modalScrollWrapper').style.display = 'block';
    }

    if (!isModal) hideLoadingOverlay();
    if (isModal && modalLoadingOverlay) modalLoadingOverlay.style.display = 'none';

    const sortControls = document.getElementById('sortControls');
    if (sortControls && !isModal) sortControls.classList.add('hidden');

    fetch(`/find_similar_movies?q=${encodeURIComponent(query)}`)
      .then(res => res.json())
      .then(data => {
        container.innerHTML = '';

        if (data.length === 0) {
          container.innerHTML = `<div class="no-results" style="grid-column: 1 / -1;"><p>No movies found similar to "${query}". Try a different search.</p></div>`;
          return;
        }

        const header = document.createElement('div');
        header.className = 'similar-movies-header';
        header.style.gridColumn = '1 / -1';
        header.innerHTML = `<h2>Did you mean?</h2><p>We couldn't find an exact match. Here are similar movies:</p>`;
        container.appendChild(header);

        const flexWrapper = document.createElement('div');
        if (!isModal) {
            flexWrapper.style.gridColumn = '1 / -1';
            flexWrapper.style.display = 'flex';
            flexWrapper.style.flexWrap = 'wrap';
            flexWrapper.style.justifyContent = 'center';
            flexWrapper.style.gap = '20px';
        }

        data.forEach(movie => {
          let card;
          if (isModal) {
              card = document.createElement('div');
              card.className = 'movie-card';
              
              const img = document.createElement('img');
              img.src = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '/static/icons/fallback.svg';
              img.alt = movie.display_title;
              img.onerror = function() {
                  this.onerror = null;
                  this.src = '/static/icons/fallback.svg';
                  this.classList.add('fallback');
              };
              card.appendChild(img);
              
              const overlay = document.createElement('div');
              overlay.className = 'hover-overlay';
              const hoverContent = document.createElement('div');
              hoverContent.className = 'hover-content';
              
              const hoverTitle = document.createElement('h3');
              hoverTitle.className = 'hover-title';
              hoverTitle.textContent = movie.display_title || 'Untitled Movie';
              
              const hoverRating = document.createElement('div');
              hoverRating.className = 'hover-rating';
              hoverRating.innerHTML = `<span class="tmdb-star">★</span> <span class="rating-value">--</span>`;
              
              const hoverOverview = document.createElement('p');
              hoverOverview.className = 'hover-overview';
              hoverOverview.textContent = 'Click to search for exact match.';
              
              hoverContent.appendChild(hoverTitle);
              hoverContent.appendChild(hoverRating);
              hoverContent.appendChild(hoverOverview);
              overlay.appendChild(hoverContent);
              card.appendChild(overlay);

          } else {
              card = document.createElement('div');
              card.className = 'similar-movie-card';

              const img = document.createElement('img');
              img.src = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '/static/icons/fallback.svg';
              img.alt = movie.display_title;
              img.onerror = function () {
                this.src = '/static/icons/fallback.svg';
              };

              const info = document.createElement('div');
              info.className = 'similar-movie-info';
              info.innerHTML = `
                  <div class="similar-movie-title">${movie.display_title}</div>
                  <div class="similar-movie-year">${movie.year}</div>
                  <div class="similar-movie-score">Match: ${movie.similarity_score}%</div>
                `;

              card.appendChild(img);
              card.appendChild(info);
          }

          card.addEventListener('click', () => {
             if (isModal) {
                modalSearchInput.value = movie.display_title;
                performModalSearch();
             } else {
                searchInput.value = movie.display_title;
                performSearch();
             }
          });

          if (isModal) {
              container.appendChild(card);
          } else {
              flexWrapper.appendChild(card);
          }
        });
        
        if (!isModal) {
            container.appendChild(flexWrapper);
        }
      })
      .catch(err => {
        console.error("Error fetching similar movies:", err);
        container.innerHTML = `<div class="no-results" style="grid-column: 1 / -1;"><p>Error finding similar movies. Please try again.</p></div>`;
      });
  }

  // Handle Sort Toggle Change
  const sortToggle = document.getElementById('qualitySortToggle');
  if (sortToggle) {
    sortToggle.addEventListener('change', () => {
      if (poolModeActive) {
         performPoolRecommendation();
         return;
      }
      const params = new URLSearchParams(window.location.search);
      const recId = params.get('recommend_id');
      const recTitle = params.get('recommend_title');
      if (recId && recTitle) {
        fetchRecommendations(recTitle, recId, true);
      }
    });
  }

  // Handle Strict Genre Toggle Change
  const strictGenreToggle = document.getElementById('strictGenreToggle');
  if (strictGenreToggle) {
    strictGenreToggle.addEventListener('change', () => {
      if (poolModeActive) {
         performPoolRecommendation();
         return;
      }
      const params = new URLSearchParams(window.location.search);
      const recId = params.get('recommend_id');
      const recTitle = params.get('recommend_title');
      if (recId && recTitle) {
        fetchRecommendations(recTitle, recId, true);
      }
    });
  }

  // Handle TMDB API Toggle Change
  const tmdbApiToggle = document.getElementById('tmdbApiToggle');
  if (tmdbApiToggle) {
    tmdbApiToggle.addEventListener('change', () => {
      if (poolModeActive) return; // N/A
      const params = new URLSearchParams(window.location.search);
      const recId = params.get('recommend_id');
      const recTitle = params.get('recommend_title');
      if (recId && recTitle) {
        fetchRecommendations(recTitle, recId, true);
      }
    });
  }

  // Handle Search button and Enter key
  searchBtn.addEventListener('click', performSearch);

  // Trigger search on Enter key press
  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      performSearch();
    }
  });

  // Handle Browser Back/Forward Buttons
  window.addEventListener('popstate', (event) => {
    const params = new URLSearchParams(window.location.search);
    const query = params.get('q');
    const recId = params.get('recommend_id');
    const recTitle = params.get('recommend_title');
    const mode = params.get('mode');

    if (mode === 'watchlist') {
      watchlistModeActive = true;
      poolModeActive = false;
      updateModeUI();
    } else if (mode === 'pool') {
      poolModeActive = true;
      watchlistModeActive = false;
      updateModeUI();
      const validIds = moviePool.filter(m => m !== null).map(m => m.id);
      if (validIds.length >= 2) performPoolRecommendation(false);
    } else {
      watchlistModeActive = false;
      poolModeActive = false;
      updateModeUI();
      if (recId && recTitle) {
        searchInput.value = recTitle;
        fetchRecommendations(recTitle, recId, true);
      } else if (query) {
        searchInput.value = query;
        // Re-run the search without pushing a new history state
        fetchAndRender(query);
      } else {
        // If we went back to the home page (no ?q=), clear results
        searchInput.value = '';
        document.getElementById('results').innerHTML = '';
        document.getElementById('loadingOverlay').style.display = 'none';
        const sortControls = document.getElementById('sortControls');
        if (sortControls) sortControls.classList.add('hidden');
      }
    }
  });

  // Read URL parameters on initial page load
  const initialParams = new URLSearchParams(window.location.search);
  const initialQuery = initialParams.get('q');
  const initialRecId = initialParams.get('recommend_id');
  const initialRecTitle = initialParams.get('recommend_title');
  const initialMode = initialParams.get('mode');

  if (initialMode === 'watchlist') {
    watchlistModeActive = true;
    poolModeActive = false;
    updateModeUI();
  } else if (initialMode === 'pool') {
    poolModeActive = true;
    watchlistModeActive = false;
    updateModeUI();
    const validIds = moviePool.filter(m => m !== null).map(m => m.id);
    if (validIds.length >= 2) performPoolRecommendation(false);
  } else if (initialRecId && initialRecTitle) {
    searchInput.value = initialRecTitle;
    fetchRecommendations(initialRecTitle, initialRecId, true);
  } else if (initialQuery) {
    searchInput.value = initialQuery;
    fetchAndRender(initialQuery);
  }

  // Refactored fetch logic to allow reusable calls without pushing state
  function fetchAndRender(title, targetContainer = null) {
    const isModal = targetContainer === modalResultsContainer;
    const container = targetContainer || document.getElementById('results');

    if (!isModal) {
        showLoadingOverlay();
    } else {
        if (modalLoadingOverlay) modalLoadingOverlay.style.display = 'flex';
    }

    // Parse (Year) if present in the search query
    let searchQuery = title.trim();
    let yearParam = '';
    const yearMatch = searchQuery.match(/\s*\((\d{4})\)$/);
    if (yearMatch) {
      yearParam = `&primary_release_year=${yearMatch[1]}`;
      searchQuery = searchQuery.replace(/\s*\(\d{4}\)$/, '');
    }

    const apiKey = window.TMDB_API_KEY || '';
    const apiBase = window.TMDB_API_BASE || 'https://api.tmdb.org/3';
    const url = `${apiBase}/search/movie?query=${encodeURIComponent(searchQuery)}${yearParam}&include_adult=true&language=en-US&page=1&api_key=${apiKey}`;

    fetch(url, { headers: { 'accept': 'application/json' } })
      .then(res => res.ok ? res.json() : Promise.reject("Failed to fetch from TMDB"))
      .then(data => {
        if (data.results && data.results.length > 0) {
          return fetch('/enrich_tmdb_results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: data.results.slice(0, 15) })
          })
            .then(res => res.json())
            .then(enrichedData => {
              if (enrichedData.results && enrichedData.results.length > 0) {
                renderMovieCards(enrichedData.results, true, container);
              } else {
                showSimilarMovies(searchQuery, container);
              }
            });
        } else {
          showSimilarMovies(searchQuery, container);
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        if(!isModal) alert("Network or Server error. Try again later.");
        if(isModal && modalLoadingOverlay) modalLoadingOverlay.style.display = 'none';
      });
  }

  /* Pool Mode Logic Additions */

  function savePool() {
      localStorage.setItem('moviePool', JSON.stringify(moviePool));
  }

  function renderPool() {
      if (!poolSlotsContainer) return;
      poolSlotsContainer.innerHTML = '';
      let filledCount = 0;

      moviePool.forEach((movie, index) => {
          const slotWrapper = document.createElement('div');
          slotWrapper.className = 'pool-slot';

          const slotCard = document.createElement('div');
          slotCard.className = `slot-card ${movie ? 'filled' : 'empty'}`;

          if (!movie) {
              slotCard.innerHTML = `<div class="add-icon">+</div>`;
              slotCard.onclick = () => openModal(index);
              slotWrapper.appendChild(slotCard);
          } else {
              filledCount++;

              let img = document.createElement('img');
              img.src = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '/static/icons/fallback.svg';
              img.onerror = function() {
                  this.onerror = null;
                  this.src = '/static/icons/fallback.svg';
              };
              slotCard.appendChild(img);

              const titleOverlay = document.createElement('div');
              titleOverlay.className = 'slot-title-overlay';
              titleOverlay.textContent = movie.title;
              slotCard.appendChild(titleOverlay);
              
              slotCard.onclick = () => openModal(index, movie.title);

              slotWrapper.appendChild(slotCard);

              const actions = document.createElement('div');
              actions.className = 'slot-actions';

              const editBtn = document.createElement('button');
              editBtn.className = 'slot-action-btn';
              editBtn.innerHTML = '<span class="material-symbols-outlined" style="font-size: 1.2rem;">edit</span>';
              editBtn.onclick = (e) => {
                  e.stopPropagation();
                  openModal(index, movie.title);
              };

              const removeBtn = document.createElement('button');
              removeBtn.className = 'slot-action-btn';
              removeBtn.innerHTML = '✕';
              removeBtn.onclick = (e) => {
                  e.stopPropagation();
                  moviePool[index] = null;
                  savePool();
                  const poolRes = document.getElementById('poolResults');
                  if (poolRes) poolRes.innerHTML = ''; // Clear pool results if shown
                  const sortControls = document.getElementById('sortControls');
                  if (sortControls) sortControls.classList.add('hidden');
                  renderPool();
              };

              actions.appendChild(editBtn);
              actions.appendChild(removeBtn);
              slotWrapper.appendChild(actions);
          }
          poolSlotsContainer.appendChild(slotWrapper);
      });

      if (filledCount >= 2) {
          findMyMixBtn.disabled = false;
          poolWarning.classList.add('hidden');
      } else {
          findMyMixBtn.disabled = true;
          if (filledCount === 1) {
              poolWarning.textContent = "Select at least 2 movies.";
              poolWarning.classList.remove('hidden');
              poolWarning.classList.add('pool-hint');
          } else {
              poolWarning.classList.add('hidden');
          }
      }
  }

  function openModal(index, defaultTitle = '') {
      activeModalSlotIndex = index;
      selectionModal.classList.remove('hidden');
      modalResultsContainer.innerHTML = '';
      document.getElementById('modalScrollWrapper').style.display = 'none';
      modalSearchInput.value = defaultTitle;
      if (defaultTitle) {
          performModalSearch();
      } else {
          setTimeout(() => modalSearchInput.focus(), 100);
      }
  }

  function closeModal() {
      selectionModal.classList.add('hidden');
      activeModalSlotIndex = null;
  }

  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (selectionModal) {
      selectionModal.addEventListener('click', (e) => {
          if (e.target === selectionModal) closeModal();
      });
  }

  function performModalSearch() {
      const title = modalSearchInput.value.trim();
      if (!title) return;
      if (modalLoadingOverlay) modalLoadingOverlay.style.display = 'flex';
      fetchAndRender(title, modalResultsContainer);
  }

  if (modalSearchBtn) modalSearchBtn.addEventListener('click', performModalSearch);
  window.addEventListener('triggerModalSearch', performModalSearch);
  if (modalSearchInput) {
      modalSearchInput.addEventListener('keydown', (e) => {
          if (e.key === 'Enter') {
              e.preventDefault();
              performModalSearch();
          }
      });
      modalSearchInput.addEventListener('input', () => {
          if (modalSearchInput.value.trim() === '') {
              modalResultsContainer.innerHTML = '';
              document.getElementById('modalScrollWrapper').style.display = 'none';
          }
      });
  }

  if (findMyMixBtn) {
      findMyMixBtn.addEventListener('click', () => performPoolRecommendation(true));
  }

  function performPoolRecommendation(pushState = true) {
      const validIds = moviePool.filter(m => m !== null).map(m => m.id);
      if (validIds.length < 2) return;

      if (loadingOverlay) loadingOverlay.style.display = 'flex';

      if (pushState) {
          const newUrl = new URL(window.location);
          newUrl.searchParams.set('mode', 'pool');
          newUrl.searchParams.delete('q');
          newUrl.searchParams.delete('recommend_id');
          newUrl.searchParams.delete('recommend_title');
          window.history.pushState({ mode: 'pool' }, '', newUrl);
      }

      // Read current sorts (they work in pool mode too per instructions)
      const sortToggle = document.getElementById('qualitySortToggle');
      const sortMode = (sortToggle && sortToggle.checked) ? 'quality' : 'similarity';
      const strictGenreToggle = document.getElementById('strictGenreToggle');
      const strictGenre = (strictGenreToggle && strictGenreToggle.checked) ? 'true' : 'false';

      fetch('/recommend_multi', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ids: validIds, limit: 50, sort: sortMode, strict_genre: strictGenre })
      })
      .then(res => res.json())
      .then(data => {
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          if (data.error) {
              poolWarning.textContent = "Error: " + data.error;
              poolWarning.classList.remove('hidden');
              poolWarning.classList.remove('pool-hint');
              if (data.error.includes("were excluded")) {
                 setTimeout(() => { poolWarning.classList.add('hidden'); }, 5000);
              }
          } else if (data.results) {
              const poolResContainer = document.getElementById('poolResults') || document.getElementById('results');
              renderMovieCards(data.results, false, poolResContainer);
              const sortControls = document.getElementById('sortControls');
              if (sortControls) {
                  sortControls.classList.remove('hidden');
                  const tmdbToggle = document.getElementById('tmdbApiToggle');
                  if (tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = 'none';
              }
          }
      })
      .catch(err => {
          console.error("Pool fetch error:", err);
          if (loadingOverlay) loadingOverlay.style.display = 'none';
          poolWarning.textContent = "Network error while finding mix. Try again.";
          poolWarning.classList.remove('hidden');
          poolWarning.classList.remove('pool-hint');
      });
  }

});
