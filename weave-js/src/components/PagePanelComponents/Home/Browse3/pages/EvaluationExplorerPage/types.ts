export type EvaluationExplorationConfig = {
  // The definition of the evaluation to run
  evaluationDefinition: {
    // The Weave Ref pointing to the evaluation definition
    originalSourceRef: string | null;
    // Whether the properties deviated from the referenced source
    dirtied: boolean;
    properties: {
      // The name of the evaluation
      name: string;
      // The description of the evaluation
      description: string;
      // The definition of the dataset to use
      dataset: {
        // The Weave Ref pointing to the dataset definition
        originalSourceRef: string | null;
        // Whether the dataset definition is dirty
        dirtied: boolean;
        properties: {
          // The name of the dataset
          name: string;
          // The description of the dataset
          description: string;
          // The rows of the dataset
          rows: {
            // The content digest hash for tracking changes
            originalSourceDigest: string | null;
            // Whether this row has been modified from its source
            dirtied: boolean;
            // The actual data for this row as key-value pairs
            data: Record<string, any>;
          }[];
        };
      };
      // The array of scorer functions to evaluate model outputs
      scorers: Array<{
        // The Weave Ref pointing to the scorer definition
        originalSourceRef: string | null;
        // Determines if the properties deviated from the referenced source
        dirtied: boolean;
        // The properties of the scorer
        properties: {
          // The name of the scorer function
          name: string;
          // The description of what this scorer evaluates
          description: string;
          // The system prompt template for the scorer LLM
          systemPromptTemplate: string;
          // The prompt template for scoring model outputs
          scorerPromptTemplate: string;
          // The expected output schema for the scorer results
          outputSchema: JSONSchema;
        };
      }>;
    };
  };
  // The array of models to evaluate
  models: Array<{
    // The Weave Ref pointing to the model definition
    originalSourceRef: string | null;
    // Whether the model definition is dirty
    dirtied: boolean;
    // The properties of the model
    properties: {
      // The name of the model
      name: string;
      // The description of the model
      description: string;
      // The system prompt template for the model
      systemPromptTemplate: string;
      // The prompt template for the model's main task
      modelPromptTemplate: string;
      // The expected output schema for the model
      outputSchema: JSONSchema;
    };
  }>;
};

// JSON Schema type for defining structured outputs
// Used to validate and describe the expected format of model and scorer outputs
type JSONSchema = {
  // The JSON Schema type (e.g., "object", "string", "number", "array", "boolean")
  type: string;
  // Object properties definition (when type is "object")
  properties?: Record<string, JSONSchema>;
  // Array items definition (when type is "array")
  items?: JSONSchema;
  // Required properties for objects
  required?: string[];
  // Additional properties allowed in objects
  additionalProperties?: boolean | JSONSchema;
  // Description of what this schema represents
  description?: string;
  // Default value if not provided
  default?: any;
  // Enum of allowed values
  enum?: any[];
  // Additional schema properties as needed
  [key: string]: any;
};
