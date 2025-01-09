import React, { useEffect, useState } from "react";
import styles from './styles.module.css';

interface ToggleSwitchProps {
  theme: any;
}

const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ theme }) => {
  const [activeButton, setActiveButton] = useState<'python' | 'typescript'>(() => {
    const params = new URLSearchParams(window.location.search);
    return (params.get('programming-language') as 'python' | 'typescript') || 'python';
  });

  useEffect(() => {
    // Add mutation observer to watch for tab changes
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.target instanceof Element) {
          const isSelected = mutation.target.getAttribute('aria-selected') === 'true';
          if (isSelected) {
            const isPython = mutation.target.textContent?.includes('Python');
            const isTypeScript = mutation.target.textContent?.includes('TypeScript');

            if (isPython) {
              setActiveButton('python');
              // Update parameter name to match tabs
              const url = new URL(window.location.href);
              url.searchParams.set('programming-language', 'python');
              window.history.pushState({}, '', url);
            } else if (isTypeScript) {
              setActiveButton('typescript');
              // Update parameter name to match tabs
              const url = new URL(window.location.href);
              url.searchParams.set('programming-language', 'typescript');
              window.history.pushState({}, '', url);
            }
          }
        }
      });
    });

    // Observe all tab elements
    const tabElements = document.querySelectorAll('.tabs__item');
    tabElements.forEach((tab) => {
      observer.observe(tab, { attributes: true, attributeFilter: ['aria-selected'] });
    });

    // Initial sync of tabs with toggle state
    tabElements.forEach((tab) => {
      if (tab.textContent?.includes('Python') && activeButton === 'python') {
        tab.setAttribute('aria-selected', 'true');
        tab.classList.add('tabs__item--active');
        tab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      } else if (tab.textContent?.includes('TypeScript') && activeButton === 'typescript') {
        tab.setAttribute('aria-selected', 'true');
        tab.classList.add('tabs__item--active');
        tab.dispatchEvent(new MouseEvent('click', { bubbles: true }));
      } else {
        tab.setAttribute('aria-selected', 'false');
        tab.classList.remove('tabs__item--active');
      }
    });

    // Cleanup observer on component unmount
    return () => observer.disconnect();
  }, [activeButton]);

  const buttonStyle = {
    '--button-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-800)' : 'var(--ifm-color-gray-100)',
    '--button-color': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-100)' : 'var(--ifm-color-gray-900)',
    '--button-active-bg': 'var(--ifm-color-primary)',
    '--button-active-color': 'var(--ifm-color-white)',
    '--button-hover-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-700)' : 'var(--ifm-color-gray-200)',
  } as React.CSSProperties;

  const handleButtonClick = (language: 'python' | 'typescript') => {
    setActiveButton(language);
    // Update parameter name to match tabs
    const url = new URL(window.location.href);
    url.searchParams.set('programming-language', language);
    window.history.pushState({}, '', url);
  };

  return (
    <div className={styles.toggleSwitch} style={buttonStyle}>
      <button
        className={`${styles.toggleButton} ${activeButton === 'python' ? styles.active : ''}`}
        onClick={() => handleButtonClick('python')}
      >
        🐍 Python
      </button>
      <button
        className={`${styles.toggleButton} ${activeButton === 'typescript' ? styles.active : ''}`}
        onClick={() => handleButtonClick('typescript')}
      >
        💠 TypeScript
      </button>
    </div>
  );
};

export default ToggleSwitch;