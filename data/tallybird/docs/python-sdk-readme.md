---
id: doc:python-sdk-readme
title: Python SDK README
kind: guide
authors: [person:kenji]
updated: "2026-04-20"
about: [svc:python-sdk, api:rest-v1, api:rest-v2]
cites: [doc:api-quickstart]
---
# tallybird-python

The official Python client for Tallybird.

## Install
`pip install tallybird`

## Usage
```python
import os, tallybird
client = tallybird.Client(api_key=os.environ["TALLYBIRD_API_KEY"])
invoice = client.invoices.create(customer="cus_123", amount=4200, currency="eur")
```

The client talks to REST API v1 by default and authenticates with your API key. To opt in to REST API v2, pass `api_version="v2"` together with OAuth client credentials.

## Retries
The SDK retries idempotent requests twice on network errors.
