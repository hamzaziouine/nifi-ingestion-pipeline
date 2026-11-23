# Parameter context

Everything that changes between environments sits in one parameter context,
`Paramètres ingestion cars`, bound to the `Ingestion cars` group.

| Parameter | Sensitive | Used by | Meaning | Local value (docker compose) |
|---|---|---|---|---|
| `chemin_in` | no | ListFile `Input Directory`, FetchFile `Move Destination Directory` (`#{chemin_in}/traite`) | Folder watched for CSV files. Processed files are moved to its `traite/` subfolder. | any folder NiFi can write to, e.g. `/srv/ingestion/in` or `C:\ingestion\in` |
| `bucket` | no | both PutS3Object | Target bucket | `bronze` (`S3_BUCKET`) |
| `url_jdbc` | no | `MySQL nifi_test` pool | JDBC URL | `jdbc:mysql://localhost:3306/nifi_test` |
| `mot_de_passe_mysql` | yes | `MySQL nifi_test` pool | Password of the `nifi` database user | `MYSQL_PASSWORD` |
| `cle_acces_minio` | yes | `Identifiants MinIO` | S3 access key | `NIFI_S3_ACCESS_KEY` |
| `cle_secrete_minio` | yes | `Identifiants MinIO` | S3 secret key | `NIFI_S3_SECRET_KEY` |

The names are French: `chemin` = path, `mot de passe` = password, `clé d'accès` /
`clé secrète` = access / secret key.

## What gets versioned

NiFi never exports a sensitive value. In `flows/ingestion-cars.json` the three sensitive
parameters exist with `value: null`, and the services only reference them
(`#{mot_de_passe_mysql}` and so on). `tests/test_flow_contract.py` fails if a future
snapshot ever carries a value or a literal secret.

Non-sensitive values are versioned with the flow (the registry client keeps parameter
values). That makes the snapshot importable as is on a dev machine, and the values are
overridden per environment.

## One context per environment

Two ways to run the same versioned flow in several environments:

- keep the context name and give it different values on each NiFi instance (simplest:
  the import creates the context, you fill in the values once per instance);
- on a shared instance, create one context per environment with the same parameter
  names, for example `ingestion-cars-dev` and `ingestion-cars-prod`, and bind each copy
  of the group to its own context (group > Configure > Parameter Context).

Changing a parameter value restarts only the components that reference it. NiFi stops
them, applies the value and starts them again.

## Settings that are not parameters yet

These are plain properties in the current snapshot. They work for a single local
install, and they are the first candidates for the next version:

| Setting | Where | Current value |
|---|---|---|
| S3 endpoint | both PutS3Object | `http://localhost:9000` |
| S3 region | both PutS3Object | `us-east-1` |
| Database user | `MySQL nifi_test` | `nifi` |
| Quarantine base directory | Quarantaine (PutFile) | relative path under the NiFi working directory |
| Retry budget | Router selon les tentatives | `${tentatives:lt(5)}` |
| Retry spacing | Router selon les tentatives, run schedule | 20 s |
| Listing period and minimum file age | Lister les CSV | 10 s and 10 s |
