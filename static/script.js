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

    // Directly query TMDB from the frontend using the exposed API key
    const apiKey = window.TMDB_API_KEY || '';
    const url = `https://api.themoviedb.org/3/search/movie?query=${encodeURIComponent(title)}&include_adult=true&language=en-US&page=1&api_key=${apiKey}`;

    fetch(url, {
      headers: {
        'accept': 'application/json'
      }
    })
      .then(res => {
        if (!res.ok) {
          throw new Error("Failed to fetch from TMDB");
        }
        return res.json();
      })
      .then(data => {
        if (data.results && data.results.length > 0) {
          // We need to fetch local matching data to get similarity, exact matching stats, etc.
          // Since we can't do this purely frontend, let's POST the raw TMDB results to the backend to filter/enrich
          return fetch('/enrich_tmdb_results', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ results: data.results.slice(0, 15) })
          })
            .then(res => res.json())
            .then(enrichedData => {
              if (enrichedData.results && enrichedData.results.length > 0) {
                console.log("Enriched Search Results:", enrichedData.results);
                renderMovieCards(enrichedData.results, true);
              } else {
                showSimilarMovies(title);
              }
            });
        } else {
          showSimilarMovies(title); // Fallback
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        alert("Network or Server error. Try again later.");
      });
  }

  // Helper function to render cards (used by both search results and recommendations)
  function renderMovieCards(movies, isSearchResult = false) {
    const resultsContainer = document.getElementById('results');
    resultsContainer.innerHTML = '';

    movies.forEach((movie, index) => {
      const card = document.createElement('div');
      card.className = 'movie-card';

      // Add "Selected" badge to the first movie ONLY if these are recommendations (not search results)
      if (!isSearchResult && index === 0) {
        card.classList.add('selected');
        const badge = document.createElement('div');
        badge.className = 'selected-badge';
        badge.textContent = 'Selected';
        card.appendChild(badge);
      } else if (isSearchResult) {
        // Optional: Add a subtle badge to indicate it's a search result lookup
        card.classList.add('search-result-card');
      }

      let img;
      if (movie.adult === 'TRUE') {
        img = document.createElement('img');
        img.src = '/static/icons/18_up_rating_24dp_8B1A10_FILL0_wght400_GRAD0_opsz24.svg';
        img.alt = '18+ Poster';
        img.classList.add('fallback');
      } else {
        img = document.createElement('img');
        img.src = `https://image.tmdb.org/t/p/w500${movie.poster_path || ''}`;
        img.alt = 'Poster';
        img.onerror = function () {
          this.onerror = null;
          this.src = '/static/icons/fallback.svg';
          this.classList.add('fallback');
        };
      }

      const title = document.createElement('h3');
      title.textContent = movie.title || 'Untitled Movie';

      const genres = document.createElement('p');
      genres.innerHTML = `<strong>Genres:</strong> ${movie.genres || 'N/A'}`;

      const overview = document.createElement('p');
      overview.className = 'overview';
      const cleanText = (movie.overview || 'No description available.').replace(/\n/g, ' ');
      overview.innerHTML = `<strong>Overview:</strong> ${cleanText}`;

      const rating = document.createElement('p');
      rating.innerHTML = `<strong>Rating:</strong> ${movie.vote_average || 'N/A'}`;

      const similarity = document.createElement('p');
      similarity.innerHTML = `<strong>Similarity:</strong> ${movie.similarity}`;

      // Step 2: When a card is clicked...
      card.onclick = () => {
        if (isSearchResult) {
          // If we clicked a search result, populate the input and trigger the recommendation engine!
          searchInput.value = movie.title;
          fetchRecommendations(movie.title, movie.id);
        } else {
          // If we clicked a recommendation, go to its detail page
          window.location.href = `/movie/${encodeURIComponent(movie.title)}`;
        }
      };

      card.appendChild(img);
      card.appendChild(title);
      card.appendChild(genres);
      card.appendChild(overview);
      card.appendChild(rating);
      card.appendChild(similarity);

      resultsContainer.appendChild(card);
    });
  }

  // Function to actually trigger the AI Recommendations
  function fetchRecommendations(title, id) {
    showLoadingForTwoSeconds();
    // Pass both title and id. Id helps resolve duplicate titles (like "Parasite").
    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=20&id=${id || ''}`;

    fetch(url)
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            if (res.status === 404) {
              showSimilarMovies(title);
              throw new Error("");
            }
            throw new Error(err.error || "An unexpected error occurred.");
          });
        }
        return res.json();
      })
      .then(data => {
        if (data.results && data.results.length > 0) {
          console.log("Recommendations:", data.results);
          renderMovieCards(data.results, false); // false = these are recommendations
        }
      })
      .catch(err => {
        if (err.message === "") return;
        console.error("Fetch errors:", err);
        alert("Server error. Try again later.");
      });
  }

  function showSimilarMovies(query) {
    loadingOverlay.style.display = 'none'; // Hide loading overlay

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

  // Handle Search button and Enter key
  searchBtn.addEventListener('click', performSearch);

  // Trigger search on Enter key press
  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      performSearch();
    }
  });

});
