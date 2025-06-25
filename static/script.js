document.addEventListener('DOMContentLoaded', () => {
  const filterBtn = document.querySelector('.filterbtn');
  const filterMenu = document.getElementById('filterMenu');
  const resetBtn = document.getElementById('resetFilters');
  const filterForm = document.getElementById('filterForm');

  filterBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    filterMenu.classList.toggle('show');
  });

  filterMenu.addEventListener('click', (event) => {
    event.stopPropagation();
  });

  document.addEventListener('click', () => {
    filterMenu.classList.remove('show');
  });

  resetBtn.addEventListener('click', (event) => {
    event.stopPropagation();
    const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
  });

  window.addEventListener('load', () => {
    const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => cb.checked = false);
  });

  filterForm.addEventListener('submit', function (e) {
    e.preventDefault();
    const formData = new FormData(this);
    const selectedGenres = formData.getAll('genre');
    const selectedCountries = formData.getAll('country');
    const selectedYears = formData.getAll('released');

    fetch('/recommend', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        genres: selectedGenres,
        countries: selectedCountries,
        released: selectedYears,
      }),
    })
    .then(res => res.json())
    .then(data => {
      console.log('Recommendations:', data);
      // TODO: Handle results if needed
    })
    .catch(err => {
      console.error('Error fetching recommendations:', err);
    });
  });

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
      alert("Please enter a movie title.");
      return;
    }

    showLoadingForTwoSeconds();

    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=10`;

    fetch(url)
      .then(res => {
        if (!res.ok) {
          return res.json().then(err => {
            throw new Error(err.error || "An unexpected error occurred.");
          });
        }
        return res.json();
      })
      .then(data => {
        if (data.results && data.results.length > 0) {
          console.log("Search Recommendations:", data.results);
          const resultsContainer = document.getElementById('results');
          resultsContainer.innerHTML = '';

          data.results.forEach((movie, index) => {
            const card = document.createElement('div');
            card.className = 'movie-card';

            if (index === 0) {
              const badge = document.createElement('div');
              badge.className = 'selected-badge';
              badge.textContent = 'Selected';
              card.appendChild(badge);
            }

            const img = document.createElement('img');
            img.className = 'movie-poster';
            img.src = `https://image.tmdb.org/t/p/w500${movie.poster_path || ''}`;
            img.alt = 'Poster';
            img.onerror = function () {
              this.onerror = null;
              this.src = '/static/icons/fallback.svg';
            };
            img.setAttribute('data-blur', movie.adult ? 'true' : 'false');

            if (movie.adult) {
              img.style.display = 'none';

              const blackOverlay = document.createElement('div');
              blackOverlay.className = 'black-overlay';

              const badge18 = document.createElement('div');
              badge18.className = 'badge-18';
              badge18.textContent = '18+';

              blackOverlay.appendChild(badge18);
              card.appendChild(blackOverlay);
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

            // ✅ Final click behavior — show modal
            card.onclick = (e) => {
              if (e.target.classList.contains('movie-poster') && e.target.getAttribute('data-blur') === 'true') return;

              const overlay = document.getElementById('movieOverlay');
              const content = document.getElementById('movieDetailContent');

              overlay.classList.remove('hidden');
              content.innerHTML = 'Loading...';

              fetch(`/movie_detail?title=${encodeURIComponent(movie.title)}`)
                .then(res => res.text())
                .then(html => {
                  content.innerHTML = html;
                })
                .catch(() => {
                  content.innerHTML = 'Failed to load details.';
                });
            };

            card.appendChild(img);
            card.appendChild(title);
            card.appendChild(genres);
            card.appendChild(overview);
            card.appendChild(rating);
            card.appendChild(similarity);

            resultsContainer.appendChild(card);
          });
        } else {
          alert(data.error || data.message || "No results.");
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        alert("Server error. Try again later.");
      });
  }

  searchBtn.addEventListener('click', performSearch);

  searchInput.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      performSearch();
    }
  });

  // ✅ Close popup
  document.addEventListener('click', function (e) {
    if (e.target.classList.contains('close-popup')) {
      document.getElementById('movieOverlay').classList.add('hidden');
    }
  });
});
