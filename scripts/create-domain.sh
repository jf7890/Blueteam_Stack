#!/usr/bin/env bash
set -euo pipefail

# ==============================
# Configuration (edit these)
# ==============================

# Base URL of nginx-love backend API
API_BASE="${API_BASE:-http://localhost:3001/api}"

# Admin login (set ADMIN_PASSWORD via env or edit here)
ADMIN_USERNAME="${ADMIN_USERNAME:-admin}"
ADMIN_PASSWORD="${ADMIN_PASSWORD:-Vannhan123@}"

# Strong password you want to use for admin AFTER bootstrap (only used if server requires first-login change)
NEW_ADMIN_PASSWORD="${NEW_ADMIN_PASSWORD:-ChangeMe!123}"

# Optional: TOTP code if 2FA is enabled (leave empty if 2FA is OFF)
TOTP_CODE="${TOTP_CODE:-}"

# Container names (only change these to auto-pick correct IPs)
PROXY_CONTAINER="${PROXY_CONTAINER:-blueteam_stack-nginx-1}"
JUICESHOP_CONTAINER="${JUICESHOP_CONTAINER:-juice-shop}"
DVWA_CONTAINER="${DVWA_CONTAINER:-dvwa}"

# If PROXY_CONTAINER is not on the same network as an upstream container, auto-connect it (true/false)
AUTO_CONNECT_NETWORK="${AUTO_CONNECT_NETWORK:-true}"

log() {
  echo "[*] $*" >&2
}

die() {
  echo "[!] $*" >&2
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || die "Missing required command: $1"
}

container_running() {
  local c="$1"
  docker inspect -f '{{.State.Running}}' "$c" 2>/dev/null | grep -qi '^true$'
}

container_networks() {
  local c="$1"
  docker inspect -f '{{range $k,$v := .NetworkSettings.Networks}}{{$k}}{{"\n"}}{{end}}' "$c" 2>/dev/null || true
}

find_common_network() {
  local a="$1"
  local b="$2"
  local net

  while IFS= read -r net; do
    [[ -z "$net" ]] && continue
    docker inspect -f "{{if index .NetworkSettings.Networks \"$net\"}}yes{{end}}" "$b" 2>/dev/null | grep -q '^yes$' && {
      echo "$net"
      return 0
    }
  done < <(container_networks "$a")

  return 1
}

container_ip_on_network() {
  local c="$1"
  local net="$2"
  docker inspect -f "{{(index .NetworkSettings.Networks \"$net\").IPAddress}}" "$c" 2>/dev/null || true
}

resolve_upstream_ip() {
  local proxy="$1"
  local target="$2"

  container_running "$proxy" || die "Proxy container not running or not found: $proxy"
  container_running "$target" || die "Target container not running or not found: $target"

  local common_net
  common_net="$(find_common_network "$proxy" "$target" || true)"

  if [[ -z "$common_net" && "$AUTO_CONNECT_NETWORK" == "true" ]]; then
    local target_net
    target_net="$(container_networks "$target" | head -n 1 || true)"
    if [[ -n "$target_net" ]]; then
      log "No common network between '$proxy' and '$target'. Connecting proxy to '$target_net'..."
      docker network connect "$target_net" "$proxy" >/dev/null 2>&1 || true
      common_net="$(find_common_network "$proxy" "$target" || true)"
    fi
  fi

  [[ -n "$common_net" ]] || die "No common Docker network between '$proxy' and '$target' (and auto-connect failed)."

  local ip
  ip="$(container_ip_on_network "$target" "$common_net")"
  [[ -n "$ip" ]] || die "Could not resolve IP of '$target' on network '$common_net'."

  log "Resolved '$target' IP on '$common_net' => $ip"
  echo "$ip"
}

build_domain_payload() {
  local domain_name="$1"
  local upstream_ip="$2"
  local upstream_port="$3"

  jq -n     --arg name "$domain_name"     --arg host "$upstream_ip"     --argjson port "$upstream_port"     '{
      name: $name,
      status: "active",
      modsecEnabled: true,
      upstreams: [
        {
          host: $host,
          port: $port,
          protocol: "http",
          sslVerify: true,
          weight: 1,
          maxFails: 3,
          failTimeout: 30
        }
      ],
      loadBalancer: {
        algorithm: "round_robin",
        healthCheckEnabled: true,
        healthCheckInterval: 30,
        healthCheckTimeout: 5,
        healthCheckPath: "/"
      },
      realIpConfig: {
        realIpEnabled: false,
        realIpCloudflare: false,
        realIpCustomCidrs: []
      },
      advancedConfig: {
        hstsEnabled: false,
        http2Enabled: true,
        grpcEnabled: false,
        clientMaxBodySize: 100,
        customLocations: []
      }
    }'
}

# ==============================
# 1. First-login password change
# ==============================

# This function is used only when the backend says "Password change required"
change_password_first_login() {
  local user_id="$1"
  local temp_token="$2"
  local new_password="$3"

  log "Changing admin password via FIRST-LOGIN endpoint..."

  local body
  body=$(jq -n     --arg u "$user_id"     --arg t "$temp_token"     --arg n "$new_password"     '{userId: $u, tempToken: $t, newPassword: $n}')

  local resp
  resp=$(curl -sS -X POST "$API_BASE/auth/first-login/change-password"     -H "Content-Type: application/json"     -d "$body")

  if ! echo "$resp" | jq . >/dev/null 2>&1; then
    log "First-login password change response is not valid JSON:"
    echo "$resp"
    return 1
  fi

  log "First-login password change API called successfully."
}

# ==============================
# 2. Login and get JWT token
#    (auto-handle first-login password change)
# ==============================

login() {
  local username="$1"
  local password="$2"

  log "Logging in as user: $username"

  # Build login request body (with optional TOTP)
  local login_body
  if [[ -n "$TOTP_CODE" ]]; then
    login_body=$(jq -n       --arg u "$username"       --arg p "$password"       --arg t "$TOTP_CODE"       '{username: $u, password: $p, totpCode: $t}')
  else
    login_body=$(jq -n       --arg u "$username"       --arg p "$password"       '{username: $u, password: $p}')
  fi

  local resp
  resp=$(curl -sS -X POST "$API_BASE/auth/login"     -H "Content-Type: application/json"     -d "$login_body")

  # Check whether the server requires a first-login password change
  local require_change
  require_change=$(echo "$resp" | jq -r '.data.requirePasswordChange // "false"' 2>/dev/null || echo "false")

  if [[ "$require_change" == "true" ]]; then
    log "Server requires first-time password change (requirePasswordChange = true)."

    local user_id temp_token
    user_id=$(echo "$resp" | jq -r '.data.userId // empty')
    temp_token=$(echo "$resp" | jq -r '.data.tempToken // empty')

    if [[ -z "$user_id" || -z "$temp_token" || "$user_id" == "null" || "$temp_token" == "null" ]]; then
      log "ERROR: requirePasswordChange=true but userId/tempToken are missing."
      log "Raw response:"
      echo "$resp"
      exit 1
    fi

    # Perform first-login password change to NEW_ADMIN_PASSWORD
    change_password_first_login "$user_id" "$temp_token" "$NEW_ADMIN_PASSWORD" || exit 1

    # After changing the password, log in again with the new password
    log "Re-logging in with NEW_ADMIN_PASSWORD after first-login password change..."

    login_body=$(jq -n       --arg u "$username"       --arg p "$NEW_ADMIN_PASSWORD"       '{username: $u, password: $p}')

    resp=$(curl -sS -X POST "$API_BASE/auth/login"       -H "Content-Type: application/json"       -d "$login_body")
  fi

  # At this point, resp should contain accessToken
  local token
  token=$(echo "$resp" | jq -r '.data.accessToken // .accessToken // empty' 2>/dev/null || echo "")

  if [[ -z "$token" || "$token" == "null" ]]; then
    log "ERROR: Cannot extract access token from login response."
    log "Raw response:"
    echo "$resp"
    exit 1
  fi

  echo "$token"
}

# ==============================
# 3. Create a domain from payload
# ==============================

create_domain() {
  local token="$1"
  local payload="$2"

  # Try to extract name from payload just for logging
  local name
  name=$(echo "$payload" | jq -r '.name // "unknown"' 2>/dev/null || echo "unknown")

  log "Creating domain '$name' via /domains ..."

  local resp
  resp=$(curl -sS -X POST "$API_BASE/domains"     -H "Authorization: Bearer $token"     -H "Content-Type: application/json"     -d "$payload")

  if ! echo "$resp" | jq . >/dev/null 2>&1; then
    log "Create domain response is not valid JSON:"
    echo "$resp"
    return 1
  fi

  log "Domain '$name' created. Response:"
  echo "$resp" | jq .
}

# ==============================
# Main flow
# ==============================

main() {
  require_cmd curl
  require_cmd jq
  require_cmd docker

  log "=== Step 0: Resolve upstream IPs (from container names) ==="
  local juice_ip dvwa_ip
  juice_ip="$(resolve_upstream_ip "$PROXY_CONTAINER" "$JUICESHOP_CONTAINER")"
  dvwa_ip="$(resolve_upstream_ip "$PROXY_CONTAINER" "$DVWA_CONTAINER")"

  local DOMAIN_JUICESHOP_PAYLOAD DOMAIN_DVWA_PAYLOAD
  DOMAIN_JUICESHOP_PAYLOAD="$(build_domain_payload "juiceshop.local" "$juice_ip" 3000)"
  DOMAIN_DVWA_PAYLOAD="$(build_domain_payload "dvwa.local" "$dvwa_ip" 80)"

  log "=== Step 1: Login & (if required) change admin password ==="
  local token
  token=$(login "$ADMIN_USERNAME" "$ADMIN_PASSWORD")
  log "Access token acquired."

  log "=== Step 2: Create juiceshop.local ==="
  create_domain "$token" "$DOMAIN_JUICESHOP_PAYLOAD"

  log "=== Step 3: Create dvwa.local ==="
  create_domain "$token" "$DOMAIN_DVWA_PAYLOAD"

  log "Bootstrap completed."
}

main "$@"