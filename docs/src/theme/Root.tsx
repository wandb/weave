import React from 'react';
import ToggleSwitch from '@site/src/components/ToggleSwitch';
import { createRoot } from 'react-dom/client';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';

export default function Root({ children }) {
    const { siteConfig } = useDocusaurusContext();
    const theme = siteConfig.themeConfig;

    React.useEffect(() => {
        const container = document.getElementById('programming-language-toggle');
        if (container) {
            const root = createRoot(container);
            root.render(<ToggleSwitch theme={theme} />);
        }
    }, [theme]);

    return <>{children}</>;
}