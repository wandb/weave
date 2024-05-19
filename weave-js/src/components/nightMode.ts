export const isInNightMode = (): boolean => {
  return document.documentElement.classList.contains('night-mode');
};
