<div align="center">
    <img width="300px" src="https://avatars.githubusercontent.com/u/26401354?s=200&v=4">
    <h1>Weights and Biases Typescript SDK</h1>
    <p><strong>Building the best tools for ML practitioners</strong></p>
    <p>Developer-friendly & type-safe Typescript SDK specifically catered to leverage the <strong>Weights and Biases</strong> API.</p>
    <a href="https://developers.docusign.com/docs/"><img src="https://img.shields.io/static/v1?label=Docs&message=API Ref&color=4c2cec&style=for-the-badge" /></a>
    <a href="https://opensource.org/licenses/MIT"><img src="https://img.shields.io/badge/License-MIT-blue.svg?style=for-the-badge" /></a>
</div>


<br /><br />
> [!IMPORTANT]
> This SDK is not yet ready for production use. To complete setup please follow the steps outlined in your [workspace](https://app.speakeasy.com/org/wandb-xdq/wandb). Delete this section before > publishing to a package manager.

<!-- Start Summary [summary] -->
## Summary

Weave Trace Server: Weave trace server summary

Weave trace server description
<!-- End Summary [summary] -->

<!-- Start Table of Contents [toc] -->
## Table of Contents
<!-- $toc-max-depth=2 -->
  * [SDK Installation](#sdk-installation)
  * [Requirements](#requirements)
  * [SDK Example Usage](#sdk-example-usage)
  * [Authentication](#authentication)
  * [Available Resources and Operations](#available-resources-and-operations)
  * [Standalone functions](#standalone-functions)
  * [React hooks with TanStack Query](#react-hooks-with-tanstack-query)
  * [File uploads](#file-uploads)
  * [Retries](#retries)
  * [Error Handling](#error-handling)
  * [Server Selection](#server-selection)
  * [Custom HTTP Client](#custom-http-client)
  * [Debugging](#debugging)
* [Development](#development)
  * [Maturity](#maturity)
  * [Contributions](#contributions)

<!-- End Table of Contents [toc] -->

<!-- Start SDK Installation [installation] -->
## SDK Installation

> [!TIP]
> To finish publishing your SDK to npm and others you must [run your first generation action](https://www.speakeasy.com/docs/github-setup#step-by-step-guide).


The SDK can be installed with either [npm](https://www.npmjs.com/), [pnpm](https://pnpm.io/), [bun](https://bun.sh/) or [yarn](https://classic.yarnpkg.com/en/) package managers.

### NPM

```bash
npm add https://github.com/speakeasy-sdks/wandb-typescript-sdk
# Install optional peer dependencies if you plan to use React hooks
npm add @tanstack/react-query react react-dom
```

### PNPM

```bash
pnpm add https://github.com/speakeasy-sdks/wandb-typescript-sdk
# Install optional peer dependencies if you plan to use React hooks
pnpm add @tanstack/react-query react react-dom
```

### Bun

```bash
bun add https://github.com/speakeasy-sdks/wandb-typescript-sdk
# Install optional peer dependencies if you plan to use React hooks
bun add @tanstack/react-query react react-dom
```

### Yarn

```bash
yarn add https://github.com/speakeasy-sdks/wandb-typescript-sdk zod
# Install optional peer dependencies if you plan to use React hooks
yarn add @tanstack/react-query react react-dom

# Note that Yarn does not install peer dependencies automatically. You will need
# to install zod as shown above.
```
<!-- End SDK Installation [installation] -->

<!-- Start Requirements [requirements] -->
## Requirements

For supported JavaScript runtimes, please consult [RUNTIMES.md](RUNTIMES.md).
<!-- End Requirements [requirements] -->

<!-- Start SDK Example Usage [usage] -->
## SDK Example Usage

### Example

```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth();

  // Handle the result
  console.log(result);
}

run();

```
<!-- End SDK Example Usage [usage] -->

<!-- Start Authentication [security] -->
## Authentication

### Per-Client Security Schemes

This SDK supports the following security scheme globally:

| Name                      | Type | Scheme     | Environment Variable                  |
| ------------------------- | ---- | ---------- | ------------------------------------- |
| `username`<br/>`password` | http | HTTP Basic | `WANDB_USERNAME`<br/>`WANDB_PASSWORD` |

You can set the security parameters through the `security` optional parameter when initializing the SDK client instance. For example:
```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth();

  // Handle the result
  console.log(result);
}

run();

```
<!-- End Authentication [security] -->

<!-- Start Available Resources and Operations [operations] -->
## Available Resources and Operations

<details open>
<summary>Available methods</summary>

### [calls](docs/sdks/calls/README.md)

* [start](docs/sdks/calls/README.md#start) - Call Start
* [end](docs/sdks/calls/README.md#end) - Call End
* [upsertBatch](docs/sdks/calls/README.md#upsertbatch) - Call Start Batch
* [delete](docs/sdks/calls/README.md#delete) - Calls Delete
* [update](docs/sdks/calls/README.md#update) - Call Update
* [read](docs/sdks/calls/README.md#read) - Call Read
* [queryStats](docs/sdks/calls/README.md#querystats) - Calls Query Stats
* [streamQuery](docs/sdks/calls/README.md#streamquery) - Calls Query Stream

### [costs](docs/sdks/costs/README.md)

* [create](docs/sdks/costs/README.md#create) - Cost Create
* [query](docs/sdks/costs/README.md#query) - Cost Query
* [purge](docs/sdks/costs/README.md#purge) - Cost Purge

### [feedback](docs/sdks/feedback/README.md)

* [create](docs/sdks/feedback/README.md#create) - Feedback Create
* [query](docs/sdks/feedback/README.md#query) - Feedback Query
* [purge](docs/sdks/feedback/README.md#purge) - Feedback Purge

### [files](docs/sdks/files/README.md)

* [create](docs/sdks/files/README.md#create) - File Create
* [content](docs/sdks/files/README.md#content) - File Content

### [objects](docs/sdks/objects/README.md)

* [create](docs/sdks/objects/README.md#create) - Obj Create
* [read](docs/sdks/objects/README.md#read) - Obj Read
* [query](docs/sdks/objects/README.md#query) - Objs Query

### [refs](docs/sdks/refs/README.md)

* [readBatch](docs/sdks/refs/README.md#readbatch) - Refs Read Batch

### [service](docs/sdks/service/README.md)

* [getHealth](docs/sdks/service/README.md#gethealth) - Read Root
* [getServerInfo](docs/sdks/service/README.md#getserverinfo) - Server Info

### [tables](docs/sdks/tables/README.md)

* [create](docs/sdks/tables/README.md#create) - Table Create
* [update](docs/sdks/tables/README.md#update) - Table Update
* [query](docs/sdks/tables/README.md#query) - Table Query
* [queryStats](docs/sdks/tables/README.md#querystats) - Table Query Stats


</details>
<!-- End Available Resources and Operations [operations] -->

<!-- Start Standalone functions [standalone-funcs] -->
## Standalone functions

All the methods listed above are available as standalone functions. These
functions are ideal for use in applications running in the browser, serverless
runtimes or other environments where application bundle size is a primary
concern. When using a bundler to build your application, all unused
functionality will be either excluded from the final bundle or tree-shaken away.

To read more about standalone functions, check [FUNCTIONS.md](./FUNCTIONS.md).

<details>

<summary>Available standalone functions</summary>

- [`callsDelete`](docs/sdks/calls/README.md#delete) - Calls Delete
- [`callsEnd`](docs/sdks/calls/README.md#end) - Call End
- [`callsQueryStats`](docs/sdks/calls/README.md#querystats) - Calls Query Stats
- [`callsRead`](docs/sdks/calls/README.md#read) - Call Read
- [`callsStart`](docs/sdks/calls/README.md#start) - Call Start
- [`callsStreamQuery`](docs/sdks/calls/README.md#streamquery) - Calls Query Stream
- [`callsUpdate`](docs/sdks/calls/README.md#update) - Call Update
- [`callsUpsertBatch`](docs/sdks/calls/README.md#upsertbatch) - Call Start Batch
- [`costsCreate`](docs/sdks/costs/README.md#create) - Cost Create
- [`costsPurge`](docs/sdks/costs/README.md#purge) - Cost Purge
- [`costsQuery`](docs/sdks/costs/README.md#query) - Cost Query
- [`feedbackCreate`](docs/sdks/feedback/README.md#create) - Feedback Create
- [`feedbackPurge`](docs/sdks/feedback/README.md#purge) - Feedback Purge
- [`feedbackQuery`](docs/sdks/feedback/README.md#query) - Feedback Query
- [`filesContent`](docs/sdks/files/README.md#content) - File Content
- [`filesCreate`](docs/sdks/files/README.md#create) - File Create
- [`objectsCreate`](docs/sdks/objects/README.md#create) - Obj Create
- [`objectsQuery`](docs/sdks/objects/README.md#query) - Objs Query
- [`objectsRead`](docs/sdks/objects/README.md#read) - Obj Read
- [`refsReadBatch`](docs/sdks/refs/README.md#readbatch) - Refs Read Batch
- [`serviceGetHealth`](docs/sdks/service/README.md#gethealth) - Read Root
- [`serviceGetServerInfo`](docs/sdks/service/README.md#getserverinfo) - Server Info
- [`tablesCreate`](docs/sdks/tables/README.md#create) - Table Create
- [`tablesQuery`](docs/sdks/tables/README.md#query) - Table Query
- [`tablesQueryStats`](docs/sdks/tables/README.md#querystats) - Table Query Stats
- [`tablesUpdate`](docs/sdks/tables/README.md#update) - Table Update

</details>
<!-- End Standalone functions [standalone-funcs] -->

<!-- Start React hooks with TanStack Query [react-query] -->
## React hooks with TanStack Query

React hooks built on [TanStack Query][tanstack-query] are included in this SDK.
These hooks and the utility functions provided alongside them can be used to
build rich applications that pull data from the API using one of the most
popular asynchronous state management library.

[tanstack-query]: https://tanstack.com/query/v5/docs/framework/react/overview

To learn about this feature and how to get started, check
[REACT_QUERY.md](./REACT_QUERY.md).

> [!WARNING]
>
> This feature is currently in **preview** and is subject to breaking changes
> within the current major version of the SDK as we gather user feedback on it.

<details>

<summary>Available React hooks</summary>

- [`useCallsDeleteMutation`](docs/sdks/calls/README.md#delete) - Calls Delete
- [`useCallsEndMutation`](docs/sdks/calls/README.md#end) - Call End
- [`useCallsQueryStatsMutation`](docs/sdks/calls/README.md#querystats) - Calls Query Stats
- [`useCallsReadMutation`](docs/sdks/calls/README.md#read) - Call Read
- [`useCallsStartMutation`](docs/sdks/calls/README.md#start) - Call Start
- [`useCallsStreamQueryMutation`](docs/sdks/calls/README.md#streamquery) - Calls Query Stream
- [`useCallsUpdateMutation`](docs/sdks/calls/README.md#update) - Call Update
- [`useCallsUpsertBatchMutation`](docs/sdks/calls/README.md#upsertbatch) - Call Start Batch
- [`useCostsCreateMutation`](docs/sdks/costs/README.md#create) - Cost Create
- [`useCostsPurgeMutation`](docs/sdks/costs/README.md#purge) - Cost Purge
- [`useCostsQueryMutation`](docs/sdks/costs/README.md#query) - Cost Query
- [`useFeedbackCreateMutation`](docs/sdks/feedback/README.md#create) - Feedback Create
- [`useFeedbackPurgeMutation`](docs/sdks/feedback/README.md#purge) - Feedback Purge
- [`useFeedbackQuery`](docs/sdks/feedback/README.md#query) - Feedback Query
- [`useFilesContentMutation`](docs/sdks/files/README.md#content) - File Content
- [`useFilesCreateMutation`](docs/sdks/files/README.md#create) - File Create
- [`useObjectsCreateMutation`](docs/sdks/objects/README.md#create) - Obj Create
- [`useObjectsQueryMutation`](docs/sdks/objects/README.md#query) - Objs Query
- [`useObjectsReadMutation`](docs/sdks/objects/README.md#read) - Obj Read
- [`useRefsReadBatchMutation`](docs/sdks/refs/README.md#readbatch) - Refs Read Batch
- [`useServiceGetHealth`](docs/sdks/service/README.md#gethealth) - Read Root
- [`useServiceGetServerInfo`](docs/sdks/service/README.md#getserverinfo) - Server Info
- [`useTablesCreateMutation`](docs/sdks/tables/README.md#create) - Table Create
- [`useTablesQueryMutation`](docs/sdks/tables/README.md#query) - Table Query
- [`useTablesQueryStatsMutation`](docs/sdks/tables/README.md#querystats) - Table Query Stats
- [`useTablesUpdateMutation`](docs/sdks/tables/README.md#update) - Table Update

</details>
<!-- End React hooks with TanStack Query [react-query] -->

<!-- Start File uploads [file-upload] -->
## File uploads

Certain SDK methods accept files as part of a multi-part request. It is possible and typically recommended to upload files as a stream rather than reading the entire contents into memory. This avoids excessive memory consumption and potentially crashing with out-of-memory errors when working with very large files. The following example demonstrates how to attach a file stream to a request.

> [!TIP]
>
> Depending on your JavaScript runtime, there are convenient utilities that return a handle to a file without reading the entire contents into memory:
>
> - **Node.js v20+:** Since v20, Node.js comes with a native `openAsBlob` function in [`node:fs`](https://nodejs.org/docs/latest-v20.x/api/fs.html#fsopenasblobpath-options).
> - **Bun:** The native [`Bun.file`](https://bun.sh/docs/api/file-io#reading-files-bun-file) function produces a file handle that can be used for streaming file uploads.
> - **Browsers:** All supported browsers return an instance to a [`File`](https://developer.mozilla.org/en-US/docs/Web/API/File) when reading the value from an `<input type="file">` element.
> - **Node.js v18:** A file stream can be created using the `fileFrom` helper from [`fetch-blob/from.js`](https://www.npmjs.com/package/fetch-blob).

```typescript
import { openAsBlob } from "node:fs";
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.files.create({
    file: await openAsBlob("example.file"),
    projectId: "<id>",
  });

  // Handle the result
  console.log(result);
}

run();

```
<!-- End File uploads [file-upload] -->

<!-- Start Retries [retries] -->
## Retries

Some of the endpoints in this SDK support retries.  If you use the SDK without any configuration, it will fall back to the default retry strategy provided by the API.  However, the default retry strategy can be overridden on a per-operation basis, or across the entire SDK.

To change the default retry strategy for a single API call, simply provide a retryConfig object to the call:
```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth({
    retries: {
      strategy: "backoff",
      backoff: {
        initialInterval: 1,
        maxInterval: 50,
        exponent: 1.1,
        maxElapsedTime: 100,
      },
      retryConnectionErrors: false,
    },
  });

  // Handle the result
  console.log(result);
}

run();

```

If you'd like to override the default retry strategy for all operations that support retries, you can provide a retryConfig at SDK initialization:
```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  retryConfig: {
    strategy: "backoff",
    backoff: {
      initialInterval: 1,
      maxInterval: 50,
      exponent: 1.1,
      maxElapsedTime: 100,
    },
    retryConnectionErrors: false,
  },
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth();

  // Handle the result
  console.log(result);
}

run();

```
<!-- End Retries [retries] -->

<!-- Start Error Handling [errors] -->
## Error Handling

Some methods specify known errors which can be thrown. All the known errors are enumerated in the `models/errors/errors.ts` module. The known errors for a method are documented under the *Errors* tables in SDK docs. For example, the `getHealth` method may throw the following errors:

| Error Type                 | Status Code                  | Content Type     |
| -------------------------- | ---------------------------- | ---------------- |
| errors.BadRequest          | 400, 413, 414, 415, 422, 431 | application/json |
| errors.Unauthorized        | 401, 403, 407                | application/json |
| errors.NotFound            | 404                          | application/json |
| errors.Timeout             | 408                          | application/json |
| errors.RateLimited         | 429                          | application/json |
| errors.InternalServerError | 500, 502, 503, 506, 507, 508 | application/json |
| errors.NotFound            | 501, 505                     | application/json |
| errors.Timeout             | 504                          | application/json |
| errors.BadRequest          | 510                          | application/json |
| errors.Unauthorized        | 511                          | application/json |
| errors.APIError            | 4XX, 5XX                     | \*/\*            |

If the method throws an error and it is not captured by the known errors, it will default to throwing a `APIError`.

```typescript
import { Wandb } from "wandb";
import {
  BadRequest,
  InternalServerError,
  NotFound,
  RateLimited,
  SDKValidationError,
  Timeout,
  Unauthorized,
} from "wandb/models/errors";

const wandb = new Wandb({
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  let result;
  try {
    result = await wandb.service.getHealth();

    // Handle the result
    console.log(result);
  } catch (err) {
    switch (true) {
      // The server response does not match the expected SDK schema
      case (err instanceof SDKValidationError): {
        // Pretty-print will provide a human-readable multi-line error message
        console.error(err.pretty());
        // Raw value may also be inspected
        console.error(err.rawValue);
        return;
      }
      case (err instanceof BadRequest): {
        // Handle err.data$: BadRequestData
        console.error(err);
        return;
      }
      case (err instanceof Unauthorized): {
        // Handle err.data$: UnauthorizedData
        console.error(err);
        return;
      }
      case (err instanceof NotFound): {
        // Handle err.data$: NotFoundData
        console.error(err);
        return;
      }
      case (err instanceof Timeout): {
        // Handle err.data$: TimeoutData
        console.error(err);
        return;
      }
      case (err instanceof RateLimited): {
        // Handle err.data$: RateLimitedData
        console.error(err);
        return;
      }
      case (err instanceof InternalServerError): {
        // Handle err.data$: InternalServerErrorData
        console.error(err);
        return;
      }
      case (err instanceof NotFound): {
        // Handle err.data$: NotFoundData
        console.error(err);
        return;
      }
      case (err instanceof Timeout): {
        // Handle err.data$: TimeoutData
        console.error(err);
        return;
      }
      case (err instanceof BadRequest): {
        // Handle err.data$: BadRequestData
        console.error(err);
        return;
      }
      case (err instanceof Unauthorized): {
        // Handle err.data$: UnauthorizedData
        console.error(err);
        return;
      }
      default: {
        // Other errors such as network errors, see HTTPClientErrors for more details
        throw err;
      }
    }
  }
}

run();

```

Validation errors can also occur when either method arguments or data returned from the server do not match the expected format. The `SDKValidationError` that is thrown as a result will capture the raw value that failed validation in an attribute called `rawValue`. Additionally, a `pretty()` method is available on this error that can be used to log a nicely formatted multi-line string since validation errors can list many issues and the plain error string may be difficult read when debugging.

In some rare cases, the SDK can fail to get a response from the server or even make the request due to unexpected circumstances such as network conditions. These types of errors are captured in the `models/errors/httpclienterrors.ts` module:

| HTTP Client Error                                    | Description                                          |
| ---------------------------------------------------- | ---------------------------------------------------- |
| RequestAbortedError                                  | HTTP request was aborted by the client               |
| RequestTimeoutError                                  | HTTP request timed out due to an AbortSignal signal  |
| ConnectionError                                      | HTTP client was unable to make a request to a server |
| InvalidRequestError                                  | Any input used to create a request is invalid        |
| UnexpectedClientError                                | Unrecognised or unexpected error                     |
<!-- End Error Handling [errors] -->

<!-- Start Server Selection [server] -->
## Server Selection

### Override Server URL Per-Client

The default server can also be overridden globally by passing a URL to the `serverURL: string` optional parameter when initializing the SDK client instance. For example:
```typescript
import { Wandb } from "wandb";

const wandb = new Wandb({
  serverURL: "https://trace.wandb.ai",
  security: {
    username: "",
    password: "",
  },
});

async function run() {
  const result = await wandb.service.getHealth();

  // Handle the result
  console.log(result);
}

run();

```
<!-- End Server Selection [server] -->

<!-- Start Custom HTTP Client [http-client] -->
## Custom HTTP Client

The TypeScript SDK makes API calls using an `HTTPClient` that wraps the native
[Fetch API](https://developer.mozilla.org/en-US/docs/Web/API/Fetch_API). This
client is a thin wrapper around `fetch` and provides the ability to attach hooks
around the request lifecycle that can be used to modify the request or handle
errors and response.

The `HTTPClient` constructor takes an optional `fetcher` argument that can be
used to integrate a third-party HTTP client or when writing tests to mock out
the HTTP client and feed in fixtures.

The following example shows how to use the `"beforeRequest"` hook to to add a
custom header and a timeout to requests and how to use the `"requestError"` hook
to log errors:

```typescript
import { Wandb } from "wandb";
import { HTTPClient } from "wandb/lib/http";

const httpClient = new HTTPClient({
  // fetcher takes a function that has the same signature as native `fetch`.
  fetcher: (request) => {
    return fetch(request);
  }
});

httpClient.addHook("beforeRequest", (request) => {
  const nextRequest = new Request(request, {
    signal: request.signal || AbortSignal.timeout(5000)
  });

  nextRequest.headers.set("x-custom-header", "custom value");

  return nextRequest;
});

httpClient.addHook("requestError", (error, request) => {
  console.group("Request Error");
  console.log("Reason:", `${error}`);
  console.log("Endpoint:", `${request.method} ${request.url}`);
  console.groupEnd();
});

const sdk = new Wandb({ httpClient });
```
<!-- End Custom HTTP Client [http-client] -->

<!-- Start Debugging [debug] -->
## Debugging

You can setup your SDK to emit debug logs for SDK requests and responses.

You can pass a logger that matches `console`'s interface as an SDK option.

> [!WARNING]
> Beware that debug logging will reveal secrets, like API tokens in headers, in log messages printed to a console or files. It's recommended to use this feature only during local development and not in production.

```typescript
import { Wandb } from "wandb";

const sdk = new Wandb({ debugLogger: console });
```

You can also enable a default debug logger by setting an environment variable `WANDB_DEBUG` to true.
<!-- End Debugging [debug] -->

<!-- Placeholder for Future Speakeasy SDK Sections -->

# Development

## Maturity

This SDK is in beta, and there may be breaking changes between versions without a major version update. Therefore, we recommend pinning usage
to a specific package version. This way, you can install the same version each time without breaking changes unless you are intentionally
looking for the latest version.

## Contributions

While we value open-source contributions to this SDK, this library is generated programmatically. Any manual changes added to internal files will be overwritten on the next generation. 
We look forward to hearing your feedback. Feel free to open a PR or an issue with a proof of concept and we'll do our best to include it in a future release. 

### SDK Created by [Speakeasy](https://www.speakeasy.com/?utm_source=wandb&utm_campaign=typescript)
