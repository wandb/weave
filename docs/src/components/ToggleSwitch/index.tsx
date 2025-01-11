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
    const syncWithTabs = () => {
      const tabElements = document.querySelectorAll('.tabs__item');
      if (tabElements.length === 0) return; // Exit if no tabs found

      // Find currently selected tab and sync state
      const selectedTab = Array.from(tabElements).find(
        tab => tab.getAttribute('aria-selected') === 'true'
      );
      if (selectedTab) {
        if (selectedTab.textContent?.includes('Python')) {
          setActiveButton('python');
        } else if (selectedTab.textContent?.includes('TypeScript')) {
          setActiveButton('typescript');
        }
      }
    };

    // Initial sync with URL parameter
    const params = new URLSearchParams(window.location.search);
    const currentLanguage = params.get('programming-language') as 'python' | 'typescript';
    if (currentLanguage && currentLanguage !== activeButton) {
      setActiveButton(currentLanguage);
    }

    // Initial sync with tabs
    syncWithTabs();

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
              const url = new URL(window.location.href);
              url.searchParams.set('programming-language', 'python');
              window.history.pushState({}, '', url);
            } else if (isTypeScript) {
              setActiveButton('typescript');
              const url = new URL(window.location.href);
              url.searchParams.set('programming-language', 'typescript');
              window.history.pushState({}, '', url);
            }
          }
        }
      });
    });

    // Set up observer for tabs container to detect when tabs become available
    const tabsObserver = new MutationObserver(() => {
      const tabElements = document.querySelectorAll('.tabs__item');
      if (tabElements.length > 0) {
        tabElements.forEach((tab) => {
          observer.observe(tab, { attributes: true, attributeFilter: ['aria-selected'] });
        });
        syncWithTabs();
      }
    });

    // Observe the document body for changes
    tabsObserver.observe(document.body, { childList: true, subtree: true });

    // Observe existing tabs if any
    const existingTabs = document.querySelectorAll('.tabs__item');
    existingTabs.forEach((tab) => {
      observer.observe(tab, { attributes: true, attributeFilter: ['aria-selected'] });
    });

    // Cleanup observers on component unmount
    return () => {
      observer.disconnect();
      tabsObserver.disconnect();
    };
  }, []);

  const buttonStyle = {
    '--button-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-800)' : 'var(--ifm-color-gray-100)',
    '--button-color': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-100)' : 'var(--ifm-color-gray-900)',
    '--button-active-bg': 'var(--ifm-color-primary)',
    '--button-active-color': 'var(--ifm-color-white)',
    '--button-hover-bg': theme.colorMode === 'dark' ? 'var(--ifm-color-gray-700)' : 'var(--ifm-color-gray-200)',
  } as React.CSSProperties;

  const handleButtonClick = (language: 'python' | 'typescript') => {
    setActiveButton(language);

    // Update URL parameter
    const url = new URL(window.location.href);
    url.searchParams.set('programming-language', language);
    window.history.pushState({}, '', url);

    // Find and click the corresponding tab if available
    const tabElements = document.querySelectorAll('.tabs__item');
    if (tabElements.length > 0) {
      tabElements.forEach((tab) => {
        if (
          (language === 'python' && tab.textContent?.includes('Python')) ||
          (language === 'typescript' && tab.textContent?.includes('TypeScript'))
        ) {
          (tab as HTMLElement).click();
        }
      });
    }
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