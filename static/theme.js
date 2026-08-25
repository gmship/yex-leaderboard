(() => {
  const storageKey = 'yex-color-theme';
  const root = document.documentElement;

  const readTheme = () => {
    try {
      const savedTheme = window.localStorage.getItem(storageKey);
      return savedTheme === 'light' || savedTheme === 'dark' ? savedTheme : 'dark';
    } catch {
      return 'dark';
    }
  };

  const applyTheme = (theme) => {
    const isLight = theme === 'light';
    root.dataset.theme = theme;
    root.style.colorScheme = theme;
    document.querySelectorAll('.js-theme-toggle').forEach((button) => {
      const nextTheme = isLight ? 'dark' : 'light';
      const label = `Switch to ${nextTheme} theme`;
      button.setAttribute('aria-label', label);
      button.setAttribute('aria-pressed', String(isLight));
      button.title = label;
    });
  };

  applyTheme(readTheme());

  document.addEventListener('DOMContentLoaded', () => {
    applyTheme(root.dataset.theme || 'dark');
    document.querySelectorAll('.js-theme-toggle').forEach((button) => {
      button.addEventListener('click', () => {
        const theme = root.dataset.theme === 'light' ? 'dark' : 'light';
        applyTheme(theme);
        try {
          window.localStorage.setItem(storageKey, theme);
        } catch {
          // The toggle still works for this page when storage is unavailable.
        }
      });
    });
  });
})();
