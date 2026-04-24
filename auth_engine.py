CLIENTS = {
    "test_client": "secret123"
}

def authenticate_client(client_id, api_key):
    return CLIENTS.get(client_id) == api_key