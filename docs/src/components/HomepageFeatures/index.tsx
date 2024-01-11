import React from 'react';
import clsx from 'clsx';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  subtitle: string;
  link: string;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Introduction',
    subtitle: 'Start here',
    link: '/intro',
  },
  {
    title: 'Quickstart',
    subtitle: 'Get up and running with a short example',
    link: '/quickstart',
  }
];

function Feature({ title, subtitle, link }: FeatureItem) {
  return (
    <a
      href={link}
      className={clsx('col col--4', styles.featureButton)}>
      <div style={{ display: 'flex', flexDirection: 'column', justifyContent: 'flex-end', alignItems: 'flex-start' }}>
        <h3>{title}</h3>
        <p>{subtitle}</p>
      </div>
    </a>
  );
}

export default function HomepageFeatures(): JSX.Element {
  return (
    <section className={styles.features}>
      <div className={styles.container}>
      <h2 className={styles.title}>Get Started</h2>
        <div className={styles.row}>
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
