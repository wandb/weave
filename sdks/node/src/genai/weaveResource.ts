/**
 * Weave-specific OTel resource attribute keys attached to every span this
 * SDK emits. Not part of the GenAI semconv spec.
 */

export const WEAVE_RESOURCE_ATTR = {
  WANDB_ENTITY: 'wandb.entity',
  WANDB_PROJECT: 'wandb.project',
  WEAVE_SDK_VERSION: 'weave.sdk.version',
  WEAVE_SDK_LANGUAGE: 'weave.sdk.language',
} as const;
