document.addEventListener('DOMContentLoaded', () => {
    const filterBtn = document.querySelector('.filterbtn');
    const filterMenu = document.getElementById('filterMenu'); // Ensure your HTML element has id="filterMenu"
    const resetBtn = document.getElementById('resetFilters'); // Ensure your reset button has id="resetFilters"
    const searchBar = document.querySelector('.searchBar'); // Assuming this is used elsewhere

    filterBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        filterMenu.classList.toggle('show');
    });

    resetBtn.addEventListener('click', (event) => {
        event.stopPropagation();
        const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
    });

    // CRITICAL FIX: Stop clicks inside the menu from propagating to document
    filterMenu.addEventListener('click', (event) => {
        event.stopPropagation();
    });

    window.addEventListener('load', () => {
        const checkboxes = filterMenu.querySelectorAll('input[type="checkbox"]');
        checkboxes.forEach(cb => cb.checked = false);
    });
});