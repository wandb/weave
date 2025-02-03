# Deploy

## Deploy to GCP

:::note
`weave deploy` requires your machine to have `gcloud` installed and configured. `weave deploy gcp` will use pre-configured configuration when not directly specified by command line arguments.
:::

Given a Weave ref to any Weave Model you can run:

```
weave deploy gcp <ref>
```

to deploy a gcp cloud function that serves your model. The last line of the deployment will look like `Service URL: <PATH_TO_MODEL>`. Visit `<PATH_TO_MODEL>/docs` to interact with your model!

Run

```
weave deploy gcp --help
```

to see all command line options.
