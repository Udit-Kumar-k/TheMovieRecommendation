const searchInput = document.getElementById('searchInput');
const suggestionsList = document.getElementById('suggestions');
const ghostText = document.getElementById('ghostText');
const didYouMean = document.getElementById('didYouMean');
const searchBtn = document.getElementById('searchBtn');

// Simulated list of movies (replace with dynamic data or API in production)
const movies = [
  "Avengers: Endgame", "Avatar", "Titanic", "The Dark Knight",
  "Avengers: Infinity War", "Interstellar", "Inception",
  "The Matrix", "The Godfather", "Gladiator", "Toy Story"
];

function getSuggestions(input) {
  if (!input) return [];
  return movies.filter(movie =>
    movie.toLowerCase().startsWith(input.toLowerCase())
  );
}

function getClosestMatch(input) {
  let bestMatch = "";
  let minDistance = Infinity;

  for (const movie of movies) {
    const distance = levenshteinDistance(input.toLowerCase(), movie.toLowerCase());
    if (distance < minDistance) {
      minDistance = distance;
      bestMatch = movie;
    }
  }
  return bestMatch;
}
// 🔧 Filter Toggle Script
document.addEventListener("DOMContentLoaded", function () {
  const filterBtn = document.querySelector('.filterbtn');
  const filterMenu = document.getElementById('filterMenu');

  if (filterBtn && filterMenu) {
    filterBtn.addEventListener('click', () => {
      filterMenu.classList.toggle('show');
    });
  }
});


function levenshteinDistance(a, b) {
  const matrix = Array.from({ length: a.length + 1 }, (_, i) => [i, ...Array(b.length).fill(0)]);

  for (let j = 1; j <= b.length; j++) matrix[0][j] = j;

  for (let i = 1; i <= a.length; i++) {
    for (let j = 1; j <= b.length; j++) {
      matrix[i][j] = a[i - 1] === b[j - 1]
        ? matrix[i - 1][j - 1]
        : Math.min(matrix[i - 1][j] + 1, matrix[i][j - 1] + 1, matrix[i - 1][j - 1] + 1);
    }
  }

  return matrix[a.length][b.length];
}

searchInput.addEventListener('input', () => {
  const query = searchInput.value;
  const suggestions = getSuggestions(query);
  suggestionsList.innerHTML = "";

  if (suggestions.length) {
    suggestions.forEach(movie => {
      const li = document.createElement("li");
      li.textContent = movie;
      li.addEventListener("click", () => {
        searchInput.value = movie;
        ghostText.textContent = "";
        suggestionsList.innerHTML = "";
        performSearch(movie);
      });
      suggestionsList.appendChild(li);
    });

    const firstSuggestion = suggestions[0];
    if (firstSuggestion.toLowerCase().startsWith(query.toLowerCase())) {
      ghostText.textContent = firstSuggestion.substring(query.length);
    } else {
      ghostText.textContent = "";
    }
  } else {
    ghostText.textContent = "";
  }
});

searchInput.addEventListener("keydown", (e) => {
  if (e.key === "Tab" && ghostText.textContent) {
    e.preventDefault();
    searchInput.value += ghostText.textContent;
    ghostText.textContent = "";
    suggestionsList.innerHTML = "";
  }
});

searchBtn.addEventListener("click", () => {
  const query = searchInput.value.trim();
  const bestMatch = getClosestMatch(query);

  if (query && bestMatch.toLowerCase() !== query.toLowerCase()) {
    didYouMean.innerHTML = `Did you mean: <strong>${bestMatch}</strong>?`;
  } else {
    didYouMean.innerHTML = "";
  }

  performSearch(bestMatch);
});

function performSearch(movieName) {
  // Placeholder: Replace with your backend query or display logic
  const results = document.getElementById('results');
  results.innerHTML = `<p>Showing results for <strong>${movieName}</strong></p>`;
}
