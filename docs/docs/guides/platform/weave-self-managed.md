# W&B Weave Self-Managed

:::important
Weave on self-managed infrastructure is currently in Private Preview.  

For production environments, W&B strongly recommends using [W&B Dedicated Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/dedicated_cloud), where Weave is Generally Available.  

To deploy a production-grade, self-managed instance, contact `support@wandb.com`.  
:::

This guide explains how to deploy all the components required to run W&B Weave in a self-managed environment.

A key component of a self-managed Weave deployment is [ClickHouseDB](https://clickhouse.com/), which the Weave application backend relies on.

Although the deployment process sets up a fully functional ClickHouseDB instance, you may need to take additional steps to ensure reliability and high availability for a production-ready environment.

## Requirements

- W&B Platform installed. For more information, see the [Self-Managed Deployment Guide](https://docs.wandb.ai/guides/hosting/hosting-options/self-managed/).
- [Altinity Kubernetes Operator for ClickHouse](https://docs.altinity.com/altinitykubernetesoperator).
- An S3 bucket pre-configured for ClickHouse storage. For configuration details, see [Provide S3 Credentials](#provide-s3-credentials).
- Kubernetes Cluster Nodes with the following specifications:
  - CPU: 8 cores  
  - RAM: 64 GB  
  - Disk: 200GB+
- A Weave-enabled license from W&B. To request a license, please contact `support@wandb.com`.

:::tip  
For a detailed reference architecture, see [https://docs.wandb.ai/guides/hosting/self-managed/ref-arch/](https://docs.wandb.ai/guides/hosting/self-managed/ref-arch/#models-and-weave).
:::

## 1. Deploy ClickHouse

The ClickHouse deployment in this document uses the [Altinity Kubernetes Operator for ClickHouse](https://docs.altinity.com/altinitykubernetesoperator).

Altinity uses operator to install, configure, and run a ClickHouse cluster in a Kubernetes cluster, including how to set up persistent storage and replication. Be aware that the GitHub repo for the project (https://github.com/Altinity/clickhouse-operator) has in-depth technical details (https://github.com/Altinity/clickhouse-operator/tree/master/docs#table-of-contents) for a number of advanced configuration.

To Install Altinity Operator for clickhouse follow the below steps:

1. [Configure the Helm repository](#configure-helm-repository)
2. [Create Helm Configuration](#create-helm-configuration)
3. [Provide S3 credentials](#provide-s3-credentials)

### Configure Helm repository

1. Add the Altinity Helm repository:

   `helm repo add altinity https://helm.altinity.com`

2. Update the helm repository:

   `helm repo update`
### Install Altinity Operator:
   
   `helm install ch-operator altinity/clickhouse --namespace clickhouse --create-namespace --version 0.2.6`

### Configure bucket access/secret credentials:
  ```
  # Create secret in clickhouse namespace with bucket secret
   SECRET_NAME="ch-bucket-cred"
   NAMESPACE="clickhouse"
   ACCESS_ID=# Get ACCESS_ID and SECRET from bucket
   kubectl -n "$NAMESPACE" create secret generic "$SECRET_NAME" \
   --from-literal=access_key="$ACCESS_ID" \
   --from-literal=secret_key="$SECRET" \
   --dry-run=client -o yaml | kubectl apply -f -
  ```
### Deploy keeper into Kubernetes cluster:

 `kubectl apply -f ch-keeper.yaml -n clickhouse`

 ```
apiVersion: "clickhouse-keeper.altinity.com/v1"
kind: "ClickHouseKeeperInstallation"
metadata:
  name: wandb
  annotations: {}
spec:
  # Default templates for all clusters
  # I'm using specific templates, but we can move all configuration
  # to default templates and suppress the templates section in the cluster configuration
  defaults:
    templates:
      podTemplate: default
      dataVolumeClaimTemplate: default

  # Clickhouse Keeper cluster templates
  templates:
    podTemplates:
      - name: keeper
        metadata:
          annotations: {}
          labels:
            app: clickhouse-keeper
        spec:
          # Pod security context: Need to set for OpenShift
          # securityContext:
          #   runAsNonRoot: true
          #   runAsUser: 101 # Your OpenShift user ID
          #   runAsGroup: 0
          #   fsGroup: 101 # Your OpenShift user ID
          #   fsGroupChangePolicy: "Always"
          #   seccompProfile:
          #     type: "RuntimeDefault"

          # Recommended for multiple nodes
          # affinity:
          #   podAntiAffinity:
          #     requiredDuringSchedulingIgnoredDuringExecution:
          #       - labelSelector:
          #           matchExpressions:
          #             - key: "app"
          #               operator: In
          #               values:
          #                 - clickhouse-keeper
          #         topologyKey: "kubernetes.io/hostname"

          # Container configuration
          containers:
            - name: clickhouse-keeper
              imagePullPolicy: IfNotPresent
              image: "clickhouse/clickhouse-keeper:25.3.5.42"
              resources:
                requests:
                  memory: "256M"
                  cpu: "1"
                limits:
                  memory: "4Gi"
                  cpu: "2"

              # Container security context: Need to set for OpenShift
              # securityContext:
              #   allowPrivilegeEscalation: false
              #   capabilities:
              #     drop:
              #       - ALL
              #     add:
              #       - NET_ADMIN
              #   privileged: false
              #   readOnlyRootFilesystem: false

    # Data volume claim template
    volumeClaimTemplates:
      - name: data
        metadata:
          labels:
            app: clickhouse-keeper
        spec:
          storageClassName: standard-rwo # Replace with your storage class
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 10Gi

  # CliCkhouse Keeper cluster configuration
  configuration:
    clusters:
      - name: keeper
        layout:
          replicasCount: 3
        # Templates for the cluster (not the default templates)
        templates:
          podTemplate: keeper
          dataVolumeClaimTemplate: data

    # For details, see:
    # https://clickhouse.com/docs/guides/sre/keeper/clickhouse-keeper#configuration
    settings:
      logger/level: "information"
      logger/console: "true"
      listen_host: "0.0.0.0"
      keeper_server/four_letter_word_white_list: "*"
      keeper_server/coordination_settings/raft_logs_level: "information"
 ```

### Deploy ch-server into Kubernetes cluster:

    Modify any parts related
    1. PVC `storageClassName`
    2. Bucket configuration
    3. Sizes of cache and other filesystems
    4. Password for `weave` user

`kubectl apply -f ch-server.yaml -n clickhouse`

```
apiVersion: "clickhouse.altinity.com/v1"
kind: "ClickHouseInstallation"
metadata:
  name: wandb
  annotations: {}
spec:
  # Default templates for all clusters
  # I'm using specific templates, but we can move all configuration
  # to default templates and suppress the templates section in the cluster configuration
  defaults:
    templates:
      podTemplate: default
      dataVolumeClaimTemplate: default

  templates:
    podTemplates:
      - name: clickhouse
        metadata:
          annotations: {}
          labels:
            app: clickhouse-server
        spec:
          # Pod security context: Need to set for OpenShift
          # securityContext:
          #   runAsNonRoot: true
          #   runAsUser: 101 # Your OpenShift user ID
          #   runAsGroup: 0
          #   fsGroup: 101 # Your OpenShift user ID
          #   fsGroupChangePolicy: "Always"
          #   seccompProfile:
          #     type: "RuntimeDefault"

          # Recommended for multiple nodes
          # affinity:
          #   podAntiAffinity:
          #     requiredDuringSchedulingIgnoredDuringExecution:
          #       - labelSelector:
          #           matchExpressions:
          #             - key: "app"
          #               operator: In
          #               values:
          #                 - clickhouse-server
          #         topologyKey: "kubernetes.io/hostname"

          containers:
            - name: clickhouse
              image: clickhouse/clickhouse-server:25.3.5.42
              resources:
                requests:
                  memory: 2Gi
                  cpu: 1
                limits:
                  memory: 16Gi
                  cpu: 2
              # If you want to use AWS credentials, you can use the following:
              #env:
              #  - name: AWS_ACCESS_KEY_ID
              #    valueFrom:
              #      secretKeyRef:
              #        name: ch-bucket-cred
              #        key: access_key
              #  - name: AWS_SECRET_ACCESS_KEY
              #    valueFrom:
              #      secretKeyRef:
              #        name: ch-bucket-cred
              #        key: secret_key

              # Container security context: Need to set for OpenShift
              # securityContext:
              #   allowPrivilegeEscalation: false
              #   capabilities:
              #     drop:
              #       - ALL
              #     add:
              #       - NET_ADMIN
              #   privileged: false
              #   readOnlyRootFilesystem: false

    volumeClaimTemplates:
      - name: data
        metadata:
          labels:
            app: clickhouse-server
        spec:
          accessModes:
            - ReadWriteOnce
          resources:
            requests:
              storage: 50Gi
          storageClassName: standard-rwo

  configuration:
    # Refer to: https://clickhouse.com/docs/operations/server-configuration-parameters/settings#zookeeper
    zookeeper:
      nodes:
        - host: chk-wandb-keeper-0-0.clickhouse.svc.cluster.local
          port: 2181
        - host: chk-wandb-keeper-0-1.clickhouse.svc.cluster.local
          port: 2181
        - host: chk-wandb-keeper-0-2.clickhouse.svc.cluster.local
          port: 2181
      # Other configurations
      # session_timeout_ms: 30000
      # operation_timeout_ms: 10000

    # Users configuration: https://clickhouse.com/docs/operations/configuration-files#user-settings
    # Tip for password :
    # sha256sum <<< weave123 OR echo -n weave123 | sha256sum OR printf "weave123" | sha256sum
    # It wil turn into <password_sha256_hex>...</password_sha256_hex> in user config
    users:
      weave/password_sha256_hex: e419535466c5c9c280a157975503187bf27f94093a35a9847ed5249d3df54b4b
      #weave/password: <PASSWORD> #for cleartext password
      weave/password:   # to use k8s secrets for "weave" user password
        valueFrom:
          secretKeyRef:
            name: <db-password>
            key: <password>
      weave/access_management: 1
      weave/profile: default
      weave/networks/ip:
        - 0.0.0.0/0

    # Settings configuration: https://clickhouse.com/docs/operations/server-configuration-parameters/settings
    # This can be here or in a config file
    settings:
      {}
      # prometheus/metrics: 1
      # prometheus/endpoint: /metrics
      # prometheus/port: 9191
      # prometheus/events: 1
      # prometheus/asynchronous_metrics: 1

    clusters:
      - name: clickhouse
        layout:
          shardsCount: 1
          replicasCount: 3
        templates:
          podTemplate: clickhouse
          dataVolumeClaimTemplate: data

    files:
      config.d/network_configuration.xml: |
        <clickhouse>
            <network_configuration>
                <listen_host>0.0.0.0</listen_host>
                <listen_host>::</listen_host>
            </network_configuration>
        </clickhouse>
      config.d/logger.xml: |
        <clickhouse>
            <logger>
                <level>information</level>
            </logger>
        </clickhouse>
      config.d/remote_servers.xml: |
        <clickhouse>
          <remote_servers>
            <weave_cluster>
              <shard>
                <replica>
                  <host>chi-wandb-clickhouse-0-0.clickhouse.svc.cluster.local</host>
                  <port>9000</port>
                </replica>
                <replica>
                  <host>chi-wandb-clickhouse-0-1.clickhouse.svc.cluster.local</host>
                  <port>9000</port>
                </replica>
                <replica>
                  <host>chi-wandb-clickhouse-0-2.clickhouse.svc.cluster.local</host>
                  <port>9000</port>
                </replica>
              </shard>
            </weave_cluster>
          </remote_servers>
        </clickhouse>
      config.d/storage_configuration.xml: |
        <clickhouse>
            <storage_configuration>
                <disks>
                    <s3_disk>
                        <type>s3</type>
                        <endpoint>https://storage.googleapis.com/wandbench-ch-1/s3_disk/{replica}</endpoint>
                        <metadata_path>/var/lib/clickhouse/disks/s3_disk/</metadata_path>
                        <use_environment_credentials>true</use_environment_credentials>
                        <s3_use_virtual_hosted_style>false</s3_use_virtual_hosted_style>
                    </s3_disk>
                    <s3_disk_cache>
                        <type>cache</type>
                        <disk>s3_disk</disk>
                        <path>/var/lib/clickhouse/s3_disk_cache/cache/</path>
                        <!-- THE CACHE SIZE MUST BE LOWER THAN PERSISTENT VOLUME -->
                        <max_size>40Gi</max_size>
                        <cache_on_write_operations>true</cache_on_write_operations>
                    </s3_disk_cache>
                </disks>
                <policies>
                    <s3_main>
                        <volumes>
                            <main>
                                <disk>s3_disk_cache</disk>
                            </main>
                        </volumes>
                    </s3_main>
                </policies>
            </storage_configuration>
            <merge_tree>
                <storage_policy>s3_main</storage_policy>
            </merge_tree>
        </clickhouse>
```
 



### Confirm ClickHouse deployment

Confirm that ClickHouse is deployed using the following command:

```bash
kubectl get pods -n clickhouse
```

You should see the following pods:

```bash
NAME                                 READY   STATUS    RESTARTS   AGE
clickhouse-shard0-0                  1/1     Running   0          9m59s
clickhouse-shard0-1                  1/1     Running   0          10m
clickhouse-shard0-2                  1/1     Running   0          10m
```
## 2. Add ClickHouse Configuration in W&B Platform CR

 
Edit the [CR instance](https://docs.wandb.ai/guides/hosting/operator/#complete-example) used to deploy the platform.

1. Use Kubernetes service details to configure Weave tracing:

  - **Endpoint**: `<release-name>-headless.<namespace>.svc.cluster.local`
    - Replace `<release-name>` with your Helm release name
    - Replace `<namespace>` with your `NAMESPACE`
    - Get the service details: `kubectl get svc -n <namespace>`
  - **Username**: Set in the `values.yaml`
  - **Password**: Set in the `values.yaml`

2. With this information, update the W&B Platform Custom Resource(CR) by adding the following configuration:

    ```yaml
    apiVersion: apps.wandb.com/v1
    kind: WeightsAndBiases
    metadata:
      labels:
        app.kubernetes.io/name: weightsandbiases
        app.kubernetes.io/instance: wandb
      name: wandb
      namespace: default
    spec:
      values:
        global:
        [...]
          clickhouse:
            host: <release-name>-headless.<namespace>.svc.cluster.local
            port: 8123
            password: <password>
            user: <username>
            database: wandb_weave
            # `replicated` must be set to `true` if replicating data across multiple nodes
            # This is in preview, use the env var `WF_CLICKHOUSE_REPLICATED`
            replicated: true

          weave-trace:
            enabled: true
        [...]
        weave-trace:
          install: true
          extraEnv:
            WF_CLICKHOUSE_REPLICATED: "true"
        [...]
    ```

:::important
When using more than one replica (W&B recommend a least 3 replicas), ensure to have the following environment variable set for Weave Traces.
```
extraEnv:
  WF_CLICKHOUSE_REPLICATED: "true"
```
This has the same effect of `replicated: true` which in preview.
:::


3. Set the `clusterName` in `values.yaml` to `weave_cluster`. If it is not, the database migration will fail.  

    Alternatively, ff you use a different cluster name, set the `WF_CLICKHOUSE_REPLICATED_CLUSTER` environment variable in `weave-trace.extraEnv` to match the chosen name, as shown in the example below.

    ```yaml
    [...]
      clickhouse:
        host: <release-name>-headless.<namespace>.svc.cluster.local
        port: 8123
        password: <password>
        user: <username>
        database: wandb_weave
        # `replicated` must be set to `true` if replicating data across multiple nodes
        # This is in preview, use the env var `WF_CLICKHOUSE_REPLICATED`
        replicated: true

      weave-trace:
        enabled: true
    [...]
    weave-trace:
      install: true
      extraEnv:
        WF_CLICKHOUSE_REPLICATED: "true"
        WF_CLICKHOUSE_REPLICATED_CLUSTER: "different_cluster_name"
    [...]
    ```

    The final configuration will look like the following example:

    ```yaml
    apiVersion: apps.wandb.com/v1
    kind: WeightsAndBiases
    metadata:
      labels:
        app.kubernetes.io/name: weightsandbiases
        app.kubernetes.io/instance: wandb
      name: wandb
      namespace: default
    spec:
      values:
        global:
          license: eyJhbGnUzaHgyQjQyQWhEU3...ZieKQ2x5GGfw
          host: https://wandb.example.com

          bucket:
            name: abc-wandb-moving-pipefish
            provider: gcs

          mysql:
            database: wandb_local
            host: 10.218.0.2
            name: wandb_local
            password: 8wtX6cJHizAZvYScjDzZcUarK4zZGjpV
            port: 3306
            user: wandb

          clickhouse:
            host: <release-name>-headless.<namespace>.svc.cluster.local
            port: 8123
            password: <password>
            user: <username>
            database: wandb_weave
            # This option must be true if replicating data across multiple nodes
            replicated: true

          weave-trace:
            enabled: true
    
        ingress:
          annotations:
            ingress.gcp.kubernetes.io/pre-shared-cert: abc-wandb-cert-creative-puma
            kubernetes.io/ingress.class: gce
            kubernetes.io/ingress.global-static-ip-name: abc-wandb-operator-address

        weave-trace:
          install: true
          extraEnv:
            WF_CLICKHOUSE_REPLICATED: "true"
    ```

4. With the Custom Resource (CR) prepared, apply the new configuration:

    ```bash
    kubectl apply -f wandb.yaml
    ```

## 3. Access Weave

Once the deployment is running, accessing the W&B endpoint configured in the `host` option should display the Weave licensing status as enabled.

![Weave](../../media/weave-self-managed/weave-org-dashboard.png)
