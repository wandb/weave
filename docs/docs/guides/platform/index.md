# Platform & Security

Weave is available on [W&B SaaS Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/saas_cloud) which is a multi-tenant, fully-managed platform deployed in W&B's Google Cloud Platform (GCP) account in a North America region.

:::info
It's coming soon on [W&B Dedicated Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/dedicated_cloud). Reach out to your W&B team if that would be of interest in your organization.
:::

## Identity & Access Management

Use the identity and access management capabilities for secure authentication and effective authorization in your [W&B Organization](https://docs.wandb.ai/guides/hosting/iam/org_team_struct#organization). The following capabilities are available for Weave users in W&B SaaS Cloud:

* Authenticate using Single-Sign On (SSO), with available options being Google, Github, Microsoft, and [OIDC providers](https://docs.wandb.ai/guides/technical-faq/general#does-wb-support-sso-for-saas)
* [Team-based access control](https://docs.wandb.ai/guides/hosting/iam/manage-users#manage-a-team), where each team may correspond to a business unit / function, department, or a project team in your company
* Use W&B projects to organize different initiatives within a team, and configure the required [visibility scope](https://docs.wandb.ai/guides/hosting/restricted-projects) for each project

## Data Security

In the W&B SaaS Cloud, data of all Weave users is stored in a shared cloud storage and is processed using shared compute services. The shared cloud storage is encrypted using the cloud-native encryption mechanism. When reading or writing data on behalf of a user, a security context comprising of the user's W&B organization, team and project is utilized to ensure data path isolation.

:::note
[Secure storage connector](https://docs.wandb.ai/guides/hosting/secure-storage-connector) is not applicable to Weave.
:::

## Maintenance

If you're using Weave on W&B SaaS Cloud, you do not incur the overhead and costs of provisioning and maintaining the W&B platform. It's all fully managed for you.

## Compliance

Security controls for W&B SaaS Cloud are periodically audited internally and externally. Refer to the [W&B Security Portal](https://security.wandb.ai/) to request the SOC2 report and other security and compliance documents.