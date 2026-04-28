# Backup operations

## Schedule (cron, daily at 02:30 UTC)

```bash
# Add to /etc/cron.d/urip-backup on the VPS:
SHELL=/bin/bash
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin
30 2 * * * root /opt/urip-adaptive-mind/scripts/backup_postgres.sh >> /var/log/urip-backup.log 2>&1
```

Verify it landed:
```bash
sudo crontab -u root -l | grep backup_postgres
sudo cat /etc/cron.d/urip-backup
```

## Manual restore drill (run quarterly)

```bash
# 1. Pick a backup file
ls -la /var/backups/urip/

# 2. Spin up a throwaway postgres container
docker run --name urip-restore-test -e POSTGRES_USER=urip \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=urip \
  -p 5499:5432 -d postgres:16-alpine
sleep 5

# 3. Restore
gunzip -c /var/backups/urip/urip_backup_YYYYMMDD_HHMMSS.sql.gz | \
  docker exec -i urip-restore-test psql -U urip -d urip

# 4. Spot-check (count tables, count rows)
docker exec urip-restore-test psql -U urip -d urip -c "\dt" | head -20
docker exec urip-restore-test psql -U urip -d urip -c "SELECT COUNT(*) FROM tenants;"
docker exec urip-restore-test psql -U urip -d urip -c "SELECT COUNT(*) FROM users;"
docker exec urip-restore-test psql -U urip -d urip -c "SELECT COUNT(*) FROM risks;"

# 5. Tear down
docker rm -f urip-restore-test
```

## S3 offsite (recommended; not yet wired)

```bash
# Add to backup_postgres.sh after the local dump succeeds:
aws s3 cp "${OUT_FILE}" \
  "s3://${URIP_BACKUP_BUCKET}/postgres/$(basename "${OUT_FILE}")" \
  --storage-class STANDARD_IA \
  --sse AES256

# IAM policy for the backup user (least privilege):
# {
#   "Version": "2012-10-17",
#   "Statement": [{
#     "Sid": "BackupBucketRW",
#     "Effect": "Allow",
#     "Action": ["s3:PutObject", "s3:PutObjectAcl", "s3:GetObject"],
#     "Resource": "arn:aws:s3:::your-bucket/postgres/*"
#   }]
# }
```

## Retention

`backup_postgres.sh` keeps 14 days of local dumps. Adjust via the
`RETENTION_DAYS` env var (passed in cron line if needed). PIPESTATUS-safe
prune ensures old backups are deleted ONLY after a successful new dump.

## Monitoring

The script exits non-zero on any failure. Cron will email root@host on
non-zero exit. Forward root mail to a real address, or wrap the cron line in
a wrapper script that POSTs to a Slack/PagerDuty webhook on failure.
