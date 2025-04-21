import * as z from 'zod';

export const ActionTypeSchema = z.enum(['contains_words', 'llm_judge']);
export type ActionType = z.infer<typeof ActionTypeSchema>;

export const ModelSchema = z.enum(['gpt-4o', 'gpt-4o-mini']);
export type Model = z.infer<typeof ModelSchema>;

export const ProviderReturnTypeSchema = z.enum(['openai']);
export type ProviderReturnType = z.infer<typeof ProviderReturnTypeSchema>;

export const DirectionSchema = z.enum(['asc', 'desc']);
export type Direction = z.infer<typeof DirectionSchema>;

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

export const ProviderSchema = z.object({
  api_key_name: z.string(),
  base_url: z.string(),
  description: z.union([z.null(), z.string()]).optional(),
  extra_headers: z.record(z.string(), z.string()).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  return_type: ProviderReturnTypeSchema.optional(),
});
export type Provider = z.infer<typeof ProviderSchema>;

export const ProviderModelSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  max_tokens: z.number(),
  name: z.union([z.null(), z.string()]).optional(),
  provider: z.string(),
});
export type ProviderModel = z.infer<typeof ProviderModelSchema>;

export const ColumnSchema = z.object({
  label: z.union([z.null(), z.string()]).optional(),
  path: z
    .union([z.array(z.union([z.number(), z.string()])), z.null()])
    .optional(),
});
export type Column = z.infer<typeof ColumnSchema>;

export const CallsFilterSchema = z.object({
  call_ids: z.union([z.array(z.string()), z.null()]).optional(),
  input_refs: z.union([z.array(z.string()), z.null()]).optional(),
  op_names: z.union([z.array(z.string()), z.null()]).optional(),
  output_refs: z.union([z.array(z.string()), z.null()]).optional(),
  parent_ids: z.union([z.array(z.string()), z.null()]).optional(),
  trace_ids: z.union([z.array(z.string()), z.null()]).optional(),
  trace_roots_only: z.union([z.boolean(), z.null()]).optional(),
  wb_run_ids: z.union([z.array(z.string()), z.null()]).optional(),
  wb_user_ids: z.union([z.array(z.string()), z.null()]).optional(),
});
export type CallsFilter = z.infer<typeof CallsFilterSchema>;

export const PinSchema = z.object({
  left: z.array(z.string()),
  right: z.array(z.string()),
});
export type Pin = z.infer<typeof PinSchema>;

export const ContainsSpecSchema = z.object({
  case_insensitive: z.union([z.boolean(), z.null()]).optional(),
  input: z.any(),
  substr: z.any(),
});
export type ContainsSpec = z.infer<typeof ContainsSpecSchema>;

export const SortBySchema = z.object({
  direction: DirectionSchema,
  field: z.string(),
});
export type SortBy = z.infer<typeof SortBySchema>;

export const TestOnlyNestedBaseModelSchema = z.object({
  a: z.number(),
  aliased_property_alias: z.number(),
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

export const ExprSchema = z.object({
  $and: z.array(z.any()).optional(),
  $or: z.array(z.any()).optional(),
  $not: z.array(z.any()).optional(),
  $eq: z.array(z.any()).optional(),
  $gt: z.array(z.any()).optional(),
  $gte: z.array(z.any()).optional(),
  $in: z.array(z.any()).optional(),
  $contains: ContainsSpecSchema.optional(),
});
export type Expr = z.infer<typeof ExprSchema>;

export const TestOnlyExampleSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  nested_base_model: TestOnlyNestedBaseModelSchema,
  nested_base_object: z.string(),
  primitive: z.number(),
});
export type TestOnlyExample = z.infer<typeof TestOnlyExampleSchema>;

export const QuerySchema = z.object({
  $expr: ExprSchema,
});
export type Query = z.infer<typeof QuerySchema>;

export const SavedViewDefinitionSchema = z.object({
  cols: z.union([z.record(z.string(), z.boolean()), z.null()]).optional(),
  columns: z.union([z.array(ColumnSchema), z.null()]).optional(),
  filter: z.union([CallsFilterSchema, z.null()]).optional(),
  page_size: z.union([z.number(), z.null()]).optional(),
  pin: z.union([PinSchema, z.null()]).optional(),
  query: z.union([QuerySchema, z.null()]).optional(),
  sort_by: z.union([z.array(SortBySchema), z.null()]).optional(),
});
export type SavedViewDefinition = z.infer<typeof SavedViewDefinitionSchema>;

export const SavedViewSchema = z.object({
  definition: SavedViewDefinitionSchema,
  description: z.union([z.null(), z.string()]).optional(),
  label: z.string(),
  name: z.union([z.null(), z.string()]).optional(),
  view_type: z.string(),
});
export type SavedView = z.infer<typeof SavedViewSchema>;

export const builtinObjectClassRegistry = {
  ActionSpec: ActionSpecSchema,
  AnnotationSpec: AnnotationSpecSchema,
  Leaderboard: LeaderboardSchema,
  Provider: ProviderSchema,
  ProviderModel: ProviderModelSchema,
  SavedView: SavedViewSchema,
  TestOnlyExample: TestOnlyExampleSchema,
  TestOnlyNestedBaseObject: TestOnlyNestedBaseObjectSchema,
};

export const GeneratedBuiltinObjectClassesZodSchema = z.object(
  builtinObjectClassRegistry
);

export type GeneratedBuiltinObjectClassesZod = z.infer<
  typeof GeneratedBuiltinObjectClassesZodSchema
>;
