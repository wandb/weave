# Platform & Security

Weave is available on the following deployment options:

- **[W&B SaaS Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/saas_cloud):** A multi-tenant, fully-managed platform deployed in W&B's Google Cloud Platform (GCP) account in a North America region.
- **[W&B Dedicated Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/dedicated_cloud):** Generally available on AWS and in preview on GCP and Azure. 
- **Self-managed instances:** For teams that prefer to host Weave independently, guidance is available from your W&B team to evaluate deployment options.

## Identity and Access Management

Use the identity and access management capabilities for secure authentication and effective authorization in your [W&B Organization](https://docs.wandb.ai/guides/hosting/iam/org_team_struct#organization). The following capabilities are available for Weave users depending on your deployment option and [pricing plan](https://wandb.ai/site/pricing/):

- **Authenticate using Single-Sign On (SSO):** Options include public identity providers like Google and Github, as well as enterprise providers such as Okta, Azure Active Directory, and other [OIDC providers](https://docs.wandb.ai/guides/technical-faq/general#does-wb-support-sso-for-saas).
- **[Team-based logical separation](https://docs.wandb.ai/guides/hosting/iam/manage-organization/#add-and-manage-teams):** Each team may correspond to a business unit, department, or project team within your organization.
- **Use W&B projects to organize initiatives:** Organize initiatives within teams and configure the required [visibility scope](https://docs.wandb.ai/guides/hosting/restricted-projects), including the `restricted` scope for sensitive collaborations.
- **Role-based access control:** Configure access at the [team](https://docs.wandb.ai/guides/hosting/iam/manage-organization#assign-or-update-a-team-members-role) or [project](https://docs.wandb.ai/guides/hosting/iam/restricted-projects#project-level-roles) level to ensure users access data on a need-to-know basis.
- **Scoped service accounts:** Automate Gen AI workflows using service accounts scoped to your organization or team.
- **[SCIM API and Python SDK](https://docs.wandb.ai/guides/hosting/iam/automate_iam):** Manage users and teams efficiently with SCIM API and Python SDK.

## Data Security

- **SaaS Cloud:** Data for all Weave users is stored in a shared Clickhouse Cloud cluster, encrypted using cloud-native encryption. Shared compute services process the data, ensuring isolation through a security context comprising your W&B organization, team, and project.

- **Dedicated Cloud:** Data is stored in a unique Clickhouse Cloud cluster in the cloud and region of your choice. A unique compute environment processes the data, with the following additional protections:
  - **IP allowlisting:** Authorize access to your instance from specific IP addresses.
  - **Private connectivity:** Route data securely through the cloud provider's private network.
  - **Data encryption:** Encrypt data at rest using a unique W&B-managed encryption key.
  - **Strong encryption mechanisms:** File-based encryption using Clickhouse Cloud's capabilities.

:::important
[The W&B Platform secure storage connector](https://docs.wandb.ai/guides/hosting/data-security/secure-storage-connector/?_gl=1*jzcfye*_gcl_au*OTI3ODM1OTcyLjE3MzE0MzU1NjUuMTYxOTQ4Mzk1LjE3MzMyNTYwMTYuMTczMzI1NjAxNQ..*_ga*ODEyMjQ4MjkyLjE3MzE0MzU1NjU.*_ga_JH1SJHJQXJ*MTczNDEyNjAxNy45Ny4xLjE3MzQxMjg5NDEuNjAuMC4w*_ga_GMYDGNGKDT*MTczNDEyNzgzMy44MS4xLjE3MzQxMjg1MTAuMC4wLjA.) is not available in Weave.
:::

## Maintenance 

If you're using Weave on SaaS Cloud or Dedicated Cloud, you avoid the overhead and costs of provisioning, operating, and maintaining the W&B platform, as it is fully managed for you.

## Compliance

:::tip
To request SOC 2 reports and other security and compliance documents, refer to the [W&B Security Portal](https://security.wandb.ai/) or contact your W&B team for more information.
:::

Security controls for both SaaS Cloud and Dedicated Cloud are periodically audited internally and externally. Both platforms are SOC 2 Type II compliant. Additionally, Dedicated Cloud is HIPAA-compliant for organizations managing PHI data while building Generative AI applications.
