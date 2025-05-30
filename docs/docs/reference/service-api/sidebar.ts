import type { SidebarsConfig } from "@docusaurus/plugin-content-docs";

const sidebar: SidebarsConfig = {
  apisidebar: [
    {
      type: "doc",
      id: "reference/service-api/fastapi",
    },
    {
      type: "category",
      label: "Service",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/read-root-health-get",
          label: "Read Root",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "reference/service-api/read-version-version-get",
          label: "Read Version",
          className: "api-method get",
        },
        {
          type: "doc",
          id: "reference/service-api/server-info-server-info-get",
          label: "Server Info",
          className: "api-method get",
        },
      ],
    },
    {
      type: "category",
      label: "OpenTelemetry",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/export-trace-otel-v-1-traces-post",
          label: "Export Trace",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Calls",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/call-start-call-start-post",
          label: "Call Start",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/call-end-call-end-post",
          label: "Call End",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/call-start-batch-call-upsert-batch-post",
          label: "Call Start Batch",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/calls-delete-calls-delete-post",
          label: "Calls Delete",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/call-update-call-update-post",
          label: "Call Update",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/call-read-call-read-post",
          label: "Call Read",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/calls-query-stats-calls-query-stats-post",
          label: "Calls Query Stats",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/calls-query-stream-calls-stream-query-post",
          label: "Calls Query Stream",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Objects",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/obj-create-obj-create-post",
          label: "Obj Create",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/obj-read-obj-read-post",
          label: "Obj Read",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/objs-query-objs-query-post",
          label: "Objs Query",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/obj-delete-obj-delete-post",
          label: "Obj Delete",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Tables",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/table-create-table-create-post",
          label: "Table Create",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/table-update-table-update-post",
          label: "Table Update",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/table-query-table-query-post",
          label: "Table Query",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/table-query-stats-table-query-stats-post",
          label: "Table Query Stats",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/table-query-stats-batch-table-query-stats-batch-post",
          label: "Table Query Stats Batch",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Refs",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/refs-read-batch-refs-read-batch-post",
          label: "Refs Read Batch",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Files",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/file-create-file-create-post",
          label: "File Create",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/file-content-file-content-post",
          label: "File Content",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/files-stats-files-query-stats-post",
          label: "Files Stats",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Costs",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/cost-create-cost-create-post",
          label: "Cost Create",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/cost-query-cost-query-post",
          label: "Cost Query",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/cost-purge-cost-purge-post",
          label: "Cost Purge",
          className: "api-method post",
        },
      ],
    },
    {
      type: "category",
      label: "Feedback",
      collapsed: false,
      items: [
        {
          type: "doc",
          id: "reference/service-api/feedback-create-feedback-create-post",
          label: "Feedback Create",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/feedback-query-feedback-query-post",
          label: "Feedback Query",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/feedback-purge-feedback-purge-post",
          label: "Feedback Purge",
          className: "api-method post",
        },
        {
          type: "doc",
          id: "reference/service-api/feedback-replace-feedback-replace-post",
          label: "Feedback Replace",
          className: "api-method post",
        },
      ],
    },
  ],
};

export default sidebar.apisidebar;
