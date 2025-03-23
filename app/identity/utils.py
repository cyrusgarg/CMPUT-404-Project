import requests
from .models import RemoteNode

def send_to_node(node_id, endpoint, method='GET', data=None):
    """
    Send data to a remote node using HTTP Basic Auth.
    """
    try:
        node = RemoteNode.objects.get(id=node_id, is_active=True)
        
        # Construct the full URL
        url = f"{node.host_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Prepare the request with Basic Auth
        auth = (node.username, node.password)
        headers = {'Content-Type': 'application/json'}
        
        # Make the request
        if method.upper() == 'GET':
            response = requests.get(url, auth=auth, headers=headers)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, auth=auth, headers=headers)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, auth=auth, headers=headers)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, auth=auth, headers=headers)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
            
        return response
        
    except RemoteNode.DoesNotExist:
        return None