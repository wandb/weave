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

export const LeaderboardColumnSchema = z.object({
  evaluation_object_ref: z.string(),
  scorer_name: z.string(),
  should_minimize: z.union([z.boolean(), z.null()]).optional(),
  summary_metric_path: z.string(),
});
export type LeaderboardColumn = z.infer<typeof LeaderboardColumnSchema>;

export const TestOnlyNestedBaseModelSchema = z.object({
  a: z.number(),
});
export type TestOnlyNestedBaseModel = z.infer<
  typeof TestOnlyNestedBaseModelSchema
>;

export const TestOnlyNestedBaseObjectSchema = z.object({
  b: z.number(),
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type TestOnlyNestedBaseObject = z.infer<
  typeof TestOnlyNestedBaseObjectSchema
>;

export const ActionSpecSchema = z.object({
  config: ConfigSchema,
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type ActionSpec = z.infer<typeof ActionSpecSchema>;

export const LeaderboardSchema = z.object({
  columns: z.array(LeaderboardColumnSchema),
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
});
export type Leaderboard = z.infer<typeof LeaderboardSchema>;

export const TestOnlyExampleSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  nested_base_model: TestOnlyNestedBaseModelSchema,
  nested_base_object: z.string(),
  primitive: z.number(),
});
export type TestOnlyExample = z.infer<typeof TestOnlyExampleSchema>;

export const builtinObjectClassRegistry = {
  ActionSpec: ActionSpecSchema,
  AnnotationSpec: AnnotationSpecSchema,
  Leaderboard: LeaderboardSchema,
  TestOnlyExample: TestOnlyExampleSchema,
  TestOnlyNestedBaseObject: TestOnlyNestedBaseObjectSchema,
};

export const GeneratedBuiltinObjectClassesZodSchema = z.object(
  builtinObjectClassRegistry
);

export type GeneratedBuiltinObjectClassesZod = z.infer<
  typeof GeneratedBuiltinObjectClassesZodSchema
>;
