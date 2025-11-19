import {requireGlobalClient} from './clientApi';
import {isOp} from './op';
import {getGlobalDomain} from './urls';
import {parseWeaveUri} from './uriParser';

export interface Callable {}

export interface WeaveObjectParameters {
  name?: string;
  description?: string;
}

/**
 * Represents a reference to a saved Weave object.
 *
 * Generally, end users will not need to interact with this class directly.
 *
 * An ObjectRef contains the project ID, object ID, and digest that uniquely identify
 * a saved object in Weave's storage system.
 *
 * @example
 * const ref = new ObjectRef('my-project', 'abc123', 'def456');
 * const uri = ref.uri(); // weave:///my-project/object/abc123:def456
 */
export class ObjectRef {
  constructor(
    public projectId: string,
    public objectId: string,
    public digest: string
  ) {}

  // TODO: Add extra

  /**
   * Creates an ObjectRef from a Weave URI string.
   *
   * @param uri - A Weave URI in the format: weave:///entity/project/object/name:digest
   * @returns A new ObjectRef instance
   * @throws Error if the URI format is invalid or not an object ref
   *
   * @example
   * const ref = ObjectRef.fromUri('weave:///my-entity/my-project/object/my-dataset:abc123');
   */
  public static fromUri(uri: string): ObjectRef {
    const parsed = parseWeaveUri(uri);

    if (!parsed || parsed.type !== 'object') {
      throw new Error(
        `Invalid object ref URI: ${uri}. Expected format: weave:///entity/project/object/name:digest`
      );
    }

    const projectId = `${parsed.entity}/${parsed.project}`;
    return new ObjectRef(projectId, parsed.name, parsed.digest);
  }

  public uri() {
    return `weave:///${this.projectId}/object/${this.objectId}:${this.digest}`;
  }

  public ui_url() {
    const domain = getGlobalDomain();
    return `https://${domain}/${this.projectId}/weave/objects/${this.objectId}/versions/${this.digest}`;
  }

  public async get() {
    const client = requireGlobalClient();
    return await client.get(this);
  }
}

export class WeaveObject {
  __savedRef?: ObjectRef | Promise<ObjectRef>;

  constructor(protected _baseParameters: WeaveObjectParameters) {}

  saveAttrs() {
    const attrs: {[key: string]: any} = {
      name: this._baseParameters?.name,
      description: this._baseParameters?.description,
    };

    for (const key of Object.keys(this)) {
      if (!key.startsWith('_')) {
        // @ts-ignore
        const value: any = this[key];
        if (isOp(value) || typeof value !== 'function') {
          attrs[key] = value;
        }
      }
    }

    return attrs;
  }

  get name() {
    return this._baseParameters.name ?? this.constructor.name;
  }

  get description() {
    return this._baseParameters.description;
  }
}

export function getClassChain(instance: WeaveObject): string[] {
  const bases: string[] = [];
  let currentProto = Object.getPrototypeOf(instance);

  while (currentProto && currentProto.constructor.name !== 'Object') {
    const className =
      currentProto.constructor.name === 'WeaveObject'
        ? 'Object'
        : currentProto.constructor.name;
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
