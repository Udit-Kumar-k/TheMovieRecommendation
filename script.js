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

  searchBtn.addEventListener('click', () => {
    const title = searchInput.value.trim();
    if (!title) {
      alert("Please enter a movie title.");
      return;
    }

    const url = `/smart_recommend?title=${encodeURIComponent(title)}&limit=10`;

    fetch(url)
      .then(res => res.json())
      .then(data => {
        if (data.results) {
          console.log("Search Recommendations:", data.results);
          // TODO: Render the results on the page
        } else {
          alert(data.error || data.message || "No results.");
        }
      })
      .catch(err => {
        console.error("Fetch error:", err);
        alert("Server error. Try again later.");
      });
  });

});
