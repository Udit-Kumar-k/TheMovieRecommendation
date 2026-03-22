document.addEventListener('DOMContentLoaded', () => {

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
    if (poolModeActive) {
      if (btnPoolMode) btnPoolMode.classList.add('active');
      if (btnSearchMode) btnSearchMode.classList.remove('active');
      if (searchBarContainer) searchBarContainer.classList.add('hidden');
      if (poolContainer) poolContainer.classList.remove('hidden');
      renderPool();
      const resultsContainer = document.getElementById('results');
      if(resultsContainer && !window.location.search.includes('mode=pool')) resultsContainer.innerHTML = '';
      const sortControls = document.getElementById('sortControls');
      if (sortControls && window.location.search.includes('mode=pool')) {
          sortControls.classList.remove('hidden');
          const tmdbToggle = document.getElementById('tmdbApiToggle');
          if(tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = 'none';
      } else if(sortControls) {
          sortControls.classList.add('hidden');
      }
    } else {
      if (btnSearchMode) btnSearchMode.classList.add('active');
      if (btnPoolMode) btnPoolMode.classList.remove('active');
      if (poolContainer) poolContainer.classList.add('hidden');
      if (searchBarContainer) searchBarContainer.classList.remove('hidden');
      const sortControls = document.getElementById('sortControls');
      if (sortControls && document.getElementById('results').innerHTML.trim() !== '') {
          const tmdbToggle = document.getElementById('tmdbApiToggle');
          if(tmdbToggle && tmdbToggle.parentElement) tmdbToggle.parentElement.style.display = 'flex';
      }
    }
  }

  if (btnSearchMode) {
    btnSearchMode.addEventListener('click', () => {
      poolModeActive = false;
      updateModeUI();
    });
  }

  if (btnPoolMode) {
    btnPoolMode.addEventListener('click', () => {
      poolModeActive = true;
      updateModeUI();
    });
  }

  updateModeUI();

  function showLoadingForTwoSeconds() {
    if (loadingOverlay) {
      loadingOverlay.style.display = 'flex';
      setTimeout(() => {
        loadingOverlay.style.display = 'none';
      }, 2000);
    }
  }

  function performSearch() {
    const title = searchInput.value.trim();
    if (!title) {
      alert("Please enter a movie search term.");
      return;
    }

    showLoadingForTwoSeconds();

    // Update URL so the Back button works
    const newUrl = new URL(window.location);
    newUrl.searchParams.set('q', title);
    // Ensure we drop any recommendation parameters from the URL when doing a raw search!
    newUrl.searchParams.delete('recommend_id');
    newUrl.searchParams.delete('recommend_title');
    newUrl.searchParams.delete('mode');
    window.history.pushState({ query: title }, '', newUrl);

    // Refactored out to avoid duplication with popstate logic
    fetchAndRender(title);
  }

  // Helper function to render cards (used by both search results and recommendations)
  function renderMovieCards(movies, isSearchResult = false, targetContainer = null) {
    const isModal = targetContainer === modalResultsContainer;
    const container = targetContainer || document.getElementById('results');

    if (isModal) {
      document.getElementById('modalScrollWrapper').style.display = 'block';
    }

    if (!isModal && loadingOverlay) loadingOverlay.style.display = 'none'; // Dismiss overlay immediately on success
    if (isModal && modalLoadingOverlay) modalLoadingOverlay.style.display = 'none';

    container.innerHTML = '';

    const sortControls = document.getElementById('sortControls');
    if (sortControls && !isModal) {
      if (isSearchResult) {
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
      const card = document.createElement('div');
      card.className = 'movie-card';

      // Default to what the backend thinks or a placeholder
      let img;
      img = document.createElement('img');
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

      // Create hovering overlay
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

      // Similarity Badge (Only for recommendations, exclude the top exact match)
      if (!isSearchResult && index !== 0 && movie.similarity && !poolModeActive) {
        const simBadge = document.createElement('div');
        simBadge.className = 'similarity-badge';
        // Ensure it has % sign
        simBadge.textContent = String(movie.similarity).includes('%') ? movie.similarity : `${movie.similarity}%`;
        card.appendChild(simBadge);
      } else if (!isSearchResult && movie.similarity && poolModeActive) {
        // In pool mode, show similarity on all returned cards!
        const simBadge = document.createElement('div');
        simBadge.className = 'similarity-badge';
        simBadge.textContent = String(movie.similarity).includes('%') ? movie.similarity : `${movie.similarity}%`;
        card.appendChild(simBadge);
      }

      // Add "Selected" badge to the highest match
      if (!isSearchResult && index === 0 && !poolModeActive) {
        card.classList.add('selected');
        const badge = document.createElement('div');
        badge.className = 'selected-badge';
        badge.textContent = 'Selected';
        card.appendChild(badge);
      }

      // Live TMDB Data Fetch on render (removes local CSV dependency)
      const targetId = movie.id || movie.tmdb_id;
      if (targetId) {
        const apiKey = window.TMDB_API_KEY || '';
        const apiBase = window.TMDB_API_BASE || 'https://api.tmdb.org/3';
        fetch(`${apiBase}/movie/${targetId}?api_key=${apiKey}`)
          .then(res => res.json())
          .then(data => {
            // Live TMDB Adult overriding
            if (data.adult === true) {
              img.src = '/static/icons/18_up_rating_24dp_8B1A10_FILL0_wght400_GRAD0_opsz24.svg';
              img.classList.add('fallback');
            } else if (data.poster_path && img.src.includes('fallback.svg') && !img.src.includes('18_up')) {
              // Only override with poster if it wasn't already caught by the local adult flag
              img.src = `https://image.tmdb.org/t/p/w500${data.poster_path}`;
              img.classList.remove('fallback');
            }
            if (data.vote_average) {
              hoverRating.querySelector('.rating-value').textContent = data.vote_average.toFixed(1);
            } else {
              hoverRating.querySelector('.rating-value').textContent = 'NR';
            }
            if (data.title) {
              hoverTitle.textContent = data.title;
            }
            if (data.overview) {
              hoverOverview.textContent = data.overview;
            }
          })
          .catch(() => {
            if (hoverRating.querySelector('.rating-value').textContent === '--') {
              hoverRating.querySelector('.rating-value').textContent = 'NR';
            }
          });
      }

      if (isModal) {
        const alreadySelected = moviePool.some(m => m && String(m.id) === String(targetId));
        if (alreadySelected) {
          card.classList.add('disabled');
        }
      }

      // Step 2: When a card is clicked...
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
          
          const mainRes = document.getElementById('results');
          if (mainRes) mainRes.innerHTML = '';
          const sc = document.getElementById('sortControls');
          if (sc) sc.classList.add('hidden');
          
          renderPool();
        } else if (isSearchResult) {
          // If we clicked a search result, trigger the recommendation engine and update the URL!
          const newUrl = new URL(window.location);
          newUrl.searchParams.set('recommend_id', movie.id);
          newUrl.searchParams.set('recommend_title', movie.title);
          newUrl.searchParams.delete('mode');
          window.history.pushState({ recommend_id: movie.id, recommend_title: movie.title }, '', newUrl);

          searchInput.value = movie.title;
          fetchRecommendations(movie.title, movie.id, false); // false = don't show loading overlay if it interrupts scroll
        } else {
          // If we clicked a recommendation, go to its detail page using its UNIQUE ID, not title
          let urlTargetId = movie.id || movie.tmdb_id;
          if (!urlTargetId) {
            console.error("Missing movie ID in payload!", movie);
            alert("Error: Movie ID not found.");
            return;
          }
          window.location.href = `/movie/${urlTargetId}`;
        }
      };

      container.appendChild(card);
    });
  }

  // Function to actually trigger the AI Recommendations
  function fetchRecommendations(title, id, showLoading = true) {
    if (showLoading) showLoadingForTwoSeconds();

    // Check TMDB API Override
    const tmdbToggle = document.getElementById('tmdbApiToggle');
    if (tmdbToggle && tmdbToggle.checked) {
      if (id) {
        console.log("TMDB API Toggle ON - Bypassing FAISS and fetching from TMDB directly...");
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

    // Check user's preferred sort method
    const sortToggle = document.getElementById('qualitySortToggle');
    const sortMode = (sortToggle && sortToggle.checked) ? 'quality' : 'similarity';

    // Check strict genre preference
    const strictGenreToggle = document.getElementById('strictGenreToggle');
    const strictGenre = (strictGenreToggle && strictGenreToggle.checked) ? 'true' : 'false';

    // Pass both title and id. Id helps resolve duplicate titles (like "Parasite").
    // Fetch limit is 50
    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=50&id=${id || ''}&sort=${sortMode}&strict_genre=${strictGenre}`;

    fetch(url)
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            if (res.status === 404) {
              // Fallback: If not found in local index, fetch directly from TMDB API Recommendations
              if (id) {
                console.log(`Movie ID ${id} not found in local index. Falling back to TMDB recommendations...`);
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
        // If the inner layer threw an error (e.g. TMDB fallback returning nothing), data might be undefined
        if (data && data.results && data.results.length > 0) {
          console.log("Recommendations:", data.results);
          renderMovieCards(data.results, false); // false = these are recommendations
        }
      })
      .catch(err => {
        if (err.message === "") return;
        console.error("Fetch errors:", err);
        // Only alert if we totally failed and didn't trigger `showSimilarMovies`
      });
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

    if (!isModal && loadingOverlay) loadingOverlay.style.display = 'none';
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

    if (mode === 'pool') {
        poolModeActive = true;
        updateModeUI();
        const validIds = moviePool.filter(m => m !== null).map(m => m.id);
        if (validIds.length >= 2) performPoolRecommendation(false);
    } else {
        if (poolModeActive) {
            poolModeActive = false;
            updateModeUI();
        }
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

  if (initialMode === 'pool') {
      poolModeActive = true;
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
        showLoadingForTwoSeconds();
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
                  document.getElementById('results').innerHTML = ''; // Clear results if shown
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
              renderMovieCards(data.results, false, null);
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
