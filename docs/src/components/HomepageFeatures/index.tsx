import React from "react";
import clsx from "clsx";
import styles from "./styles.module.css";

type FeatureItem = {
  title: string;
  subtitle: string;
  link: string;
  background: string;
};

const FeatureList: FeatureItem[] = [
  {
    title: "Try Weave",
    subtitle: "Track your first LLM application",
    link: "/quickstart",
    background: "linear-gradient(135deg, #6e8efb, #a777e3)",
  },
  {
    title: "Why Weave?",
    subtitle: "Learn what problems Weave helps with",
    link: "/introduction",
    background: "linear-gradient(135deg, #fb6ef2, #e377a4)",
  },
];

function Feature({ title, subtitle, link, background }: FeatureItem) {
  return (
    <a
      href={link}
      className={clsx("col col--4", styles.featureButton)}
      style={{ background: background }}
    >
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          justifyContent: "flex-end",
          alignItems: "flex-start",
        }}
      >
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
