# Costs
(*costs*)

## Overview

### Available Operations

* [create](#create) - Cost Create
* [query](#query) - Cost Query
* [purge](#purge) - Cost Purge

## create

Cost Create

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
  const result = await wandb.costs.create({
    projectId: "entity/project",
    costs: {
      "key": {
        promptTokenCost: 1184.23,
        completionTokenCost: 6584.66,
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
import { costsCreate } from "wandb/funcs/costsCreate.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await costsCreate(wandb, {
    projectId: "entity/project",
    costs: {
      "key": {
        promptTokenCost: 1184.23,
        completionTokenCost: 6584.66,
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
  useCostsCreateMutation
} from "wandb/react-query/costsCreate.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CostCreateReq](../../models/components/costcreatereq.md)                                                                                                           | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CostCreateRes](../../models/components/costcreateres.md)\>**

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

## query

Cost Query

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
  const result = await wandb.costs.query({
    projectId: "entity/project",
    fields: [
      "id",
      "llm_id",
      "prompt_token_cost",
      "completion_token_cost",
      "prompt_token_cost_unit",
      "completion_token_cost_unit",
      "effective_date",
      "provider_id",
    ],
    limit: 10,
    offset: 0,
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
import { costsQuery } from "wandb/funcs/costsQuery.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await costsQuery(wandb, {
    projectId: "entity/project",
    fields: [
      "id",
      "llm_id",
      "prompt_token_cost",
      "completion_token_cost",
      "prompt_token_cost_unit",
      "completion_token_cost_unit",
      "effective_date",
      "provider_id",
    ],
    limit: 10,
    offset: 0,
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
  useCostsQueryMutation
} from "wandb/react-query/costsQuery.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CostQueryReq](../../models/components/costqueryreq.md)                                                                                                             | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CostQueryRes](../../models/components/costqueryres.md)\>**

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

## purge

Cost Purge

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
  const result = await wandb.costs.purge({
    projectId: "entity/project",
    query: [
      "<value>",
      "<value>",
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
import { costsPurge } from "wandb/funcs/costsPurge.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await costsPurge(wandb, {
    projectId: "entity/project",
    query: [
      "<value>",
      "<value>",
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
  useCostsPurgeMutation
} from "wandb/react-query/costsPurge.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.CostPurgeReq](../../models/components/costpurgereq.md)                                                                                                             | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.CostPurgeRes](../../models/components/costpurgeres.md)\>**

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