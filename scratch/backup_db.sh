#!/bin/bash

# Configuration
DB_NAME="stall_cart_prod"
DB_USER="stallcart"
DB_PASS="manish@vivek@7080"
BACKUP_DIR="/var/backups/stall_cart"
DATE=$(date +%Y-%m-%d_%H-%M-%S)
BACKUP_FILE="${BACKUP_DIR}/${DB_NAME}_backup_${DATE}.sql.gz"
LOG_FILE="/var/log/stall_cart_backup.log"

# --- EMAIL BACKUP SETTINGS ---
# Set this to "true" to send email backups, or "false" to disable them.
SEND_EMAIL_BACKUP="true"
# ------------------------------

# Ensure backup directory exists
mkdir -p "${BACKUP_DIR}"

# Run mysqldump and compress
echo "[$(date)] Starting backup of ${DB_NAME}..." >> "${LOG_FILE}"
if mysqldump --no-tablespaces -u "${DB_USER}" -h "127.0.0.1" -p"${DB_PASS}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"; then
    echo "[$(date)] Backup completed successfully: ${BACKUP_FILE}" >> "${LOG_FILE}"
    
    # If email backup is enabled, send it
    if [ "${SEND_EMAIL_BACKUP}" = "true" ]; then
        echo "[$(date)] Sending backup email..." >> "${LOG_FILE}"
        if /var/www/stall_cart_project/venv/bin/python /root/send_backup_email.py "${BACKUP_FILE}" >> "${LOG_FILE}" 2>&1; then
            echo "[$(date)] Backup email sent successfully." >> "${LOG_FILE}"
        else
            echo "[$(date)] Backup email sending FAILED!" >> "${LOG_FILE}"
        fi
    fi
else
    echo "[$(date)] Backup FAILED!" >> "${LOG_FILE}"
    exit 1
fi

# Keep only the last 30 days of backups
find "${BACKUP_DIR}" -name "${DB_NAME}_backup_*.sql.gz" -type f -mtime +30 -delete
echo "[$(date)] Cleaned up backups older than 30 days." >> "${LOG_FILE}"
