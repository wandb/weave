import * as z from 'zod';

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

export const TestOnlyExampleSchema = z.object({
  description: z.union([z.null(), z.string()]).optional(),
  name: z.union([z.null(), z.string()]).optional(),
  nested_base_model: TestOnlyNestedBaseModelSchema,
  nested_base_object: z.string(),
  primitive: z.number(),
});
export type TestOnlyExample = z.infer<typeof TestOnlyExampleSchema>;

export const baseObjectClassRegistry = {
  TestOnlyExample: TestOnlyExampleSchema,
  TestOnlyNestedBaseObject: TestOnlyNestedBaseObjectSchema,
};

export const GeneratedBaseObjectClassesZodSchema = z.object(
  baseObjectClassRegistry
);

export type GeneratedBaseObjectClassesZod = z.infer<
  typeof GeneratedBaseObjectClassesZodSchema
>;
