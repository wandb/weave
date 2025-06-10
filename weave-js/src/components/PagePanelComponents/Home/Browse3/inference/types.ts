import {createContext} from 'react';

export type ModelId = string;

export type KnownSource =
  | 'BAAI'
  | 'deepseek-ai'
  | 'ibm-granite'
  | 'meta-llama'
  | 'microsoft'
  | 'mistralai';
export type Source = KnownSource | string;

// Status of the model - for future use, imagining values like:
// hosted - CoreWeave hosted model, live, ready to use.
// deployable - Models that you can deploy to a CoreWeave cluster
// usable - There is an API key configured in scope, you can use this in the playground of the project
// available - There is no API key configured in scope, but if you provide one we can connect to the model
// connected - Used for models we
// indexed - You can't use this model in our system, but we have metadata about it.
export type ModelStatus = 'hosted';

// This controls the API style we show and playground availability.
export type ApiStyle = 'chat' | 'embedding';

export type Modality = 'Text' | 'Vision' | 'Embedding';

// TODO: Fix snake case to camel case
// TODO: Maybe use name ModelData or something so we can save Model for an object that has attached logic
export type Model = {
  // Model id scoped with provider
  id: ModelId;

  // This is who is hosting the model.
  // This string is used for categorization in the Playground
  provider: string;

  // This is who the model is from.
  // This string is used for showing an icon.
  source: string;

  status: ModelStatus;

  // id used in Weave's playground - this is inconsistently scoped py provider currently
  // For hosted current thinking is that it will be the same as idHuggingFace but having
  // separate field gives us flexibility to use this for custom or non-hosted models in the future.
  idPlayground: string;

  // TODO: Decide how we want to handle this - right now we are constructing urlHuggingFace from it
  idHuggingFace?: string;

  // What we want to show in the UI, e.g. maybe "DeepSeek R1" instead of "DeepSeek-R1"
  label?: string;

  // Short description of the model for a tile.
  descriptionShort?: string;

  // Longer description of the model for the details page.
  descriptionMedium?: string;

  // Taken from spreadsheet, maybe eventually have exact date we could compute from
  launchDate?: string;

  // Hugging Face data
  likesHuggingFace?: number;
  downloadsHuggingFace?: number;

  // The maximum number of tokens the model can attend to at once
  contextWindow?: number;

  // See https://weightsandbiases.slack.com/archives/C08RU04P36G/p1747854100749529?thread_ts=1747770351.952239&cid=C08RU04P36G
  priceCentsPerBillionTokensInput?: number;
  priceCentsPerBillionTokensOutput?: number;

  modalities?: Modality[];

  apiStyle: ApiStyle;

  supportsFunctionCalling?: boolean;

  urlHuggingFace?: string;
  card: {
    text: string;
    data: Record<string, any>;
  };
};

export type Models = Model[];

export type ModelInfo = {
  // TODO: Optional cache of summary information?
  models: Models;
};

export type SelectedState = {
  selected: ModelId[];
  selectedWithPlayground: ModelId[];
};

// The Inference code living in Weave needs to be able to do things like
// create a project like a quickstart does. Rather than move or duplicate code
// from core we wrap inference pages with a context object that has the necessary
// information and methods.
export type InferenceContextType = {
  isLoggedIn: boolean;
  isInferenceEnabled: boolean;
  availabilityMessage: string;
  playgroundEntity: string;
  playgroundProject: string;
  projectExists: boolean | undefined;
  ensureProjectExists: () => Promise<void>;
};

export const InferenceContext = createContext<InferenceContextType | undefined>(
  undefined
);
