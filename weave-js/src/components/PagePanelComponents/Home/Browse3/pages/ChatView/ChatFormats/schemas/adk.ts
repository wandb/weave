import {z} from 'zod';

export const OutcomeSchema = z.enum([
  'OUTCOME_UNSPECIFIED',
  'OUTCOME_OK',
  'OUTCOME_FAILED',
  'OUTCOME_DEADLINE_EXCEEDED',
]);
export type Outcome = z.infer<typeof OutcomeSchema>;

export const LanguageSchema = z.enum(['LANGUAGE_UNSPECIFIED', 'PYTHON']);
export type Language = z.infer<typeof LanguageSchema>;

export const TypeSchema = z.enum([
  'TYPE_UNSPECIFIED',
  'STRING',
  'NUMBER',
  'INTEGER',
  'BOOLEAN',
  'ARRAY',
  'OBJECT',
  'NULL',
]);
export type Type = z.infer<typeof TypeSchema>;

export const HarmCategorySchema = z.enum([
  'HARM_CATEGORY_UNSPECIFIED',
  'HARM_CATEGORY_HATE_SPEECH',
  'HARM_CATEGORY_DANGEROUS_CONTENT',
  'HARM_CATEGORY_HARASSMENT',
  'HARM_CATEGORY_SEXUALLY_EXPLICIT',
  'HARM_CATEGORY_CIVIC_INTEGRITY',
  'HARM_CATEGORY_IMAGE_HATE',
  'HARM_CATEGORY_IMAGE_DANGEROUS_CONTENT',
  'HARM_CATEGORY_IMAGE_HARASSMENT',
  'HARM_CATEGORY_IMAGE_SEXUALLY_EXPLICIT',
]);
export type HarmCategory = z.infer<typeof HarmCategorySchema>;

export const HarmBlockMethodSchema = z.enum([
  'HARM_BLOCK_METHOD_UNSPECIFIED',
  'SEVERITY',
  'PROBABILITY',
]);
export type HarmBlockMethod = z.infer<typeof HarmBlockMethodSchema>;

export const HarmBlockThresholdSchema = z.enum([
  'HARM_BLOCK_THRESHOLD_UNSPECIFIED',
  'BLOCK_LOW_AND_ABOVE',
  'BLOCK_MEDIUM_AND_ABOVE',
  'BLOCK_ONLY_HIGH',
  'BLOCK_NONE',
  'OFF',
]);
export type HarmBlockThreshold = z.infer<typeof HarmBlockThresholdSchema>;

export const ModeSchema = z.enum(['MODE_UNSPECIFIED', 'MODE_DYNAMIC']);
export type Mode = z.infer<typeof ModeSchema>;

export const AuthTypeSchema = z.enum([
  'AUTH_TYPE_UNSPECIFIED',
  'NO_AUTH',
  'API_KEY_AUTH',
  'HTTP_BASIC_AUTH',
  'GOOGLE_SERVICE_ACCOUNT_AUTH',
  'OAUTH',
  'OIDC_AUTH',
]);
export type AuthType = z.infer<typeof AuthTypeSchema>;

export const ApiSpecSchema = z.enum([
  'API_SPEC_UNSPECIFIED',
  'SIMPLE_SEARCH',
  'ELASTIC_SEARCH',
]);
export type ApiSpec = z.infer<typeof ApiSpecSchema>;

export const EnvironmentSchema = z.enum([
  'ENVIRONMENT_UNSPECIFIED',
  'ENVIRONMENT_BROWSER',
]);
export type Environment = z.infer<typeof EnvironmentSchema>;

export const UrlRetrievalStatusSchema = z.enum([
  'URL_RETRIEVAL_STATUS_UNSPECIFIED',
  'URL_RETRIEVAL_STATUS_SUCCESS',
  'URL_RETRIEVAL_STATUS_ERROR',
]);
export type UrlRetrievalStatus = z.infer<typeof UrlRetrievalStatusSchema>;

export const FinishReasonSchema = z.enum([
  'FINISH_REASON_UNSPECIFIED',
  'STOP',
  'MAX_TOKENS',
  'SAFETY',
  'RECITATION',
  'LANGUAGE',
  'OTHER',
  'BLOCKLIST',
  'PROHIBITED_CONTENT',
  'SPII',
  'MALFORMED_FUNCTION_CALL',
  'IMAGE_SAFETY',
  'UNEXPECTED_TOOL_CALL',
]);
export type FinishReason = z.infer<typeof FinishReasonSchema>;

export const HarmProbabilitySchema = z.enum([
  'HARM_PROBABILITY_UNSPECIFIED',
  'NEGLIGIBLE',
  'LOW',
  'MEDIUM',
  'HIGH',
]);
export type HarmProbability = z.infer<typeof HarmProbabilitySchema>;

export const HarmSeveritySchema = z.enum([
  'HARM_SEVERITY_UNSPECIFIED',
  'HARM_SEVERITY_NEGLIGIBLE',
  'HARM_SEVERITY_LOW',
  'HARM_SEVERITY_MEDIUM',
  'HARM_SEVERITY_HIGH',
]);
export type HarmSeverity = z.infer<typeof HarmSeveritySchema>;

export const BlockedReasonSchema = z.enum([
  'BLOCKED_REASON_UNSPECIFIED',
  'SAFETY',
  'OTHER',
  'BLOCKLIST',
  'PROHIBITED_CONTENT',
  'IMAGE_SAFETY',
]);
export type BlockedReason = z.infer<typeof BlockedReasonSchema>;

export const TrafficTypeSchema = z.enum([
  'TRAFFIC_TYPE_UNSPECIFIED',
  'ON_DEMAND',
  'PROVISIONED_THROUGHPUT',
]);
export type TrafficType = z.infer<typeof TrafficTypeSchema>;

export const ModalitySchema = z.enum([
  'MODALITY_UNSPECIFIED',
  'TEXT',
  'IMAGE',
  'AUDIO',
]);
export type Modality = z.infer<typeof ModalitySchema>;

export const MediaResolutionSchema = z.enum([
  'MEDIA_RESOLUTION_UNSPECIFIED',
  'MEDIA_RESOLUTION_LOW',
  'MEDIA_RESOLUTION_MEDIUM',
  'MEDIA_RESOLUTION_HIGH',
]);
export type MediaResolution = z.infer<typeof MediaResolutionSchema>;

export const JobStateSchema = z.enum([
  'JOB_STATE_UNSPECIFIED',
  'JOB_STATE_QUEUED',
  'JOB_STATE_PENDING',
  'JOB_STATE_RUNNING',
  'JOB_STATE_SUCCEEDED',
  'JOB_STATE_FAILED',
  'JOB_STATE_CANCELLING',
  'JOB_STATE_CANCELLED',
  'JOB_STATE_PAUSED',
  'JOB_STATE_EXPIRED',
  'JOB_STATE_UPDATING',
  'JOB_STATE_PARTIALLY_SUCCEEDED',
]);
export type JobState = z.infer<typeof JobStateSchema>;

export const AdapterSizeSchema = z.enum([
  'ADAPTER_SIZE_UNSPECIFIED',
  'ADAPTER_SIZE_ONE',
  'ADAPTER_SIZE_TWO',
  'ADAPTER_SIZE_FOUR',
  'ADAPTER_SIZE_EIGHT',
  'ADAPTER_SIZE_SIXTEEN',
  'ADAPTER_SIZE_THIRTY_TWO',
]);
export type AdapterSize = z.infer<typeof AdapterSizeSchema>;

export const FeatureSelectionPreferenceSchema = z.enum([
  'FEATURE_SELECTION_PREFERENCE_UNSPECIFIED',
  'PRIORITIZE_QUALITY',
  'BALANCED',
  'PRIORITIZE_COST',
]);
export type FeatureSelectionPreference = z.infer<
  typeof FeatureSelectionPreferenceSchema
>;

export const BehaviorSchema = z.enum([
  'UNSPECIFIED',
  'BLOCKING',
  'NON_BLOCKING',
]);
export type Behavior = z.infer<typeof BehaviorSchema>;

export const DynamicRetrievalConfigModeSchema = z.enum([
  'MODE_UNSPECIFIED',
  'MODE_DYNAMIC',
]);
export type DynamicRetrievalConfigMode = z.infer<
  typeof DynamicRetrievalConfigModeSchema
>;

export const FunctionCallingConfigModeSchema = z.enum([
  'MODE_UNSPECIFIED',
  'AUTO',
  'ANY',
  'NONE',
]);
export type FunctionCallingConfigMode = z.infer<
  typeof FunctionCallingConfigModeSchema
>;

export const SafetyFilterLevelSchema = z.enum([
  'BLOCK_LOW_AND_ABOVE',
  'BLOCK_MEDIUM_AND_ABOVE',
  'BLOCK_ONLY_HIGH',
  'BLOCK_NONE',
]);
export type SafetyFilterLevel = z.infer<typeof SafetyFilterLevelSchema>;

export const PersonGenerationSchema = z.enum([
  'DONT_ALLOW',
  'ALLOW_ADULT',
  'ALLOW_ALL',
]);
export type PersonGeneration = z.infer<typeof PersonGenerationSchema>;

export const ImagePromptLanguageSchema = z.enum([
  'auto',
  'en',
  'ja',
  'ko',
  'hi',
  'zh',
  'pt',
  'es',
]);
export type ImagePromptLanguage = z.infer<typeof ImagePromptLanguageSchema>;

export const MaskReferenceModeSchema = z.enum([
  'MASK_MODE_DEFAULT',
  'MASK_MODE_USER_PROVIDED',
  'MASK_MODE_BACKGROUND',
  'MASK_MODE_FOREGROUND',
  'MASK_MODE_SEMANTIC',
]);
export type MaskReferenceMode = z.infer<typeof MaskReferenceModeSchema>;

export const ControlReferenceTypeSchema = z.enum([
  'CONTROL_TYPE_DEFAULT',
  'CONTROL_TYPE_CANNY',
  'CONTROL_TYPE_SCRIBBLE',
  'CONTROL_TYPE_FACE_MESH',
]);
export type ControlReferenceType = z.infer<typeof ControlReferenceTypeSchema>;

export const SubjectReferenceTypeSchema = z.enum([
  'SUBJECT_TYPE_DEFAULT',
  'SUBJECT_TYPE_PERSON',
  'SUBJECT_TYPE_ANIMAL',
  'SUBJECT_TYPE_PRODUCT',
]);
export type SubjectReferenceType = z.infer<typeof SubjectReferenceTypeSchema>;

export const EditModeSchema = z.enum([
  'EDIT_MODE_DEFAULT',
  'EDIT_MODE_INPAINT_REMOVAL',
  'EDIT_MODE_INPAINT_INSERTION',
  'EDIT_MODE_OUTPAINT',
  'EDIT_MODE_CONTROLLED_EDITING',
  'EDIT_MODE_STYLE',
  'EDIT_MODE_BGSWAP',
  'EDIT_MODE_PRODUCT_IMAGE',
]);
export type EditMode = z.infer<typeof EditModeSchema>;

export const VideoCompressionQualitySchema = z.enum(['OPTIMIZED', 'LOSSLESS']);
export type VideoCompressionQuality = z.infer<
  typeof VideoCompressionQualitySchema
>;

export const FileStateSchema = z.enum([
  'STATE_UNSPECIFIED',
  'PROCESSING',
  'ACTIVE',
  'FAILED',
]);
export type FileState = z.infer<typeof FileStateSchema>;

export const FileSourceSchema = z.enum([
  'SOURCE_UNSPECIFIED',
  'UPLOADED',
  'GENERATED',
]);
export type FileSource = z.infer<typeof FileSourceSchema>;

export const MediaModalitySchema = z.enum([
  'MODALITY_UNSPECIFIED',
  'TEXT',
  'IMAGE',
  'VIDEO',
  'AUDIO',
  'DOCUMENT',
]);
export type MediaModality = z.infer<typeof MediaModalitySchema>;

export const StartSensitivitySchema = z.enum([
  'START_SENSITIVITY_UNSPECIFIED',
  'START_SENSITIVITY_HIGH',
  'START_SENSITIVITY_LOW',
]);
export type StartSensitivity = z.infer<typeof StartSensitivitySchema>;

export const EndSensitivitySchema = z.enum([
  'END_SENSITIVITY_UNSPECIFIED',
  'END_SENSITIVITY_HIGH',
  'END_SENSITIVITY_LOW',
]);
export type EndSensitivity = z.infer<typeof EndSensitivitySchema>;

export const ActivityHandlingSchema = z.enum([
  'ACTIVITY_HANDLING_UNSPECIFIED',
  'START_OF_ACTIVITY_INTERRUPTS',
  'NO_INTERRUPTION',
]);
export type ActivityHandling = z.infer<typeof ActivityHandlingSchema>;

export const TurnCoverageSchema = z.enum([
  'TURN_COVERAGE_UNSPECIFIED',
  'TURN_INCLUDES_ONLY_ACTIVITY',
  'TURN_INCLUDES_ALL_INPUT',
]);
export type TurnCoverage = z.infer<typeof TurnCoverageSchema>;

export const FunctionResponseSchedulingSchema = z.enum([
  'SCHEDULING_UNSPECIFIED',
  'SILENT',
  'WHEN_IDLE',
  'INTERRUPT',
]);
export type FunctionResponseScheduling = z.infer<
  typeof FunctionResponseSchedulingSchema
>;

export const ScaleSchema = z.enum([
  'SCALE_UNSPECIFIED',
  'C_MAJOR_A_MINOR',
  'D_FLAT_MAJOR_B_FLAT_MINOR',
  'D_MAJOR_B_MINOR',
  'E_FLAT_MAJOR_C_MINOR',
  'E_MAJOR_D_FLAT_MINOR',
  'F_MAJOR_D_MINOR',
  'G_FLAT_MAJOR_E_FLAT_MINOR',
  'G_MAJOR_E_MINOR',
  'A_FLAT_MAJOR_F_MINOR',
  'A_MAJOR_G_FLAT_MINOR',
  'B_FLAT_MAJOR_G_MINOR',
  'B_MAJOR_A_FLAT_MINOR',
]);
export type Scale = z.infer<typeof ScaleSchema>;

export const LiveMusicPlaybackControlSchema = z.enum([
  'PLAYBACK_CONTROL_UNSPECIFIED',
  'PLAY',
  'PAUSE',
  'STOP',
  'RESET_CONTEXT',
]);
export type LiveMusicPlaybackControl = z.infer<
  typeof LiveMusicPlaybackControlSchema
>;

export const VideoMetadataSchema = z.object({
  fps: z.number().optional(),
  end_offset: z.string().optional(),
  start_offset: z.string().optional(),
});
export type VideoMetadata = z.infer<typeof VideoMetadataSchema>;
export type VideoMetadataOrDict = z.infer<typeof VideoMetadataSchema>;

export const BlobSchema = z.object({
  display_name: z.string().optional(),
  data: z.instanceof(Uint8Array).optional(),
  mime_type: z.string().optional(),
});
export type Blob = z.infer<typeof BlobSchema>;
export type BlobOrDict = z.infer<typeof BlobSchema>;

export const FileDataSchema = z.object({
  display_name: z.string().optional(),
  file_uri: z.string().optional(),
  mime_type: z.string().optional(),
});
export type FileData = z.infer<typeof FileDataSchema>;
export type FileDataOrDict = z.infer<typeof FileDataSchema>;

export const CodeExecutionResultSchema = z.object({
  outcome: OutcomeSchema.optional(),
  output: z.string().optional(),
});
export type CodeExecutionResult = z.infer<typeof CodeExecutionResultSchema>;
export type CodeExecutionResultOrDict = z.infer<
  typeof CodeExecutionResultSchema
>;

export const ExecutableCodeSchema = z.object({
  code: z.string().optional(),
  language: LanguageSchema.optional(),
});
export type ExecutableCode = z.infer<typeof ExecutableCodeSchema>;
export type ExecutableCodeOrDict = z.infer<typeof ExecutableCodeSchema>;

export const FunctionCallSchema = z.object({
  id: z.string().optional(),
  args: z.record(z.any()).optional(),
  name: z.string().optional(),
});
export type FunctionCall = z.infer<typeof FunctionCallSchema>;
export type FunctionCallOrDict = z.infer<typeof FunctionCallSchema>;

export const FunctionResponseSchema = z.object({
  will_continue: z.boolean().optional(),
  scheduling: FunctionResponseSchedulingSchema.optional(),
  id: z.string().optional(),
  name: z.string().optional(),
  response: z.record(z.any()).optional(),
});
export type FunctionResponse = z.infer<typeof FunctionResponseSchema>;
export type FunctionResponseOrDict = z.infer<typeof FunctionResponseSchema>;

export const PartSchema = z.object({
  video_metadata: VideoMetadataSchema.optional(),
  thought: z.boolean().optional(),
  inline_data: BlobSchema.optional(),
  file_data: FileDataSchema.optional(),
  thought_signature: z.instanceof(Uint8Array).optional(),
  code_execution_result: CodeExecutionResultSchema.optional(),
  executable_code: ExecutableCodeSchema.optional(),
  function_call: FunctionCallSchema.optional(),
  function_response: FunctionResponseSchema.optional(),
  text: z.string().optional(),
});
export type Part = z.infer<typeof PartSchema>;
export type PartOrDict = z.infer<typeof PartSchema>;

export const ContentSchema = z.object({
  parts: z.array(PartSchema).optional(),
  role: z.string().optional(),
});
export type Content = z.infer<typeof ContentSchema>;
export type ContentOrDict = z.infer<typeof ContentSchema>;

export const HttpRetryOptionsSchema = z.object({
  attempts: z.number().int().optional(),
  initial_delay: z.number().optional(),
  max_delay: z.number().optional(),
  exp_base: z.number().optional(),
  jitter: z.number().optional(),
  http_status_codes: z.array(z.number().int()).optional(),
});
export type HttpRetryOptions = z.infer<typeof HttpRetryOptionsSchema>;
export type HttpRetryOptionsOrDict = z.infer<typeof HttpRetryOptionsSchema>;

export const HttpOptionsSchema = z.object({
  base_url: z.string().optional(),
  api_version: z.string().optional(),
  headers: z.record(z.string()).optional(),
  timeout: z.number().int().optional(),
  client_args: z.record(z.any()).optional(),
  async_client_args: z.record(z.any()).optional(),
  extra_body: z.record(z.any()).optional(),
  retry_options: HttpRetryOptionsSchema.optional(),
});
export type HttpOptions = z.infer<typeof HttpOptionsSchema>;
export type HttpOptionsOrDict = z.infer<typeof HttpOptionsSchema>;

export const JSONSchemaTypeSchema = z.enum([
  'null',
  'boolean',
  'object',
  'array',
  'number',
  'integer',
  'string',
]);
export type JSONSchemaType = z.infer<typeof JSONSchemaTypeSchema>;

export const JSONSchemaSchema: z.ZodType<any> = z.lazy(() =>
  z.object({
    type: z
      .union([JSONSchemaTypeSchema, z.array(JSONSchemaTypeSchema)])
      .optional(),
    format: z.string().optional(),
    title: z.string().optional(),
    description: z.string().optional(),
    default: z.any().optional(),
    items: JSONSchemaSchema.optional(),
    min_items: z.number().int().optional(),
    max_items: z.number().int().optional(),
    enum: z.array(z.any()).optional(),
    properties: z.record(JSONSchemaSchema).optional(),
    required: z.array(z.string()).optional(),
    min_properties: z.number().int().optional(),
    max_properties: z.number().int().optional(),
    minimum: z.number().optional(),
    maximum: z.number().optional(),
    min_length: z.number().int().optional(),
    max_length: z.number().int().optional(),
    pattern: z.string().optional(),
    any_of: z.array(JSONSchemaSchema).optional(),
  })
);
export type JSONSchema = z.infer<typeof JSONSchemaSchema>;

export const SchemaSchema: z.ZodType<any> = z.lazy(() =>
  z.object({
    additional_properties: z.any().optional(),
    defs: z.record(SchemaSchema).optional(),
    ref: z.string().optional(),
    any_of: z.array(SchemaSchema).optional(),
    default: z.any().optional(),
    description: z.string().optional(),
    enum: z.array(z.string()).optional(),
    example: z.any().optional(),
    format: z.string().optional(),
    items: SchemaSchema.optional(),
    max_items: z.number().int().optional(),
    max_length: z.number().int().optional(),
    max_properties: z.number().int().optional(),
    maximum: z.number().optional(),
    min_items: z.number().int().optional(),
    min_length: z.number().int().optional(),
    min_properties: z.number().int().optional(),
    minimum: z.number().optional(),
    nullable: z.boolean().optional(),
    pattern: z.string().optional(),
    properties: z.record(SchemaSchema).optional(),
    property_ordering: z.array(z.string()).optional(),
    required: z.array(z.string()).optional(),
    title: z.string().optional(),
    type: TypeSchema.optional(),
  })
);
export type Schema = z.infer<typeof SchemaSchema>;
export type SchemaOrDict = z.infer<typeof SchemaSchema>;

export const ModelSelectionConfigSchema = z.object({
  feature_selection_preference: FeatureSelectionPreferenceSchema.optional(),
});
export type ModelSelectionConfig = z.infer<typeof ModelSelectionConfigSchema>;
export type ModelSelectionConfigOrDict = z.infer<
  typeof ModelSelectionConfigSchema
>;

export const GroundingMetadataSchema = z.object({
  web_search_queries: z.array(z.string()).optional(),
  retrieval_queries: z.array(z.string()).optional(),
});
export type GroundingMetadata = z.infer<typeof GroundingMetadataSchema>;

export const GenerateContentResponseUsageMetadataSchema = z.object({
  prompt_token_count: z.number().int().optional(),
  candidates_token_count: z.number().int().optional(),
  total_token_count: z.number().int().optional(),
});
export type GenerateContentResponseUsageMetadata = z.infer<
  typeof GenerateContentResponseUsageMetadataSchema
>;

export const GenerateContentConfigSchema = z.object({
  temperature: z.number().optional(),
  top_p: z.number().optional(),
  top_k: z.number().int().optional(),
  candidate_count: z.number().int().optional(),
  max_output_tokens: z.number().int().optional(),
  stop_sequences: z.array(z.string()).optional(),
  response_mime_type: z.string().optional(),
  response_schema: SchemaSchema.optional(),
  system_instruction: ContentSchema.optional(),
  tools: z.array(z.any()).optional(), // Assuming Tool is defined elsewhere
});
export type GenerateContentConfig = z.infer<typeof GenerateContentConfigSchema>;

export const LiveConnectConfigSchema = z.object({});
export type LiveConnectConfig = z.infer<typeof LiveConnectConfigSchema>;

export const AuthSchemeSchema = z.object({
  type_: z.string(),
});
export type AuthScheme = z.infer<typeof AuthSchemeSchema>;

export const AuthCredentialSchema = z.object({
  auth_type: z.string(),
});
export type AuthCredential = z.infer<typeof AuthCredentialSchema>;

export const AuthConfigSchema = z.object({
  auth_scheme: AuthSchemeSchema,
  raw_auth_credential: AuthCredentialSchema.optional(),
  exchanged_auth_credential: AuthCredentialSchema.optional(),
  credential_key: z.string().optional(),
});
export type AuthConfig = z.infer<typeof AuthConfigSchema>;

export const BaseToolSchema = z.object({
  name: z.string(),
  description: z.string(),
  is_long_running: z.boolean().default(false),
});
export type BaseTool = z.infer<typeof BaseToolSchema>;

export const LlmResponseSchema = z.object({
  content: ContentSchema.optional(),
  grounding_metadata: GroundingMetadataSchema.optional(),
  partial: z.boolean().optional(),
  turn_complete: z.boolean().optional(),
  error_code: z.string().optional(),
  error_message: z.string().optional(),
  interrupted: z.boolean().optional(),
  custom_metadata: z.record(z.any()).optional(),
  usage_metadata: GenerateContentResponseUsageMetadataSchema.optional(),
});
export type LlmResponse = z.infer<typeof LlmResponseSchema>;

export const EventActionsSchema = z.object({
  skip_summarization: z.boolean().optional(),
  state_delta: z.record(z.any()).optional(),
  artifact_delta: z.record(z.number().int()).optional(),
  transfer_to_agent: z.string().optional(),
  escalate: z.boolean().optional(),
  requested_auth_configs: z.record(AuthConfigSchema).optional(),
});
export type EventActions = z.infer<typeof EventActionsSchema>;

export const EventSchema = LlmResponseSchema.extend({
  invocation_id: z.string(),
  author: z.string(),
  actions: EventActionsSchema.default({}),
  long_running_tool_ids: z.set(z.string()).optional(),
  branch: z.string().optional(),
  id: z.string(),
  timestamp: z.number(),
});
export type Event = z.infer<typeof EventSchema>;

export const LlmRequestSchema = z.object({
  model: z.string().optional(),
  contents: z.array(ContentSchema).default([]),
  config: GenerateContentConfigSchema.optional(),
  live_connect_config: LiveConnectConfigSchema.default({}),
  tools_dict: z.record(BaseToolSchema).default({}),
});
export type LlmRequest = z.infer<typeof LlmRequestSchema>;

export const OtelHttpOptionsSchema = z.object({
  headers: z.record(z.string()).optional(),
});
export type OtelHttpOptions = z.infer<typeof OtelHttpOptionsSchema>;

export const OtelFunctionDeclarationSchema = z.object({
  description: z.string().optional(),
  name: z.string(),
  parameters: z
    .object({
      properties: z.record(
        z.object({
          type: z.string(),
        })
      ),
      required: z.array(z.string()).optional(),
      type: z.string(),
    })
    .optional(),
  response: z
    .object({
      type: z.string(),
    })
    .optional(),
});
export type OtelFunctionDeclaration = z.infer<
  typeof OtelFunctionDeclarationSchema
>;

export const OtelToolSchema = z.object({
  function_declarations: z.array(OtelFunctionDeclarationSchema).optional(),
});
export type OtelTool = z.infer<typeof OtelToolSchema>;

export const OtelGenerateContentConfigSchema = z.object({
  http_options: OtelHttpOptionsSchema.optional(),
  system_instruction: z.string().optional(),
  tools: z.array(OtelToolSchema).optional(),
  labels: z.record(z.string()).optional(),
});
export type OtelGenerateContentConfig = z.infer<
  typeof OtelGenerateContentConfigSchema
>;

export const OtelLlmRequestSchema = z.object({
  model: z.string().optional(),
  config: OtelGenerateContentConfigSchema.optional(),
  contents: z.array(ContentSchema).optional(),
});
export type OtelLlmRequest = z.infer<typeof OtelLlmRequestSchema>;

export const TokenDetailsSchema = z.object({
  modality: z.string(),
  token_count: z.number(),
});
export type TokenDetails = z.infer<typeof TokenDetailsSchema>;

export const OtelUsageMetadataSchema = z.object({
  candidates_token_count: z.number().optional(),
  candidates_tokens_details: z.array(TokenDetailsSchema).optional(),
  prompt_token_count: z.number().optional(),
  prompt_tokens_details: z.array(TokenDetailsSchema).optional(),
  total_token_count: z.number().optional(),
  traffic_type: TrafficTypeSchema.optional(),
});
export type OtelUsageMetadata = z.infer<typeof OtelUsageMetadataSchema>;

export const OtelLlmResponseSchema = z.object({
  content: ContentSchema.optional(),
  usage_metadata: OtelUsageMetadataSchema.optional(),
});
export type OtelLlmResponse = z.infer<typeof OtelLlmResponseSchema>;
