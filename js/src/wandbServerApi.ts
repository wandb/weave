import {userAgent} from './userAgent';

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
  private host: string;
  private apiKey: string;

  constructor(host: string, apiKey: string) {
    this.host = host;
    this.apiKey = apiKey;
  }

  private async graphqlRequest(
    query: string,
    variables: Record<string, any> = {}
  ) {
    try {
      const response = await fetch(`${this.host}/graphql`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'User-Agent': userAgent(),
          Authorization: `Basic ${Buffer.from(`api:${this.apiKey}`).toString('base64')}`,
        },
        body: JSON.stringify({
          query,
          variables,
        }),
      });

      if (!response.ok) {
        throw new Error(
          `HTTP error! status: ${response.status}, statusText: ${response.statusText}`
        );
      }

      const result = await response.json();

      if (result.errors) {
        throw new Error(`GraphQL Error: ${JSON.stringify(result.errors)}`);
      }

      return result.data;
    } catch (error) {
      console.error('Error in graphqlRequest:', error);
      throw error;
    }
  }

  async defaultEntityName() {
    try {
      const result = await this.graphqlRequest(VIEWER_DEFAULT_ENTITY_QUERY);
      if (
        !result.viewer ||
        !result.viewer.defaultEntity ||
        !result.viewer.defaultEntity.name
      ) {
        throw new Error('Default entity name not found in the response');
      }
      return result.viewer.defaultEntity.name;
    } catch (error) {
      console.error('Error in defaultEntityName:', error);
      throw error;
    }
  }
}
