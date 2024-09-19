export interface WeaveObjectParameters {
  id?: string;
  description?: string;
}

export class ObjectRef {
  constructor(
    public projectId: string,
    public objectId: string,
    public digest: string
  ) {}

  public uri() {
    return `weave:///${this.projectId}/object/${this.objectId}:${this.digest}`;
  }

  public ui_url() {
    return `https://wandb.ai/${this.projectId}/weave/objects/${this.objectId}/versions/${this.digest}`;
  }
}

export class WeaveObject {
  saveAttrNames: string[] = [];
  __savedRef?: ObjectRef | Promise<ObjectRef>;

  constructor(protected baseParameters: WeaveObjectParameters) {}

  className() {
    return Object.getPrototypeOf(this).constructor.name;
  }

  saveAttrs() {
    const attrs: { [key: string]: any } = {};
    this.saveAttrNames.forEach((attr) => {
      // @ts-ignore
      attrs[attr] = this[attr];
    });
    return attrs;
  }

  get id() {
    return this.baseParameters.id ?? this.constructor.name;
  }

  get description() {
    return this.baseParameters.description;
  }
}

export function getClassChain(instance: WeaveObject): string[] {
  const bases: string[] = [];
  let currentProto = Object.getPrototypeOf(instance);

  while (currentProto && currentProto.constructor.name !== "Object") {
    const className =
      currentProto.constructor.name === "WeaveObject"
        ? "Object"
        : currentProto.constructor.name;
    bases.push(className);
    currentProto = Object.getPrototypeOf(currentProto);
  }
  // Frontend does this overly specific check for datasets, so push BaseModel to ensure we pass for now.
  //   data._type === 'Dataset' &&
  //   data._class_name === 'Dataset' &&
  //   _.isEqual(data._bases, ['Object', 'BaseModel'])
  bases.push("BaseModel");

  return bases;
}
