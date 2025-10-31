// TODO: Implement parseUri

/**
 * Represents a reference to a Weave call.
 */
export class CallRef {
  constructor(
    public entity: string,
    public project: string,
    public callId: string
  ) {}

  /**
   * Returns the call URI in weave:/// format.
   */
  public toString(): string {
    return `weave:///${this.entity}/${this.project}/call/${this.callId}`;
  }
}
