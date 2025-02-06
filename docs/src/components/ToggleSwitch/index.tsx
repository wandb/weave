import React, { useEffect, useState } from "react";
import styles from './styles.module.css';

interface ToggleSwitchProps {
  theme: any;
}

const ToggleSwitch: React.FC<ToggleSwitchProps> = ({ theme }) => {
  const [activeButton, setActiveButton] = useState<'python' | 'typescript'>(() => {
    // Check URL first
    const params = new URLSearchParams(window.location.search);
    const urlValue = params.get('programming-language');
    if (urlValue === 'python' || urlValue === 'typescript') {
      return urlValue;
    }

    // Then check localStorage
    const storedValue = localStorage.getItem('docusaurus.tab.programming-language');
    if (storedValue === 'python' || storedValue === 'typescript') {
      return storedValue;
    }

    // Finally check DOM for selected tabs
    const selectedTab = document.querySelector('.tabs__item[aria-selected="true"]');
    if (selectedTab) {
      if (selectedTab.textContent?.includes('Python')) return 'python';
      if (selectedTab.textContent?.includes('TypeScript')) return 'typescript';
    }

    return 'python';
  });

  const handleButtonClick = (language: 'python' | 'typescript') => {
    setActiveButton(language);

    // Update URL parameter
    const url = new URL(window.location.href);
    url.searchParams.set('programming-language', language);
    window.history.pushState({}, '', url);

    // Update localStorage
    localStorage.setItem('docusaurus.tab.programming-language', language);

    // Find and click the corresponding tab
    const tabs = document.querySelectorAll('.tabs__item');
    tabs.forEach((tab) => {
      if (
        (language === 'python' && tab.textContent?.includes('Python')) ||
        (language === 'typescript' && tab.textContent?.includes('TypeScript'))
      ) {
        (tab as HTMLElement).click();
      }
    });
  };

  useEffect(() => {
    const syncWithExistingTabs = () => {
      const selectedTab = document.querySelector('.tabs__item[aria-selected="true"]');
      if (selectedTab && !selectedTab.textContent?.includes(activeButton === 'python' ? 'Python' : 'TypeScript')) {
        if (selectedTab.textContent?.includes('Python')) {
          setActiveButton('python');
        } else if (selectedTab.textContent?.includes('TypeScript')) {
          setActiveButton('typescript');
        }
      }
    };

    // Initial sync
    syncWithExistingTabs();

    // Watch for tab changes
    const observer = new MutationObserver((mutations) => {
      mutations.forEach((mutation) => {
        if (mutation.type === 'attributes' &&
          mutation.attributeName === 'aria-selected' &&
          mutation.target instanceof Element) {
          const isSelected = mutation.target.getAttribute('aria-selected') === 'true';
          if (isSelected) {
            if (mutation.target.textContent?.includes('Python')) {
              setActiveButton('python');
            } else if (mutation.target.textContent?.includes('TypeScript')) {
              setActiveButton('typescript');
            }
          }
        }
      });
    });

    // Observe all tabs
    const tabs = document.querySelectorAll('.tabs__item');
    tabs.forEach(tab => {
      observer.observe(tab, { attributes: true });
    });

    return () => observer.disconnect();
  }, []);

  const buttonStyle = {
    '--button-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-800)' : 'var(--ifm-color-gray-100)',
    '--button-color': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-100)' : 'var(--ifm-color-gray-900)',
    '--button-active-bg': 'var(--ifm-color-primary)',
    '--button-active-color': 'var(--ifm-color-white)',
    '--button-hover-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-700)' : 'var(--ifm-color-gray-200)',
  } as React.CSSProperties;

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