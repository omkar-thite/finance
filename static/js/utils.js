// Apply saved theme immediately on page load to avoid flash
(function () {
    if (localStorage.getItem('theme') === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }
}());

function toggleDarkMode() {
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    if (isDark) {
        document.documentElement.removeAttribute('data-theme');
        localStorage.setItem('theme', 'light');
    } else {
        document.documentElement.setAttribute('data-theme', 'dark');
        localStorage.setItem('theme', 'dark');
    }
    updateToggleIcon();
}

function updateToggleIcon() {
    const btn = document.getElementById('theme-toggle');
    if (!btn) return;
    btn.textContent = document.documentElement.getAttribute('data-theme') === 'dark' ? '\u2600' : '\u263D';
}

document.addEventListener('DOMContentLoaded', function () {
    updateToggleIcon();
    const btn = document.getElementById('theme-toggle');
    if (btn) btn.addEventListener('click', toggleDarkMode);

    const greetingEl = document.getElementById('greeting-msg');
    if (greetingEl) greetingEl.textContent = getGreeting();
});
