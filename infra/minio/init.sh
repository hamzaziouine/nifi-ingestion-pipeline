#!/bin/sh
# Runs once in the minio-init container: bucket + a NiFi user limited to that bucket.
set -eu

until mc alias set local http://minio:9000 "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; do
  echo "waiting for minio..."
  sleep 2
done

mc mb --ignore-existing "local/$S3_BUCKET"

cat > /tmp/nifi-writer.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [
    {"Effect": "Allow", "Action": ["s3:GetBucketLocation", "s3:ListBucket"],
     "Resource": ["arn:aws:s3:::$S3_BUCKET"]},
    {"Effect": "Allow", "Action": ["s3:PutObject", "s3:GetObject", "s3:AbortMultipartUpload", "s3:ListMultipartUploadParts"],
     "Resource": ["arn:aws:s3:::$S3_BUCKET/*"]}
  ]
}
EOF

mc admin policy create local nifi-writer /tmp/nifi-writer.json >/dev/null 2>&1 || true
mc admin user add local "$NIFI_S3_ACCESS_KEY" "$NIFI_S3_SECRET_KEY" >/dev/null
mc admin policy attach local nifi-writer --user "$NIFI_S3_ACCESS_KEY" >/dev/null 2>&1 || true

echo "bucket $S3_BUCKET ready, user $NIFI_S3_ACCESS_KEY can write to it"
