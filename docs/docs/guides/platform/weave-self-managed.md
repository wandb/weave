# W&B Weave Self-managed

This document will guide you through deploying all components necessary to enable W&B Weave in a self-managed environment.

:::important
This is a tech-preview and not recommended to be in production.
The W&B team is working to deliver enterprise grade in the next weeks.
We recommend to use the [W&B Dedicated Cloud](https://docs.wandb.ai/guides/hosting/hosting-options/dedicated_cloud) deployment where the Weave is Generaly Available for production environments.
:::

One of the main componentes to deploy the W&B Weave is the database used by the application, in our case the ClickHouseDB.
Most of this document will describe how you can deploy the ClickHouseDB to support the W&B Weave.
Although a fully functional ClickHouseDB installation is deployed, many measures to ensure a more reliable and available installation are not fully covered, which will be part of the final documentation.

## Requirements

* **W&B Platform Installed(https://docs.wandb.ai/guides/hosting/hosting-options/self-managed/)**
* **Bitnami's ClickHouse Helm chart**
* **S3 Bucket:**
  * A pre-configured S3 bucket for ClickHouse storage (see the **Providing S3 Credentials** section for configuring credentials)  
* **Kubernetes Cluster Nodes with the following specs:** 
  * CPU: 8  
  * RAM: 64  
  * Disk: 200GB+

## Deploy ClickHouse

The ClickHouse deployment for this document will use the [Bitnami ClickHouse](https://bitnami.com/stack/clickhouse) package.
This Helm has a good support for the basic functionalities of ClickHouse, especially the usage of [ClickHouse Keeper](https://clickhouse.com/docs/en/guides/sre/keeper/clickhouse-keeper).

### Configure Helm repository

Add the Bitnami Helm repository:

`helm repo add bitnami https://charts.bitnami.com/bitnami` 

Udate the repository

`helm repo update`


### Create Helm Configuration

The following is an example `values.yaml` file with parameters that you can customize based on your needs.
The critical part in this document is the ClickHouse configuation in `XML` format. 
To facilitate the configuration we added comments in the relevante configuration parts in the following format `<!-- COMMENT -->`
For this configuration, we recommend you modify the `clusterName`, `auth.username`, `auth.password` and some configurations for the S3 bucket.

```yaml
# Stable version
image:
  registry: docker.io
  repository: bitnami/clickhouse
  tag: 24.8

## @param clusterName ClickHouse cluster name
clusterName: cluster_1S_3R

## @param shards Number of ClickHouse shards to deploy
shards: 1

## @param replicaCount Number of ClickHouse replicas per shard to deploy
## if keeper enable, same as keeper count, keeper cluster by shards.
replicaCount: 3
persistence:
  enabled: false


## ClickHouse resource requests and limits
resources:
  requests:
    cpu: 0.5
    memory: 500Mi
  limits:
    cpu: 3.0
    memory: 6Gi

## Authentication
auth:
  username: weave_admin
  password: "weave_123"
  existingSecret: ""
  existingSecretKey: ""


## @param logLevel Logging level
logLevel: information

## @section ClickHouse keeper configuration parameters
keeper:
  enabled: true

## @param defaultConfigurationOverrides [string] Default configuration overrides (evaluated as a template)
defaultConfigurationOverrides: |
  <clickhouse>
    <!-- Macros -->
    <macros>
      <shard from_env="CLICKHOUSE_SHARD_ID"></shard>
      <replica from_env="CLICKHOUSE_REPLICA_ID"></replica>
    </macros>
    <!-- Log Level -->
    <logger>
      <level>{{ .Values.logLevel }}</level>
    </logger>
    {{- if or (ne (int .Values.shards) 1) (ne (int .Values.replicaCount) 1)}}
    <remote_servers>
      <{{ .Values.clusterName }}>
        {{- $shards := $.Values.shards | int }}
        {{- range $shard, $e := until $shards }}
        <shard>
          <internal_replication>true</internal_replication>
          {{- $replicas := $.Values.replicaCount | int }}
          {{- range $i, $_e := until $replicas }}
          <replica>
            <host>{{ printf "%s-shard%d-%d.%s.%s.svc.%s" (include "common.names.fullname" $ ) $shard $i (include "clickhouse.headlessServiceName" $) (include "common.names.namespace" $) $.Values.clusterDomain }}</host>
            <port>{{ $.Values.service.ports.tcp }}</port>
          </replica>
          {{- end }}
        </shard>
        {{- end }}
      </{{ .Values.clusterName }}>
    </remote_servers>
    {{- end }}
    {{- if .Values.keeper.enabled }}
    <keeper_server>
      <tcp_port>{{ $.Values.containerPorts.keeper }}</tcp_port>
      {{- if .Values.tls.enabled }}
      <tcp_port_secure>{{ $.Values.containerPorts.keeperSecure }}</tcp_port_secure>
      {{- end }}
      <server_id from_env="KEEPER_SERVER_ID"></server_id>
      <log_storage_path>/bitnami/clickhouse/keeper/coordination/log</log_storage_path>
      <snapshot_storage_path>/bitnami/clickhouse/keeper/coordination/snapshots</snapshot_storage_path>
      <coordination_settings>
        <operation_timeout_ms>10000</operation_timeout_ms>
        <session_timeout_ms>30000</session_timeout_ms>
        <raft_logs_level>trace</raft_logs_level>
      </coordination_settings>
      <raft_configuration>
        {{- $nodes := .Values.replicaCount | int }}
        {{- range $node, $e := until $nodes }}
        <server>
          <id>{{ $node | int }}</id>
          <hostname from_env="{{ printf "KEEPER_NODE_%d" $node }}"></hostname>
          <port>{{ $.Values.service.ports.keeperInter }}</port>
        </server>
        {{- end }}
      </raft_configuration>
    </keeper_server>
    {{- end }}
    {{- if or .Values.keeper.enabled .Values.zookeeper.enabled .Values.externalZookeeper.servers }}
    <zookeeper>
      {{- if or .Values.keeper.enabled }}
      {{- $nodes := .Values.replicaCount | int }}
      {{- range $node, $e := until $nodes }}
      <node>
        <host from_env="{{ printf "KEEPER_NODE_%d" $node }}"></host>
        <port>{{ $.Values.service.ports.keeper }}</port>
      </node>
      {{- end }}
      {{- else if .Values.zookeeper.enabled }}
      {{- $nodes := .Values.zookeeper.replicaCount | int }}
      {{- range $node, $e := until $nodes }}
      <node>
        <host from_env="{{ printf "KEEPER_NODE_%d" $node }}"></host>
        <port>{{ $.Values.zookeeper.service.ports.client }}</port>
      </node>
      {{- end }}
      {{- else if .Values.externalZookeeper.servers }}
      {{- range $node :=.Values.externalZookeeper.servers }}
      <node>
        <host>{{ $node }}</host>
        <port>{{ $.Values.externalZookeeper.port }}</port>
      </node>
      {{- end }}
      {{- end }}
    </zookeeper>
    {{- end }}
    {{- if .Values.metrics.enabled }}
    <prometheus>
      <endpoint>/metrics</endpoint>
      <port from_env="CLICKHOUSE_METRICS_PORT"></port>
      <metrics>true</metrics>
      <events>true</events>
      <asynchronous_metrics>true</asynchronous_metrics>
    </prometheus>
    {{- end }}
    <storage_configuration>
      <disks>
        <s3_disk>
          <type>s3</type>
          <!-- MODIFY THE BUCKET NAME -->
          <endpoint>https://s3.us-east-1.amazonaws.com/bucketname/foldername</endpoint>
          <!-- MODIFY THE BUCKET NAME -->

          <!-- AVOID USE CREDENTIALS CHECK THE RECOMMENDATION -->
          <access_key_id>xxx</access_key_id>
          <secret_access_key>xxx</secret_access_key>
          <!-- AVOID USE CREDENTIALS CHECK THE RECOMMENDATION -->

         <metadata_path>/var/lib/clickhouse/disks/s3_disk/</metadata_path>
        </s3_disk>
        <s3_disk_cache>
  	      <type>cache</type>
          <disk>s3_disk</disk>
          <path>/var/lib/clickhouse/s3_disk_cache/cache/</path>
          <max_size>100Gi</max_size>
          <cache_on_write_operations>1</cache_on_write_operations>
          <enable_filesystem_cache_on_write_operations>1</enable_filesystem_cache_on_write_operations> 
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

## @section Zookeeper subchart parameters
zookeeper:
  enabled: false
```
#### **Note:** Providing S3 Credentials

You can specify credentials for accessing an S3 bucket in two ways:

1. **Hardcoded in the Configuration**    
   Directly include the credentials in the storage configuration:

   `<type>s3</type>`

`<endpoint>https://s3.us-east-1.amazonaws.com/bucketname/foldername</endpoint>`  
`<access_key_id>xxx</access_key_id>`  
`<secret_access_key>xxx</secret_access_key>`

2. **Using Environment Variables or EC2 Metadata**  
   Instead of hardcoding credentials, you can enable ClickHouse to fetch them dynamically from environment variables or Amazon EC2 instance metadata:

   `<use_environment_credentials>true</use_environment_credentials>`  
   
   More details at [ClickHouse: Separation of Storage and Compute](https://clickhouse.com/docs/en/guides/separation-storage-compute).

### Install ClickHouse

With the reposiories prepared and `values.yaml` ready, the next step is deploy ClickHouse.
```
helm install --create-namespace --namespace <NAMESPACE> clickhouse bitnami/clickhouse -f values.yaml 
```
* If you don't want to create namespace or install in a specific namespace, remove he argunments `--create-namespace --namespace <NAMESPACE>`

#### Confirm Clickhouse deployment

```
kubectl get pods -n <NAMESPACE>
```

## Deploy W&B Weave

Weave is already available for automatic deployment via [W&B Operator](https://docs.wandb.ai/guides/hosting/operator/#wb-kubernetes-operator). With the W&B Platform installed, the next steps are:

1. Edit the [CR instance](https://docs.wandb.ai/guides/hosting/operator/#complete-example) used to deploy the platform
2. Add the Weave configuration.

### Gathering information

Use the service information from Kubernetes to configure Weave Trace:

- **Endpoint**: `<release-name>-headless.<namespace>.svc.cluster.local`
  - Replace `<release-name>` with your helm release name
  - Replace `<namespace>` with `NAMESPACE`
  - **Get the service details:** `kubectl get svc -n <namespace>`
- **Username** set in the `values.yaml`
- **Password** also set in the `values.yaml`

With the information above, reconfigure the W&B Platform CR, and ad the following configuration 

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

      weave-trace:
        enabled: true
    [...]
    weave-trace:
      install: true
    [...]
```

The final configuration may look like the example below:

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
      host: https://abc-wandb.sandbox-gcp.wandb.ml

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

      weave-trace:
        enabled: true
 
    ingress:
      annotations:
        ingress.gcp.kubernetes.io/pre-shared-cert: abc-wandb-cert-creative-puma
        kubernetes.io/ingress.class: gce
        kubernetes.io/ingress.global-static-ip-name: abc-wandb-operator-address

    weave-trace:
      install: true
```

With the CR ready, simply apply the new configuration

`kubectl apply -n <NAMESPACE> -f wandb.yaml`

:::tip
Ensure the license has the Weave Trace enable
:::

