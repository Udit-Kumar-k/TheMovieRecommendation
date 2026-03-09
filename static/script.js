document.addEventListener('DOMContentLoaded', () => {
  const filterBtn = document.querySelector('.filterbtn');
  const filterMenu = document.getElementById('filterMenu'); // Make sure your filter menu has id="filterMenu"
  const resetBtn = document.getElementById('resetFilters'); // Make sure your reset button has id="resetFilters"
  const filterForm = document.getElementById('filterForm'); // Your form must have id="filterForm"

  // Toggle filter menu visibility on filter button click
  filterBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    filterMenu.classList.toggle('show');
  });

  // Prevent clicks inside filter menu from closing it
  filterMenu.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  // Clicking outside the filter menu closes it
  document.addEventListener('click', () => {
    filterMenu.classList.remove('show');
  });

  // Reset all checkboxes when reset button clicked
  resetBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
  });

  // Optionally clear checkboxes on page load
  window.addEventListener('load', () => {
    const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
  });

  // Handle form submit for recommendations
  filterForm.addEventListener('submit', function (e) {
    e.preventDefault();

    const formData = new FormData(this);

    // Collect all selected filters
    const selectedGenres = formData.getAll('genre');
    const selectedCountries = formData.getAll('country');
    const selectedYears = formData.getAll('released');
    // Add more filters like themes and moods here if needed

    // Send filters to backend via POST
    fetch('/recommend', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        genres: selectedGenres,
        countries: selectedCountries,
        released: selectedYears,
        // theme: [], mood: []  <-- add later as needed
      }),
    })
      .then(res => res.json())
      .then(data => {
        console.log('Recommendations:', data);
        // TODO: Update your UI here with results
      })
      .catch(err => {
        console.error('Error fetching recommendations:', err);
      });
  });
  // Handle search button click
  const searchInput = document.querySelector('.searchInput');
  const searchBtn = document.querySelector('.okbtn');
  const loadingOverlay = document.getElementById('loadingOverlay');

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
    window.history.pushState({ query: title }, '', newUrl);

    // Refactored out to avoid duplication with popstate logic
    fetchAndRender(title);
  }

  // Helper function to render cards (used by both search results and recommendations)
  function renderMovieCards(movies, isSearchResult = false) {
    if (loadingOverlay) loadingOverlay.style.display = 'none'; // Dismiss overlay immediately on success
    const resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';

    const sortControls = document.getElementById('sortControls');
    if (sortControls) {
      if (isSearchResult) {
        sortControls.classList.add('hidden');
      } else {
        sortControls.classList.remove('hidden');
      }
    }

    movies.forEach((movie, index) => {
      const card = document.createElement('div');
      card.className = 'movie-card';

      const img = document.createElement('img');
      img.src = movie.poster_path ? `https://image.tmdb.org/t/p/w500${movie.poster_path}` : '/static/icons/fallback.svg';
      img.alt = 'Poster';
      if (!movie.poster_path) img.classList.add('fallback');

      img.onerror = function () {
        this.onerror = null;
        this.src = '/static/icons/fallback.svg';
        this.classList.add('fallback');
      };

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
      if (!isSearchResult && index !== 0 && movie.similarity) {
        const simBadge = document.createElement('div');
        simBadge.className = 'similarity-badge';
        // Ensure it has % sign
        simBadge.textContent = String(movie.similarity).includes('%') ? movie.similarity : `${movie.similarity}%`;
        card.appendChild(simBadge);
      }

      // Add "Selected" badge to the highest match
      if (!isSearchResult && index === 0) {
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
        fetch(`https://api.themoviedb.org/3/movie/${targetId}?api_key=${apiKey}`)
          .then(res => res.json())
          .then(data => {
            if (data.poster_path) {
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

      // Step 2: When a card is clicked...
      card.onclick = () => {
        if (isSearchResult) {
          // If we clicked a search result, trigger the recommendation engine and update the URL!
          const newUrl = new URL(window.location);
          newUrl.searchParams.set('recommend_id', movie.id);
          newUrl.searchParams.set('recommend_title', movie.title);
          window.history.pushState({ recommend_id: movie.id, recommend_title: movie.title }, '', newUrl);

          searchInput.value = movie.title;
          fetchRecommendations(movie.title, movie.id, false); // false = don't show loading overlay if it interrupts scroll
        } else {
          // If we clicked a recommendation, go to its detail page using its UNIQUE ID, not title
          let targetId = movie.id || movie.tmdb_id;
          if (!targetId) {
            console.error("Missing movie ID in payload!", movie);
            alert("Error: Movie ID not found.");
            return;
          }
          window.location.href = `/movie/${targetId}`;
        }
      };

      resultsContainer.appendChild(card);
    });
  }

  // Function to actually trigger the AI Recommendations
  function fetchRecommendations(title, id, showLoading = true) {
    if (showLoading) showLoadingForTwoSeconds();

    // Check user's preferred sort method
    const sortToggle = document.getElementById('qualitySortToggle');
    const sortMode = (sortToggle && sortToggle.checked) ? 'quality' : 'similarity';

    // Pass both title and id. Id helps resolve duplicate titles (like "Parasite").
    // Fetch limit is 20
    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=20&id=${id || ''}&sort=${sortMode}`;

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
    const url = `https://api.themoviedb.org/3/movie/${id}/recommendations?api_key=${apiKey}&language=en-US&page=1`;
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

          return { results: [mockedResults[0], ...similarMovies].slice(0, 21) }; // top item + 20 related
        } else {
          showSimilarMovies(title);
          throw new Error("");
        }
      });
  }

  function showSimilarMovies(query) {
    loadingOverlay.style.display = 'none'; // Hide loading overlay

    const sortControls = document.getElementById('sortControls');
    if (sortControls) sortControls.classList.add('hidden');

    fetch(`/find_similar_movies?q=${encodeURIComponent(query)}`)
      .then(res => res.json())
      .then(data => {
        const resultsContainer = document.getElementById('results');
        resultsContainer.innerHTML = '';

        if (data.length === 0) {
          resultsContainer.innerHTML = `<div class="no-results"><p>No movies found similar to "${query}". Try a different search.</p></div>`;
          return;
        }

        // Show "Did you mean?" section
        const header = document.createElement('div');
        header.className = 'similar-movies-header';
        header.innerHTML = `<h2>Did you mean?</h2><p>We couldn't find an exact match. Here are similar movies:</p>`;
        resultsContainer.appendChild(header);

        data.forEach(movie => {
          const card = document.createElement('div');
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

          // Make card clickable to select this movie
          card.addEventListener('click', () => {
            searchInput.value = movie.display_title;
            performSearch();
          });

          resultsContainer.appendChild(card);
        });
      })
      .catch(err => {
        console.error("Error fetching similar movies:", err);
        resultsContainer.innerHTML = `<div class="no-results"><p>Error finding similar movies. Please try again.</p></div>`;
      });
  }

  // Handle Sort Toggle Change
  const sortToggle = document.getElementById('qualitySortToggle');
  if (sortToggle) {
    sortToggle.addEventListener('change', () => {
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
    }
  });

  // Read URL parameters on initial page load
  const initialParams = new URLSearchParams(window.location.search);
  const initialQuery = initialParams.get('q');
  const initialRecId = initialParams.get('recommend_id');
  const initialRecTitle = initialParams.get('recommend_title');

  if (initialRecId && initialRecTitle) {
    searchInput.value = initialRecTitle;
    fetchRecommendations(initialRecTitle, initialRecId, true);
  } else if (initialQuery) {
    searchInput.value = initialQuery;
    fetchAndRender(initialQuery);
  }

  // Refactored fetch logic to allow reusable calls without pushing state
  function fetchAndRender(title) {
    showLoadingForTwoSeconds();
    const apiKey = window.TMDB_API_KEY || '';
    const url = `https://api.themoviedb.org/3/search/movie?query=${encodeURIComponent(title)}&include_adult=true&language=en-US&page=1&api_key=${apiKey}`;

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
                renderMovieCards(enrichedData.results, true);
              } else {
                showSimilarMovies(title);
              }
            });
        } else {
          showSimilarMovies(title);
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        alert("Network or Server error. Try again later.");
      });
  }

});
