import { WeaveClient } from "./weaveClient";
import { getApiKey } from "./settings";
import { WandbServerApi } from "./wandbServerApi";
import { Api as TraceServerApi } from "./traceServerApi";
import { InMemoryTraceServer } from "./inMemoryTraceServer";
import { ConcurrencyLimiter } from "./concurrencyLimit";
import { createFetchWithRetry } from "./retry";

// Global client instance
export let globalClient: WeaveClient | null = null;

export async function init(projectName: string): Promise<WeaveClient> {
  const host = "https://api.wandb.ai";
  const apiKey = getApiKey();

  const headers: Record<string, string> = {
    "User-Agent": `W&B Internal JS Client ${process.env.VERSION || "unknown"}`,
    Authorization: `Basic ${Buffer.from(`api:${apiKey}`).toString("base64")}`,
  };

  try {
    const wandbServerApi = new WandbServerApi(host, apiKey);
    const defaultEntityName = await wandbServerApi.defaultEntityName();
    const projectId = `${defaultEntityName}/${projectName}`;

    const retryFetch = createFetchWithRetry({
      baseDelay: 1000,
      maxDelay: 5 * 60 * 1000, // 5 minutes
      maxRetryTime: 12 * 60 * 60 * 1000, // 12 hours
      retryOnStatus: (status: number) =>
        status === 429 || (status >= 500 && status < 600),
    });
    const concurrencyLimiter = new ConcurrencyLimiter(20);
    const concurrencyLimitedFetch = concurrencyLimiter.limitFunction(
      async (...fetchParams: Parameters<typeof fetch>) => {
        const result = await retryFetch(...fetchParams);
        // Useful for debugging
        // console.log(`Active: ${concurrencyLimiter.active} Pending: ${concurrencyLimiter.pending}`);
        return result;
      }
    );

    const traceServerApi = new TraceServerApi({
      baseUrl: "https://trace.wandb.ai",
      baseApiParams: {
        headers: headers,
      },
      customFetch: concurrencyLimitedFetch,
    });

    globalClient = new WeaveClient(traceServerApi, wandbServerApi, projectId);
    console.log(`Initializing project: ${projectId}`);
    return globalClient;
  } catch (error) {
    console.error("Error during initialization:", error);
    throw error;
  }
}

export function initWithCustomTraceServer(
  projectName: string,
  customTraceServer: InMemoryTraceServer
) {
  globalClient = new WeaveClient(
    customTraceServer as unknown as TraceServerApi<any>,
    {} as WandbServerApi, // Placeholder, as we don't use WandbServerApi in this case
    projectName,
    true
  );
}
