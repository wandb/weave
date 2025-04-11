import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";
import { SidebarItemCategoryBase } from "@docusaurus/plugin-content-docs-types";

const CATEGORY_SECTION_HEADER_MIXIN: SidebarItemCategoryBase = {
  type: "category",
  collapsible: false,
  collapsed: false,
  className: "sidebar-section-title",
};

const sidebars: SidebarsConfig = {
  documentationSidebar: [
    {
      label: "👋 Introduction",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        "introduction",
        {
          type: "doc",
          label: "Quickstart: Track LLM Calls",
          id: "quickstart",
        },
      ],
    },
    {
      label: "🔄 Iteration",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      
      items: [
        {
          type: "doc",
          label: "Track Application Logic",
          id: "tutorial-tracing_2",
        },
        {
          type: "category",
          collapsible: true,
          collapsed: false,
          label: "Tracing & Debugging",
          items: [
            {
              type: "doc",
              label: "Tracing Overview",
              id: "guides/tracking/tracing",
            },
            "guides/tracking/costs",
            {
              type: "doc",
              label: "Logging Media",
              id: "guides/core-types/media",
            },
            "guides/tools/playground",
            "guides/integrations/index",
            {
              type: "doc",
              label: "Compare Traces",
              id: "guides/tools/comparison",
            },
            "guides/tracking/trace-tree"
          ]
        },
        {
          type: "category",
          collapsible: true,
          collapsed: true,
          label: "Version Control for Models & Prompts",
          items: [
            {
              type: "doc",
              label: "App Versioning",
              id: "tutorial-weave_models",
            },
            "guides/core-types/models",
            "guides/core-types/prompts",
            "guides/tracking/objects",
            "guides/tracking/ops",
          ]
        },
      ],
    },
    {
      label: "📊 Evaluation",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        {
          type: "doc",
          label: "Build an Evaluation Pipeline",
          id: "tutorial-eval",
        },
        {
          type: "doc",
          label: "Evaluate a RAG App",
          id: "tutorial-rag",
        },
        {
          type: "category",
          collapsible: true,
          collapsed: false,
          label: "Evaluations",
          items: [
            "guides/core-types/evaluations",
            "guides/core-types/datasets",
            "guides/evaluation/scorers",
            "guides/evaluation/builtin_scorers",
            "guides/evaluation/weave_local_scorers",
          ]
        },
      ],
    },
    {
      label: "🚀 Productionization",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        {
          type: "category",
          collapsible: true,
          collapsed: false,
          label: "Collect Feedback & Examples",
          items: [
            "guides/tracking/feedback",
            "guides/tracking/redact-pii",
          ]
        },
        {
          type: "category",
          collapsible: true,
          collapsed: false,
          label: "Online Evaluation",
              link: { type: "doc", id: "guides/evaluation/guardrails_and_monitors" },
              items: [
                {
                  type: "link",
                  href: "/guides/evaluation/guardrails_and_monitors#using-scorers-as-guardrails",
                  label: "Guardrails",
                  autoAddBaseUrl: true,
                },
                {
                  type: "link",
                  href: "/guides/evaluation/guardrails_and_monitors#using-scorers-as-monitors",
                  label: "Monitors",
                  autoAddBaseUrl: true,
                }
              ],
        },
        {
          type: "category",
          collapsible: true,
          collapsed: true,
          label: "Tools & Utilities",
          link: { type: "doc", id: "guides/tools/index" },
          items: ["guides/tools/serve", "guides/tools/deploy"],
        },
      ],
    },
    {
      label: "🔥 Integrations",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      link: { type: "doc", id: "guides/integrations/index" },
      items: [
        {
          type: "category",
          collapsible: true,
          collapsed: true,
          label: "LLM Providers",
          items: [
            "guides/integrations/bedrock",
            "guides/integrations/anthropic",
            "guides/integrations/cerebras",
            "guides/integrations/cohere",
            "guides/integrations/google",
            "guides/integrations/groq",
            "guides/integrations/huggingface",
            "guides/integrations/litellm",
            "guides/integrations/azure",
            "guides/integrations/mistral",
            "guides/integrations/nvidia_nim",
            "guides/integrations/openai",
            "guides/integrations/openrouter",
            "guides/integrations/together_ai",
          ],          
        },
        "guides/integrations/local_models",
        {
          type: "category",
          collapsible: true,
          collapsed: true,
          label: "Frameworks",
          items: [
            "guides/integrations/openai_agents",
            "guides/integrations/langchain",
            "guides/integrations/llamaindex",
            "guides/integrations/dspy",
            "guides/integrations/instructor",
            "guides/integrations/crewai",
            "guides/integrations/smolagents",
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
        {
          type: "doc",
          id: "guides/platform/weave-self-managed",
        }
      ],
    },
    {
      label: "🛠️ Tools & Resources",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      items: [
        "guides/core-types/env-vars",
        "guides/troubleshooting",
        "guides/tracking/faqs",
      ],
    },
  ],
  // TODO: add the actual ts-sdk sidebar
  typescriptSdkSidebar: [
    { type: "autogenerated", dirName: "reference/typescript-sdk" },
  ],
  pythonSdkSidebar: [
    { type: "autogenerated", dirName: "reference/python-sdk" },
  ],
  serviceApiSidebar: require("./docs/reference/service-api/sidebar.ts")
    .filter((row) => {
      if (row.id == "reference/service-api/fastapi") {
        // Remove FastAPI from the sidebar - this is a default homepage that is not useful for us
        return false;
      }

      // Hide the `Service` category from the sidebar
      if (row.label == "Service") {
        return false;
      }

      return true;
    })
    .map((row) => {
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
  notebookSidebar: [
    {
      label: "Python",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      collapsible: true,
      collapsed: false,
      items: [
        { type: "autogenerated", dirName: "reference/gen_notebooks" },
      ],
    },
    {
      label: "TypeScript",
      ...CATEGORY_SECTION_HEADER_MIXIN,
      collapsible: true,
      collapsed: false,
      items: [
        { type: "autogenerated", dirName: "reference/generated_typescript_docs" },
      ],
    },
  ],
};

export default sidebars;
