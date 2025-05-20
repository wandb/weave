export type KnownProvider =
  | 'BAAI'
  | 'deepseek-ai'
  | 'ibm-granite'
  | 'meta-llama'
  | 'microsoft'
  | 'mistralai';
export type Provider = KnownProvider | string;

// TODO: Maybe use ModelData or something so we can save Model for an object that has attached logic
export type ModelId = string;

export type Model = {
  // Model id scoped with provider
  id: ModelId;

  // This string is used for categorization in the Playground
  provider: string;

  // id used in Weave's playground - this inconsistently scope by provider
  id_playground: string;

  // TODO: Decide how we want to handle this - right now we are constructing url_huggingface from it
  id_huggingface?: string;

  // What we want to show in the UI, e.g. maybe "DeepSeek R1" instead of "DeepSeek-R1"
  label?: string;

  // Short description of the model for a tile.
  // TODO: Confirm values
  descriptionShort?: string;
  descriptionMedium?: string;

  // Taken from spreadsheet, maybe eventually have exact date we could compute from
  launchDate?: string;

  // Hugging Face likes count
  likes?: number;

  // The maximum number of tokens the model can attend to at once
  contextWindow?: number;

  // See https://weightsandbiases.slack.com/archives/C08RU04P36G/p1747854100749529?thread_ts=1747770351.952239&cid=C08RU04P36G
  priceCentsPerBillionTokensInput?: number;
  priceCentsPerBillionTokensOutput?: number;

  modalities?: string[];

  url_huggingface?: string;
  card: {
    text: string;
    data: Record<string, any>;
  };
};

export type Models = Model[];

export type ModelInfo = {
  // Todo: Optional cache of summary information?
  models: Models;
};
