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
DOMAIN="$3"
NEW_IP="$4"

# Function to make API calls
api_call() {
    curl -s -X POST "$1" \
         -H "Content-Type: application/json" \
         -d "{\"secretapikey\":\"$SECRET_KEY\",\"apikey\":\"$API_KEY\"$2}"
}

# Function to extract value from JSON response
get_json_value() {
    echo "$1" | sed -n 's/.*"'"$2"'"\s*:\s*"\([^"]*\)".*/\1/p'
}

# Retrieve current DNS record
RECORD=$(api_call "$API_BASE/retrieveByNameType/$DOMAIN/A")

if ! echo "$RECORD" | grep -q '"status":"SUCCESS"'; then
    echo "nohost"
    exit 1
fi

CURRENT_IP=$(echo "$RECORD" | sed -n 's/.*"content"\s*:\s*"\([^"]*\)".*/\1/p' | head -n1)

if [ "$NEW_IP" = "$CURRENT_IP" ]; then
    echo "nochg"
    exit 0
fi

# Update DNS record
UPDATE=$(api_call "$API_BASE/editByNameType/$DOMAIN/A" ",\"content\":\"$NEW_IP\"")

if ! echo "$UPDATE" | grep -q '"status":"SUCCESS"'; then
    error_message=$(get_json_value "$UPDATE" "message")
    case "$error_message" in
        *"authentication"*) echo "badauth" ;;
        *"not found"*) echo "nohost" ;;
        *) echo "911" ;;
    esac
    exit 1
fi

echo "good"
exit 0

