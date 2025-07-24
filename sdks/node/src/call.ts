import {getGlobalClient} from './clientApi';
import {CallSchema} from './generated/traceServerApi';

const MAX_DISPLAY_NAME_LENGTH = 1000;

export enum CallState {
  uninitialized,
  pending,
  finished,
  failed,
}

export class InternalCall {
  _state: CallState = CallState.uninitialized;

  public callSchema: Partial<CallSchema> = {};

  constructor() {}

  public async setDisplayName(displayName: string) {
    const elidedDisplayName = elideDisplayName(displayName);
    this.callSchema.display_name = elidedDisplayName;

    if ([CallState.pending, CallState.uninitialized].includes(this._state)) {
      // nothing needs to be done here, the call will be updated when it is finished
      return;
    }

    const client = getGlobalClient();
    if (!client) {
      throw new Error('Weave is not initialized');
    }
    await client.updateCall(this.callSchema.id!, elidedDisplayName);
  }

  public updateWithCallSchemaData(callSchemaExchangeData: Partial<CallSchema>) {
    Object.assign(this.callSchema, callSchemaExchangeData);
  }

  // This proxy is used to access the call schema properties, we don't directly expose the InternalCall instance
  get proxy(): Call {
    return new Proxy(
      this.callSchema,
      buildProxyHandlers(this.callSchema, this)
    ) as unknown as Call;
  }

  set state(state: CallState) {
    this._state = state;
  }
}

function buildProxyHandlers(
  callSchema: Partial<CallSchema>,
  internalCall: InternalCall
) {
  return {
    get(target: Partial<CallSchema>, prop: string) {
      if (prop === 'toJSON') {
        return (...args: any[]) => JSON.stringify(callSchema, ...args);
      }

      if (prop === 'setDisplayName') {
        return internalCall.setDisplayName.bind(internalCall);
      }

      // If the property exists on the call schema, return it
      if (Reflect.has(internalCall.callSchema, prop)) {
        return Reflect.get(internalCall.callSchema, prop);
      }

      return undefined;
    },
    set(target: Partial<CallSchema>, prop: string, value: any) {
      // Disallow setting properties on the call schema
      return false;
    },
  };
}

export interface Call extends CallSchema {
  setDisplayName(displayName: string): Promise<void>;
}

function elideDisplayName(name: string) {
  if (name.length > MAX_DISPLAY_NAME_LENGTH) {
    console.warn(
      `Display name ${name} is longer than ${MAX_DISPLAY_NAME_LENGTH} characters.  It will be truncated!`
    );
    return name.slice(0, MAX_DISPLAY_NAME_LENGTH - 3) + '...';
  }
  return name;
}
