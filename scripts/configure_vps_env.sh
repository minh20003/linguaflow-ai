#!/usr/bin/env sh
# Configure only deployment-specific values. Application and provider secrets
# already present in .env are preserved; the database password is generated on
# the VPS and never written to source control.
set -eu

app_domain=${1:?usage: configure_vps_env.sh APP_DOMAIN API_DOMAIN}
api_domain=${2:?usage: configure_vps_env.sh APP_DOMAIN API_DOMAIN}
env_file=.env

if [ ! -f "$env_file" ]; then
  echo "Missing $env_file" >&2
  exit 1
fi

upsert_env() {
  key=$1
  value=$2
  if grep -q "^${key}=" "$env_file"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$env_file"
  else
    printf '%s=%s\n' "$key" "$value" >> "$env_file"
  fi
}

acme_email=$(sed -n 's/^SMTP_FROM_EMAIL=//p' "$env_file" | head -n 1)
if [ -z "$acme_email" ]; then
  echo "SMTP_FROM_EMAIL must be set before deployment" >&2
  exit 1
fi

upsert_env POSTGRES_DB linguaflow
upsert_env POSTGRES_USER linguaflow
upsert_env POSTGRES_PASSWORD "$(openssl rand -hex 24)"
upsert_env APP_ENV production
upsert_env ENVIRONMENT production
upsert_env CORS_ORIGINS "https://${app_domain}"
upsert_env APP_DOMAIN "$app_domain"
upsert_env API_DOMAIN "$api_domain"
upsert_env ACME_EMAIL "$acme_email"
upsert_env NEXT_PUBLIC_API_URL "https://${api_domain}"

chmod 600 "$env_file"
