import * as z from 'zod';

export const ActionTypeSchema = z.enum(['contains_words', 'llm_judge']);
export type ActionType = z.infer<typeof ActionTypeSchema>;

export const ModelSchema = z.enum(['gpt-4o', 'gpt-4o-mini']);
export type Model = z.infer<typeof ModelSchema>;

export const ConfigSchema = z.object({
  action_type: ActionTypeSchema.optional(),
  model: ModelSchema.optional(),
  prompt: z.string().optional(),
  response_schema: z.record(z.string(), z.any()).optional(),
  target_words: z.array(z.string()).optional(),
});
export type Config = z.infer<typeof ConfigSchema>;

export const AnnotationSpecSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  field_schema: z.record(z.string(), z.any()).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  op_scope: z.union([z.array(z.string()), z.null()]).optional(),
  unique_among_creators: z.boolean().optional(),
});
export type AnnotationSpec = z.infer<typeof AnnotationSpecSchema>;

export const NestedBaseModelForTestingSchema = z.object({
  a: z.number(),
});
export type NestedBaseModelForTesting = z.infer<
  typeof NestedBaseModelForTestingSchema
>;

export const LeaderboardColumnSchema = z.object({
  evaluation_object_ref: z.string(),
  scorer_name: z.string(),
  should_minimize: z.union([z.boolean(), z.null()]).optional(),
  summary_metric_path: z.string(),
});
export type LeaderboardColumn = z.infer<typeof LeaderboardColumnSchema>;

export const NestedBaseObjectForTestingSchema = z.object({
  b: z.number(),
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type NestedBaseObjectForTesting = z.infer<
  typeof NestedBaseObjectForTestingSchema
>;

export const ActionSpecSchema = z.object({
  config: ConfigSchema,
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type ActionSpec = z.infer<typeof ActionSpecSchema>;

export const ExampleForTestingSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  nested_base_model: NestedBaseModelForTestingSchema,
  nested_base_object: z.string(),
  primitive: z.number(),
});
export type ExampleForTesting = z.infer<typeof ExampleForTestingSchema>;

export const LeaderboardSchema = z.object({
  columns: z.array(LeaderboardColumnSchema),
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type Leaderboard = z.infer<typeof LeaderboardSchema>;

export const builtinObjectClassRegistry = {
  ActionSpec: ActionSpecSchema,
  AnnotationSpec: AnnotationSpecSchema,
  ExampleForTesting: ExampleForTestingSchema,
  Leaderboard: LeaderboardSchema,
  NestedBaseObjectForTesting: NestedBaseObjectForTestingSchema,
};

export const GeneratedBuiltinObjectClassesZodSchema = z.object(
  builtinObjectClassRegistry
);

export type GeneratedBuiltinObjectClassesZod = z.infer<
  typeof GeneratedBuiltinObjectClassesZodSchema
>;
