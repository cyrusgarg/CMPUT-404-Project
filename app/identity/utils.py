import requests
import re
from urllib.parse import urlparse, urlunparse
from .models import RemoteNode

def send_to_node(node_id, endpoint, method='GET', data=None):
    """
    Send data to a remote node using HTTP Basic Auth.
    """
    try:
        node = RemoteNode.objects.get(id=node_id, is_active=True)
        
        # Ensure the URL is properly formatted (IPv6 with brackets)
        host_url = node.host_url.rstrip('/')
        if ':' in host_url.replace('http://', '').replace('https://', '') and not '[' in host_url:
            # It's an IPv6 address without brackets
            protocol = 'https://' if host_url.startswith('https://') else 'http://'
            address = host_url.replace('http://', '').replace('https://', '')
            host_url = f"{protocol}[{address}]"
        
        # Construct the full URL
        url = f"{host_url}/{endpoint.lstrip('/')}"
        
        print(f"Connecting to URL: {url}")
        print(f"Using credentials: {node.username}:{'*' * len(node.password)}")
        
        # Prepare the request with Basic Auth
        auth = (node.username, node.password)
        headers = {'Content-Type': 'application/json'}
        
        # Make the request with a longer timeout
        if method.upper() == 'GET':
            response = requests.get(url, auth=auth, headers=headers, timeout=30)
        elif method.upper() == 'POST':
            response = requests.post(url, json=data, auth=auth, headers=headers, timeout=30)
        elif method.upper() == 'PUT':
            response = requests.put(url, json=data, auth=auth, headers=headers, timeout=30)
        elif method.upper() == 'DELETE':
            response = requests.delete(url, auth=auth, headers=headers, timeout=30)
        else:
            raise ValueError(f"Unsupported HTTP method: {method}")
        
        # Log response details
        print(f"Response status: {response.status_code}")
        print(f"Response content (first 100 chars): {response.text[:100]}")
        
        return response
        
    except RemoteNode.DoesNotExist:
        print("RemoteNode not found")
        return None
    except Exception as e:
        print(f"Error connecting to node: {type(e).__name__} - {str(e)}")
        return None