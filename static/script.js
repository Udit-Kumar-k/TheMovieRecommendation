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
      alert("Please enter a movie title.");
      return;
    }

    showLoadingForTwoSeconds(); // Show loader for exactly 2 seconds

    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=20`;

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
      resultsContainer.innerHTML = ''; // Clear previous results



  data.results.forEach((movie, index) => {
  const card = document.createElement('div');
  card.className = 'movie-card';

  // 🟡 Add "Selected" badge to the first movie
  if (index === 0) {
    card.classList.add('selected');
    const badge = document.createElement('div');
    badge.className = 'selected-badge';
    badge.textContent = 'Selected';
    card.appendChild(badge);
  }

  // Create image
  let img;
  if (movie.adult === 'TRUE') {
    // 🚩 Imprinting: Show 18+ icon for adult movies, no zoom/crop, object-fit: contain
    img = document.createElement('img');
    img.src = '/static/icons/18_up_rating_24dp_000000_FILL0_wght400_GRAD0_opsz24.svg';
    img.alt = '18+ Poster';
    img.classList.add('fallback'); // fallback class ensures object-fit: contain and background
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

  // Create title
  const title = document.createElement('h3');
  title.textContent = movie.title || 'Untitled Movie';

  // Create genres
  const genres = document.createElement('p');
  genres.innerHTML = `<strong>Genres:</strong> ${movie.genres || 'N/A'}`;

// Truncate overview to 3–4 lines and add "..."
const overview = document.createElement('p');
overview.className = 'overview';

const cleanText = (movie.overview || 'No description available.').replace(/\n/g, ' ');

// Set as innerHTML: bold "Overview:" followed by plain text
overview.innerHTML = `<strong>Overview:</strong> ${cleanText}`;

  // Rating and similarity
  const rating = document.createElement('p');
  rating.innerHTML = `<strong>Rating:</strong> ${movie.vote_average || 'N/A'}`;

  const similarity = document.createElement('p');
  similarity.innerHTML = `<strong>Similarity:</strong> ${movie.similarity}`;

  // ✅ Make the whole card clickable
  card.onclick = () => {
    window.location.href = `/movie/${encodeURIComponent(movie.title)}`;
  };


  // Append everything
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

// Trigger search on Enter key press
searchInput.addEventListener('keydown', (event) => {
  if (event.key === 'Enter') {
    event.preventDefault();
    performSearch();
  }
});

});
