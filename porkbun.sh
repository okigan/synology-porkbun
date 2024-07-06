#!/bin/sh

# Synology router will call the script with these parameters:
# $1 = username (API_KEY in our case)
# $2 = password (SECRET_KEY in our case)
# $3 = hostname (DOMAIN in our case)
# $4 = ip (new IP address)

# set -o xtrace

# echo $1, $2, $3, $4 >> /tmp/log.txt


API_BASE="https://api.porkbun.com/api/json/v3/dns"
API_KEY="$1"
SECRET_KEY="$2"
FULL_DOMAIN="$3"
NEW_IP="$4"

api_call() {
    curl -s -X POST "$1" -H "Content-Type: application/json" \
         -d "{\"secretapikey\":\"$SECRET_KEY\",\"apikey\":\"$API_KEY\"$2}"
}

# Extract domain and subdomain
DOMAIN=$(echo "$FULL_DOMAIN" | awk -F. '{print $(NF-1)"."$NF}')
SUBDOMAIN=$(echo "$FULL_DOMAIN" | sed "s/.$DOMAIN$//")

# Construct API endpoint
if [ -n "$SUBDOMAIN" ]; then
    API_ENDPOINT="$API_BASE/retrieveByNameType/$DOMAIN/A/$SUBDOMAIN"
else
    API_ENDPOINT="$API_BASE/retrieveByNameType/$DOMAIN/A"
fi

RECORD=$(api_call "$API_ENDPOINT")

if ! echo "$RECORD" | grep -q '"status":"SUCCESS"'; then
    echo "nohost"; exit 1
fi

CURRENT_IP=$(echo "$RECORD" | sed -n 's/.*"content"\s*:\s*"\([^"]*\)".*/\1/p' | head -n1)

[ "$NEW_IP" = "$CURRENT_IP" ] && { echo "nochg"; exit 0; }

# Construct update endpoint
if [ -n "$SUBDOMAIN" ]; then
    UPDATE_ENDPOINT="$API_BASE/editByNameType/$DOMAIN/A/$SUBDOMAIN"
else
    UPDATE_ENDPOINT="$API_BASE/editByNameType/$DOMAIN/A"
fi

UPDATE=$(api_call "$UPDATE_ENDPOINT" ",\"content\":\"$NEW_IP\"")

if ! echo "$UPDATE" | grep -q '"status":"SUCCESS"'; then
    case "$(echo "$UPDATE" | sed -n 's/.*"message"\s*:\s*"\([^"]*\)".*/\1/p')" in
        *"authentication"*) echo "badauth" ;;
        *"not found"*) echo "nohost" ;;
        *) echo "911" ;;
    esac
    exit 1
fi

echo "good"