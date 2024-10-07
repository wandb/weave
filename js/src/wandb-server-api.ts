import {userAgent} from './user-agent';

const VIEWER_DEFAULT_ENTITY_QUERY = `
query DefaultEntity {
    viewer {
        username
        defaultEntity {
            name
        }
    }
}
`;

export class WandbServerApi {
  constructor(
    private host: string,
    private apiKey: string
  ) {}

  private async gqlRequest(query: string, variables: Record<string, any> = {}) {
    try {
      const resp = await fetch(`${this.host}/graphql`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': userAgent(),
          Authorization: `Basic ${Buffer.from(`api:${this.apiKey}`).toString('base64')}`,
        },
        body: JSON.stringify({query, variables}),
      });
      if (!resp.ok) {
        throw new Error(`HTTP error! status: ${resp.status}, statusText: ${resp.statusText}`);
      }

      const res = await resp.json();
      if (res.errors) {
        throw new Error(`GraphQL Error: ${JSON.stringify(res.errors)}`);
      }

      return res.data;
    } catch (error) {
      console.error('Error in graphqlRequest:', error);
      throw error;
    }
  }

  async defaultEntityName() {
    try {
      const result = await this.gqlRequest(VIEWER_DEFAULT_ENTITY_QUERY);
      if (!result.viewer || !result.viewer.defaultEntity || !result.viewer.defaultEntity.name) {
        throw new Error('Default entity name not found in the response');
      }
      return result.viewer.defaultEntity.name;
    } catch (error) {
      console.error('Error in defaultEntityName:', error);
      throw error;
    }
  }
}
