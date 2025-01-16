# Objects
(*objects*)

## Overview

### Available Operations

* [create](#create) - Obj Create
* [read](#read) - Obj Read
* [query](#query) - Objs Query

## create

Obj Create

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
  const result = await wandb.objects.create({
    obj: {
      projectId: "<id>",
      objectId: "<id>",
      val: "<value>",
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
import { objectsCreate } from "wandb/funcs/objectsCreate.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await objectsCreate(wandb, {
    obj: {
      projectId: "<id>",
      objectId: "<id>",
      val: "<value>",
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
  useObjectsCreateMutation
} from "wandb/react-query/objectsCreate.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.ObjCreateReq](../../models/components/objcreatereq.md)                                                                                                             | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.ObjCreateRes](../../models/components/objcreateres.md)\>**

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

Obj Read

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
  const result = await wandb.objects.read({
    projectId: "<id>",
    objectId: "<id>",
    digest: "<value>",
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
import { objectsRead } from "wandb/funcs/objectsRead.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await objectsRead(wandb, {
    projectId: "<id>",
    objectId: "<id>",
    digest: "<value>",
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
  useObjectsReadMutation
} from "wandb/react-query/objectsRead.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.ObjReadReq](../../models/components/objreadreq.md)                                                                                                                 | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.ObjReadRes](../../models/components/objreadres.md)\>**

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

Objs Query

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
  const result = await wandb.objects.query({
    projectId: "user/project",
    filter: {
      baseObjectClasses: [
        "Dataset",
      ],
      objectIds: [
        "my_favorite_dataset",
      ],
      isOp: true,
      latestOnly: false,
    },
    limit: 100,
    offset: 0,
    sortBy: [
      {
        field: "created_at",
        direction: "desc",
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
import { objectsQuery } from "wandb/funcs/objectsQuery.js";

// Use `WandbCore` for best tree-shaking performance.
// You can create one instance of it to use across an application.
const wandb = new WandbCore({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const res = await objectsQuery(wandb, {
    projectId: "user/project",
    filter: {
      baseObjectClasses: [
        "Dataset",
      ],
      objectIds: [
        "my_favorite_dataset",
      ],
      isOp: true,
      latestOnly: false,
    },
    limit: 100,
    offset: 0,
    sortBy: [
      {
        field: "created_at",
        direction: "desc",
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
  useObjectsQueryMutation
} from "wandb/react-query/objectsQuery.js";
```

### Parameters

| Parameter                                                                                                                                                                      | Type                                                                                                                                                                           | Required                                                                                                                                                                       | Description                                                                                                                                                                    |
| ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `request`                                                                                                                                                                      | [components.ObjQueryReq](../../models/components/objqueryreq.md)                                                                                                               | :heavy_check_mark:                                                                                                                                                             | The request object to use for the request.                                                                                                                                     |
| `options`                                                                                                                                                                      | RequestOptions                                                                                                                                                                 | :heavy_minus_sign:                                                                                                                                                             | Used to set various options for making HTTP requests.                                                                                                                          |
| `options.fetchOptions`                                                                                                                                                         | [RequestInit](https://developer.mozilla.org/en-US/docs/Web/API/Request/Request#options)                                                                                        | :heavy_minus_sign:                                                                                                                                                             | Options that are passed to the underlying HTTP request. This can be used to inject extra headers for examples. All `Request` options, except `method` and `body`, are allowed. |
| `options.retries`                                                                                                                                                              | [RetryConfig](../../lib/utils/retryconfig.md)                                                                                                                                  | :heavy_minus_sign:                                                                                                                                                             | Enables retrying HTTP requests under certain failure conditions.                                                                                                               |

### Response

**Promise\<[components.ObjQueryRes](../../models/components/objqueryres.md)\>**

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