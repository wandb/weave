import type * as Preset from "@docusaurus/preset-classic";
import type { Config } from "@docusaurus/types";
import type * as OpenApiPlugin from "docusaurus-plugin-openapi-docs";
import { themes as prismThemes } from "prism-react-renderer";

const config: Config = {
  title: "W&B Weave",
  tagline: "Confidently ship LLM applications.",
  favicon: "img/favicon.ico",

  // Set the production url of your site here
  url: "https://weave-docs.wandb.ai",
  // Set the /<baseUrl>/ pathname under which your site is served
  // For GitHub pages deployment, it is often '/<projectName>/'
  baseUrl: "/",

  // GitHub pages deployment config.
  // If you aren't using GitHub pages, you don't need these.
  organizationName: "wandb", // Usually your GitHub org/user name.
  projectName: "weave", // Usually your repo name.

  onBrokenLinks: "throw",
  onBrokenMarkdownLinks: "warn",

  // Even if you don't use internationalization, you can use this field to set
  // useful metadata like html lang. For example, if your site is Chinese, you
  // may want to replace "en" with "zh-Hans".
  i18n: {
    defaultLocale: "en",
    locales: ["en"],
  },

  markdown: {
    mermaid: true,
  },

  presets: [
    [
      "classic",
      {
        docs: {
          sidebarPath: "./sidebars.ts",
          sidebarCollapsible: true,
          breadcrumbs: true,
          // Please change this to your repo.
          // Remove this to remove the "edit this page" links.
          editUrl: "https://github.com/wandb/weave/blob/master/docs/",
          routeBasePath: "/",
          docItemComponent: "@theme/ApiItem", // Derived from docusaurus-theme-openapi
          showLastUpdateTime: true,
        },
        theme: {
          customCss: "./src/css/custom.scss",
        },
      } satisfies Preset.Options,
    ],
  ],

  plugins: [
    ...(process.env.DOCS_SEGMENT_API_KEY
      ? [
          [
            "@laxels/docusaurus-plugin-segment",
            {
              apiKey: process.env.DOCS_SEGMENT_API_KEY,
              host: "wandb.ai",
              ajsPath: "/sa-docs.min.js",
              page: false,
              excludeUserAgents: ["GoogleSecurityScanner"],
            },
          ],
        ]
      : []),
    [
      // See https://github.com/PaloAltoNetworks/docusaurus-openapi-docs
      "docusaurus-plugin-openapi-docs",
      {
        id: "api", // plugin id
        docsPluginId: "classic", // configured for preset-classic
        config: {
          weave: {
            specPath: "./scripts/.cache/service_api_openapi_docs.json",
            outputDir: "docs/reference/service-api",
            sidebarOptions: {
              groupPathsBy: "tag",
              sidebarCollapsed: false,
            },
          } satisfies OpenApiPlugin.Options,
        },
      },
    ],
    "docusaurus-plugin-sass",
    [
      "@docusaurus/plugin-google-tag-manager",
      {
        containerId: "GTM-NM4PR4J9",
      },
    ],
    [
      "@docusaurus/plugin-google-gtag",
      {
        id: "gtag-1",
        trackingID: "G-JH1SJHJQXJ",
        anonymizeIP: true,
      },
    ],
    [
      "@docusaurus/plugin-google-gtag",
      {
        id: "gtag-2",
        trackingID: "G-0J3TM1K4Z4",
        anonymizeIP: true,
      },
    ],
    "plugin-image-zoom",
  ],

  themes: [
    [
      require.resolve("@easyops-cn/docusaurus-search-local"),
      {
        // https://github.com/easyops-cn/docusaurus-search-local?tab=readme-ov-file
        docsRouteBasePath: "/",
      },
    ],
    "docusaurus-theme-openapi-docs",
    "@docusaurus/theme-mermaid",
  ],
  themeConfig: {
    // Replace with your project's social card
    image: "img/logo-large-padded.png",
    navbar: {
      title: "W&B Weave",
      logo: {
        alt: "My Site Logo",
        src: "img/logo.svg",
      },
      items: [
        {
          type: "docSidebar",
          sidebarId: "documentationSidebar",
          position: "left",
          label: "Documentation",
        },
        {
          type: "docSidebar",
          sidebarId: "notebookSidebar",
          position: "left",
          label: "Cookbooks",
        },
        {
          position: "left",
          label: "Reference",
          type: "dropdown",
          items: [
            {
              type: "docSidebar",
              sidebarId: "pythonSdkSidebar",
              label: "Python SDK",
            },
            {
              type: "docSidebar",
              sidebarId: "typescriptSdkSidebar",
              label: "TypeScript SDK",
            },
            {
              type: "docSidebar",
              sidebarId: "serviceApiSidebar",
              label: "Service API",
            },
          ],
        },
        {
          position: "left",
          label: "Open Source",
          type: "dropdown",
          items: [
            {
              href: "https://github.com/wandb/weave",
              label: "GitHub",
            },
            {
              href: "https://github.com/wandb/weave/releases",
              label: "Release Changelog",
            },
          ],
        },
        {
          type: "search",
          position: "right",
        },
        {
          to: "https://wandb.ai/home",
          label: "Open App",
          position: "right",
          className: "button button--secondary button--med margin-right--sm",
        },
        {
          position: "left",
          label: "Community",
          type: "dropdown",
          items: [
            {
              label: "LLM Courses",
              href: "https://www.wandb.courses/",
            },
            {
              label: "Forum",
              href: "https://community.wandb.ai",
            },
            {
              label: "Twitter",
              href: "https://twitter.com/weights_biases",
            },
          ],
        },
      ],
    },
    footer: {
      copyright: `Made with ❤️ by Weights & Biases`,
    },
    prism: {
      // theme: prismThemes.nightOwl,
      theme: prismThemes.nightOwlLight,
      darkTheme: prismThemes.dracula,
      magicComments: [
        // Remember to extend the default highlight class name as well!
        {
          className: "theme-code-block-highlighted-line",
          line: "highlight-next-line",
          block: { start: "highlight-start", end: "highlight-end" },
        },
      ],
    },
    imageZoom: {
      // CSS selector to apply the plugin to
      selector: "img.zoomable",
      // Optional medium-zoom options
      // see: https://www.npmjs.com/package/medium-zoom#options
      options: {},
    },
  } satisfies Preset.ThemeConfig,
};

export default config;
