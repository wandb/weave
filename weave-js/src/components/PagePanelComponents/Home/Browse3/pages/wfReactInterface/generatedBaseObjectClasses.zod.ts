import * as z from 'zod';

// BEGINNING OF CUSTOM CODE /////
// Sadly, the json-schema to zod converter doesn't support discriminator
// so we have to define the schemas manually. If you run the generator
// make sure to review the changes to this section.
export const LlmJudgeActionSpecSchema = z.object({
  action_type: z.enum(['llm_judge']),
  model: z.enum(['gpt-4o', 'gpt-4o-mini']),
  prompt: z.string(),
  response_schema: z.record(z.string(), z.any()),
});
export type LlmJudgeActionSpec = z.infer<typeof LlmJudgeActionSpecSchema>;

export const ContainsWordsActionSpecSchema = z.object({
  action_type: z.enum(['contains_words']),
  target_words: z.array(z.string()),
});
export type ContainsWordsActionSpec = z.infer<
  typeof ContainsWordsActionSpecSchema
>;

export const SpecSchema = z.discriminatedUnion('action_type', [
  LlmJudgeActionSpecSchema,
  ContainsWordsActionSpecSchema,
]);
export type Spec = z.infer<typeof SpecSchema>;
// END OF CUSTOM CODE /////

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

export const ActionDefinitionSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  spec: SpecSchema,
});
export type ActionDefinition = z.infer<typeof ActionDefinitionSchema>;

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

export const baseObjectClassRegistry = {
  ActionDefinition: ActionDefinitionSchema,
  Leaderboard: LeaderboardSchema,
  TestOnlyExample: TestOnlyExampleSchema,
  TestOnlyNestedBaseObject: TestOnlyNestedBaseObjectSchema,
};

export const GeneratedBaseObjectClassesZodSchema = z.object(
  baseObjectClassRegistry
);

export type GeneratedBaseObjectClassesZod = z.infer<
  typeof GeneratedBaseObjectClassesZodSchema
>;
