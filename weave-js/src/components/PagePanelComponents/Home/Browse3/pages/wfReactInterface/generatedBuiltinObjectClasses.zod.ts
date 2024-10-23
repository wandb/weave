import * as z from 'zod';

export const ActionTypeSchema = z.enum(['contains_words', 'llm_judge']);
export type ActionType = z.infer<typeof ActionTypeSchema>;

export const ModelSchema = z.enum(['gpt-4o', 'gpt-4o-mini']);
export type Model = z.infer<typeof ModelSchema>;

export const LogicoperatorSchema = z.enum(['and']);
export type Logicoperator = z.infer<typeof LogicoperatorSchema>;

export const SortSchema = z.enum(['asc', 'desc']);
export type Sort = z.infer<typeof SortSchema>;

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

export const LegacyFilterSchema = z.object({
  input_object_version_refs: z
    .union([z.array(z.string()), z.null()])
    .optional(),
  op_version_refs: z.union([z.array(z.string()), z.null()]).optional(),
  output_object_version_refs: z
    .union([z.array(z.string()), z.null()])
    .optional(),
});
export type LegacyFilter = z.infer<typeof LegacyFilterSchema>;

export const FilterSchema = z.object({
  field: z.string(),
  id: z.number(),
  operator: z.string(),
  value: z.any(),
});
export type Filter = z.infer<typeof FilterSchema>;

export const PinSchema = z.object({
  left: z.array(z.string()),
  right: z.array(z.string()),
});
export type Pin = z.infer<typeof PinSchema>;

export const SortClauseSchema = z.object({
  field: z.string(),
  sort: SortSchema,
});
export type SortClause = z.infer<typeof SortClauseSchema>;

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

export const FiltersSchema = z.object({
  items: z.array(FilterSchema),
  logicOperator: LogicoperatorSchema,
});
export type Filters = z.infer<typeof FiltersSchema>;

export const TestOnlyExampleSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  nested_base_model: TestOnlyNestedBaseModelSchema,
  nested_base_object: z.string(),
  primitive: z.number(),
});
export type TestOnlyExample = z.infer<typeof TestOnlyExampleSchema>;

export const SavedViewDefinitionSchema = z.object({
  cols: z.union([z.record(z.string(), z.boolean()), z.null()]).optional(),
  filter: z.union([LegacyFilterSchema, z.null()]).optional(),
  filters: z.union([FiltersSchema, z.null()]).optional(),
  page_size: z.union([z.number(), z.null()]).optional(),
  pin: z.union([PinSchema, z.null()]).optional(),
  sort: z.union([z.array(SortClauseSchema), z.null()]).optional(),
});
export type SavedViewDefinition = z.infer<typeof SavedViewDefinitionSchema>;

export const SavedViewSchema = z.object({
  definition: SavedViewDefinitionSchema,
  description: z.union([z.null(), z.string()]).optional(),
  label: z.string(),
  name: z.union([z.null(), z.string()]).optional(),
  table: z.string(),
});
export type SavedView = z.infer<typeof SavedViewSchema>;

export const builtinObjectClassRegistry = {
  ActionSpec: ActionSpecSchema,
  AnnotationSpec: AnnotationSpecSchema,
  Leaderboard: LeaderboardSchema,
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
