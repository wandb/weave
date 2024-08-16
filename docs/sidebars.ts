import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";
import { SidebarItemCategoryBase } from "@docusaurus/plugin-content-docs-types";

const CATEGORY_SECTION_HEADER_MIXIN: SidebarItemCategoryBase = {
  type: "category",
  collapsible: false,
  collapsed: false,
  className: "sidebar-section-title",
}

const sidebars: SidebarsConfig = {
  documentationSidebar: [
    {
      type: 'doc',
      label: '👋 Introduction',
      id: "introduction"
    },
    {
      type: 'doc',
      label: '🤖 Live Demo',
      id: "introduction"
    },
    {
      type: 'doc',
      label: '🚀 Quickstart',
      id: "introduction"
    },
    {
      label: "📝 End-to-End Tutorial",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        {
          label: "Tracing",
          type: "category",
          collapsible: false,
          collapsed: false,
          items: [
            {
              type: 'doc',
              label: '1: "Hello World"',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '2: Connect an LLM',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '3: Define a Model',
              id: "introduction"
            },
          ],
        },
        {
          label: "Evaluation",
          type: "category",
          collapsible: false,
          collapsed: false,
          items: [
                        {
              type: 'doc',
              label: '4: Run an Evaluation',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '5: Analyze Performance',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '6: Compare Models',
              id: "introduction"
            },
          ],
        },
        {
          label: "Feedback",
          type: "category",
          collapsible: false,
          collapsed: false,
          items: [
                        {
              type: 'doc',
              label: '7: Serve Predictions',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '8: Collect Feedback',
              id: "introduction"
            },
            {
              type: 'doc',
              label: '9: Improve the Model',
              id: "introduction"
            },
          ],
        },
      ],
    },
    {
      label: "💻 Product Walkthrough",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        {
          type: 'doc',
          label: 'Overview',
          id: "introduction"
        },
        {
          type: "category",
          collapsible: false,
          collapsed: false,
          label: "Application Tracing",
          items: [
            {
              type: 'doc',
              label: 'Understanding Traces',
              id: "introduction"
            },
            {
              type: 'doc',
              label: 'Calls',
              id: "introduction"
            },
            {
              type: 'doc',
              label: 'Ops',
              id: "introduction"
            },
            {
              type: 'doc',
              label: 'Objects',
              id: "introduction"
            },
          ],
        },
        {
          type: 'doc',
          label: 'Models',
          id: "introduction"
        },
        {
          type: 'doc',
          label: 'Datasets',
          id: "introduction"
        },
        {
          type: 'doc',
          label: 'Prompts',
          id: "introduction"
        },
        {
          type: 'doc',
          label: 'Production Feedback',
          id: "introduction"
        },
        {
          type: "category",
          collapsible: true,
          collapsed: false,
          label: "Integrations",
          link: { type: "doc", id: "guides/integrations/index" },
          items: [
            {
              type: "category",
              collapsible: true,
              collapsed: true,
              label: "LLM Providers",
              items: [
                "guides/integrations/openai",
                "guides/integrations/anthropic",
                "guides/integrations/cohere",
                "guides/integrations/mistral",
                "guides/integrations/together_ai",
                "guides/integrations/groq",
                "guides/integrations/openrouter",
                "guides/integrations/litellm",
              ],
            },
            "guides/integrations/local_models",
            {
              type: "category",
              collapsible: true,
              collapsed: true,
              label: "Frameworks",
              items: [,
                "guides/integrations/langchain",
                "guides/integrations/llamaindex",
                "guides/integrations/dspy",
              ],
            },
          ],
        },
        {
          label: "Technical FAQ",
          items: [
            {
              type: 'doc',
              label: 'Tables vs Lists',
              id: "introduction"
            },
            {
              type: 'doc',
              label: 'Refs',
              id: "introduction"
            },
            {
              type: 'doc',
              label: 'Object Serialization',
              id: "introduction"
            },
          ],
        },
      ],
      
    },
    {
      label: "🏭 Enterprise",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        {
          type: "doc",
          id: "guides/platform/index",
        },
      ],
    },
  ],
  pythonSdkSidebar: [{ type: "autogenerated", dirName: "reference/python-sdk" }],
  serviceApiSidebar: require("./docs/reference/service-api/sidebar.ts").filter((row) => {
    if (row.id == "reference/service-api/fastapi") {
      // Remove FastAPI from the sidebar - this is a default homepage that is not useful for us
      return false;
    }

    // Hide the `Service` category from the sidebar
    if (row.label == "Service") {
      return false;
    }

    return true;
  }).map((row) => {
    // This makes each section nicely formatted.
    // Totally up for debate if we want to keep this or not.
    if (row.type === "category") {
      return {
        ...row,
        ...CATEGORY_SECTION_HEADER_MIXIN,
      };
    }

    return row;
  }),
  // This will probably need to be customized in the future
  notebookSidebar: [{ type: "autogenerated", dirName: "reference/gen_notebooks" }],
};

export default sidebars;
