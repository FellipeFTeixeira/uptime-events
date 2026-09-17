#!/usr/bin/env sh
# CPU time percentiles per invocation for the spike Worker (last 24h).
# Requires: CLOUDFLARE_API_TOKEN (Account Analytics: Read) and CLOUDFLARE_ACCOUNT_ID.
set -eu
START=$(date -u -d '24 hours ago' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v-24H +%Y-%m-%dT%H:%M:%SZ)
END=$(date -u +%Y-%m-%dT%H:%M:%SZ)
GQL='query($acc:string,$s:string,$e:string){viewer{accounts(filter:{accountTag:$acc}){workersInvocationsAdaptive(limit:1000,filter:{scriptName:"uptime-spike",datetime_geq:$s,datetime_leq:$e}){sum{requests subrequests errors}quantiles{cpuTimeP50 cpuTimeP90 cpuTimeP99 wallTimeP50 wallTimeP99}dimensions{status}}}}}'
curl -sS https://api.cloudflare.com/client/v4/graphql \
  -H "Authorization: Bearer $CLOUDFLARE_API_TOKEN" \
  -H "Content-Type: application/json" \
  --data "{\"query\":\"$GQL\",\"variables\":{\"acc\":\"$CLOUDFLARE_ACCOUNT_ID\",\"s\":\"$START\",\"e\":\"$END\"}}"
