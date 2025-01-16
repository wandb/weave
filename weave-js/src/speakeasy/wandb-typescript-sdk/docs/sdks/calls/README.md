# Calls
(*calls*)

## Overview

### Available Operations

* [start](#start) - Call Start
* [end](#end) - Call End
* [upsertBatch](#upsertbatch) - Call Start Batch
* [delete](#delete) - Calls Delete
* [update](#update) - Call Update
* [read](#read) - Call Read
* [queryStats](#querystats) - Calls Query Stats
* [streamQuery](#streamquery) - Calls Query Stream

## start

Call Start

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.start({
    start: {
      projectId: "<id>",
      opName: "<value>",
      startedAt: new Date("2023-03-07T00:06:01.890Z"),
      attributes: {},
      inputs: {},
    },
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsStart } from "wandb/funcs/callsStart.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsStart(wandb, {
    start: {
      projectId: "<id>",
      opName: "<value>",
      startedAt: new Date("2023-03-07T00:06:01.890Z"),
      attributes: {},
      inputs: {},
    },
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsStartMutation
} from "wandb/react-query/callsStart.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallStartReq](../../models/components/callstartreq.md)                                                                                                             | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallStartRes](../../models/components/callstartres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## end

Call End

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.end({
    end: {
      projectId: "<id>",
      id: "<id>",
      endedAt: new Date("2023-10-15T10:16:55.532Z"),
      summary: {
        additionalProperties: {

        },
      },
    },
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsEnd } from "wandb/funcs/callsEnd.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsEnd(wandb, {
    end: {
      projectId: "<id>",
      id: "<id>",
      endedAt: new Date("2023-10-15T10:16:55.532Z"),
      summary: {
        additionalProperties: {
  
        },
      },
    },
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsEndMutation
} from "wandb/react-query/callsEnd.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallEndReq](../../models/components/callendreq.md)                                                                                                                 | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallEndRes](../../models/components/callendres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## upsertBatch

Call Start Batch

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.upsertBatch({
    batch: [
      {
        req: {
          start: {
            projectId: "<id>",
            opName: "<value>",
            startedAt: new Date("2023-07-09T04:54:32.741Z"),
            attributes: {},
            inputs: {},
          },
        },
      },
      {
        req: {
          end: {
            projectId: "<id>",
            id: "<id>",
            endedAt: new Date("2025-08-10T08:47:16.049Z"),
            summary: {
              additionalProperties: {

              },
            },
          },
        },
      },
    ],
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsUpsertBatch } from "wandb/funcs/callsUpsertBatch.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsUpsertBatch(wandb, {
    batch: [
      {
        req: {
          start: {
            projectId: "<id>",
            opName: "<value>",
            startedAt: new Date("2023-07-09T04:54:32.741Z"),
            attributes: {},
            inputs: {},
          },
        },
      },
      {
        req: {
          end: {
            projectId: "<id>",
            id: "<id>",
            endedAt: new Date("2025-08-10T08:47:16.049Z"),
            summary: {
              additionalProperties: {
  
              },
            },
          },
        },
      },
    ],
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsUpsertBatchMutation
} from "wandb/react-query/callsUpsertBatch.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallCreateBatchReq](../../models/components/callcreatebatchreq.md)                                                                                                 | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallCreateBatchRes](../../models/components/callcreatebatchres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## delete

Calls Delete

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.delete({
    projectId: "<id>",
    callIds: [

    ],
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsDelete } from "wandb/funcs/callsDelete.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsDelete(wandb, {
    projectId: "<id>",
    callIds: [
  
    ],
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsDeleteMutation
} from "wandb/react-query/callsDelete.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallsDeleteReq](../../models/components/callsdeletereq.md)                                                                                                         | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallsDeleteRes](../../models/components/callsdeleteres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## update

Call Update

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.update({
    projectId: "<id>",
    callId: "<id>",
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsUpdate } from "wandb/funcs/callsUpdate.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsUpdate(wandb, {
    projectId: "<id>",
    callId: "<id>",
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsUpdateMutation
} from "wandb/react-query/callsUpdate.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallUpdateReq](../../models/components/callupdatereq.md)                                                                                                           | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallUpdateRes](../../models/components/callupdateres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## read

Call Read

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.read({
    projectId: "<id>",
    id: "<id>",
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsRead } from "wandb/funcs/callsRead.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsRead(wandb, {
    projectId: "<id>",
    id: "<id>",
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsReadMutation
} from "wandb/react-query/callsRead.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallReadReq](../../models/components/callreadreq.md)                                                                                                               | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallReadRes](../../models/components/callreadres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## queryStats

Calls Query Stats

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.queryStats({
    projectId: "<id>",
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsQueryStats } from "wandb/funcs/callsQueryStats.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsQueryStats(wandb, {
    projectId: "<id>",
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsQueryStatsMutation
} from "wandb/react-query/callsQueryStats.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallsQueryStatsReq](../../models/components/callsquerystatsreq.md)                                                                                                 | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CallsQueryStatsRes](../../models/components/callsquerystatsres.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |

## streamQuery

Calls Query Stream

### Example Usage

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.calls.streamQuery({
    projectId: "<id>",
    expandColumns: [
      "inputs.self.message",
      "inputs.model.prompt",
    ],
  });

  // Handle the result
  console.log(result);
}

run();
```

### Standalone function

The standalone function version of this method:

```typescript
import { WandbCore } from "wandb/core.js";
import { callsStreamQuery } from "wandb/funcs/callsStreamQuery.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await callsStreamQuery(wandb, {
    projectId: "<id>",
    expandColumns: [
      "inputs.self.message",
      "inputs.model.prompt",
    ],
  });

  if (!res.ok) {
    throw res.error;
  }

  const { value: result } = res;

  // Handle the result
  console.log(result);
}

run();
```

### React hooks and utilities

This method can be used in React components through the following hooks and
associated utilities.

> Check out [this guide][hook-guide] for information about each of the utilities
> below and how to get started using React hooks.

[hook-guide]: ../../../REACT_QUERY.md

```tsx
import {
  // Mutation hook for triggering the API call.
  useCallsStreamQueryMutation
} from "wandb/react-query/callsStreamQuery.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CallsQueryReq](../../models/components/callsqueryreq.md)                                                                                                           | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[any](../../models/.md)\>**

### Errors

| Error Type                   | Status Code                  | Content Type                 |
| ---------------------------- | ---------------------------- | ---------------------------- |
| errors.BadRequest            | 400, 413, 414, 415, 431      | application/json             |
| errors.Unauthorized          | 401, 403, 407                | application/json             |
| errors.NotFound              | 404                          | application/json             |
| errors.Timeout               | 408                          | application/json             |
| errors.HTTPValidationError   | 422                          | application/json             |
| errors.RateLimited           | 429                          | application/json             |
| errors.InternalServerError   | 500, 502, 503, 506, 507, 508 | application/json             |
| errors.NotFound              | 501, 505                     | application/json             |
| errors.Timeout               | 504                          | application/json             |
| errors.BadRequest            | 510                          | application/json             |
| errors.Unauthorized          | 511                          | application/json             |
| errors.APIError              | 4XX, 5XX                     | \*/\*                        |