export interface QueryArg {
  name: string;
  value: any;
}

export interface QueryField {
  name: string;
  args?: QueryArg[];

  // TODO: make fields? optional, it's annoying
  fields: QueryField[];
  alias?: string;
}

export interface Query {
  queryFields: QueryField[];
}
