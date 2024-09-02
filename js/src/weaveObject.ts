export interface WeaveObjectParameters {
    id?: string;
    description?: string;
}

export class ObjectRef {
    constructor(public projectId: string, public objectId: string, public digest: string) { }

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

    constructor(private baseParameters: WeaveObjectParameters) { }

    className() {
        return Object.getPrototypeOf(this).constructor.name;
    }

    saveAttrs() {
        const attrs: { [key: string]: any } = {};
        this.saveAttrNames.forEach(attr => {
            // @ts-ignore
            attrs[attr] = this[attr];
        });
        return attrs;
    }

    id() {
        return this.baseParameters.id;
    }

    description() {
        return this.baseParameters.description;
    }
}


export function getClassChain(instance: WeaveObject): string[] {
    const bases: string[] = [];
    let currentProto = Object.getPrototypeOf(instance);

    while (currentProto && currentProto.constructor.name !== 'Object') {
        bases.push(currentProto.constructor.name);
        currentProto = Object.getPrototypeOf(currentProto);
    }

    return bases;
}