import {WANDB_URL} from './constants';
import {isOp} from './op';

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
    return `${WANDB_URL}/${this.projectId}/weave/objects/${this.objectId}/versions/${this.digest}`;
  }
}

export class WeaveObject {
  __savedRef?: ObjectRef | Promise<ObjectRef>;

  constructor(protected _baseParameters: WeaveObjectParameters) {}

  className() {
    return Object.getPrototypeOf(this).constructor.name;
  }

  saveAttrs() {
    const attrs: {[key: string]: any} = {};

    const nonUnderscoreKeys = Object.keys(this).filter(key => !key.startsWith('_'));

    // Include values first (non-functions)
    for (const key of Object.keys(this)) {
      // @ts-ignore
      const value: any = this[key];
      if (typeof value !== 'function') {
        attrs[key] = value;
      }
    }

    // Then ops
    for (const key of nonUnderscoreKeys) {
      // @ts-ignore
      const value: any = this[key];
      if (isOp(value)) {
        attrs[key] = value;
      }
    }

    return attrs;
  }

  get id() {
    return this._baseParameters.id ?? this.constructor.name;
  }

  get description() {
    return this._baseParameters.description;
  }
}

export function getClassChain(instance: WeaveObject): string[] {
  const bases: string[] = [];
  let currentProto = Object.getPrototypeOf(instance);

  while (currentProto && currentProto.constructor.name !== 'Object') {
    const className = currentProto.constructor.name === 'WeaveObject' ? 'Object' : currentProto.constructor.name;
    bases.push(className);
    currentProto = Object.getPrototypeOf(currentProto);
  }
  // Frontend does this overly specific check for datasets, so push BaseModel to ensure we pass for now.
  //   data._type === 'Dataset' &&
  //   data._class_name === 'Dataset' &&
  //   _.isEqual(data._bases, ['Object', 'BaseModel'])
  bases.push('BaseModel');

  return bases;
}
