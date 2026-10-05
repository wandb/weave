/**
 * W&B-specific OTel resource attribute keys attached to every span this
 * SDK emits. Not part of the GenAI semconv spec.
 */

// NOTE: The target project/entity is intentionally NOT a Resource attribute.
// Routing rides the exporter's `project_id` header instead, because the OTel
// Resource is immutable per-provider and server-side precedence ranks
// `wandb.project`/`wandb.entity` Resource attrs above the header. Baking the
// project into the Resource pins routing to whatever project was first seen, so
// a later `weave.init('ent/other')` would bleed its agent spans into the first
// project. See genai/provider.ts and Python PR #7507.
export const WANDB_RESOURCE_ATTR = {
  WANDB_SDK_NAME: 'wandb.sdk.name',
  WANDB_SDK_VERSION: 'wandb.sdk.version',
  WANDB_SDK_LANGUAGE: 'wandb.sdk.language',
} as const;
