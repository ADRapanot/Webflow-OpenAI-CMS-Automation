# Get Collection ID

curl https://api.webflow.com/v2/collections/$WEBFLOW_COLLECTION_ID \
 -H "Authorization: Bearer df611c0cef967c53524ccad395f6632e8b5b840acc8f14d5bc1d1e15d49b8633" \
 -H "accept-version: 2.0.0" \
 -o collection_schema.json

# Get Site ID

curl https://api.webflow.com/v2/sites \
 -H "Authorization: Bearer df611c0cef967c53524ccad395f6632e8b5b840acc8f14d5bc1d1e15d49b8633" \
 -H "accept-version: 2.0.0" \
 -o collection_schema.json
