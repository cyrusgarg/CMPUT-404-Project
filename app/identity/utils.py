import requests
from urllib.parse import urlparse
from .models import RemoteNode

def send_to_node(node_id, endpoint, method='GET', data=None):
    """
    Send data to a remote node using HTTP Basic Auth.
    """
    try:
        node = RemoteNode.objects.get(id=node_id, is_active=True)
        
        # Construct the full URL
        url = f"{node.host_url.rstrip('/')}/{endpoint.lstrip('/')}"
        
        # Handle IPv6 addresses in URLs if needed
        parsed_url = urlparse(url)
        if ':' in parsed_url.netloc and '[' not in parsed_url.netloc:
            # This is an IPv6 address without brackets - add them
            host_parts = parsed_url.netloc.split(':')
            if len(host_parts) > 2:  # More than one colon means IPv6
                # Extract port if present
                port = None
                if len(host_parts) > 6:  # IPv6 with port
                    port = host_parts[-1]
                    ipv6 = ':'.join(host_parts[:-1])
                else:
                    ipv6 = parsed_url.netloc
                
                # Reconstruct with proper IPv6 formatting
                new_netloc = f"[{ipv6}]"
                if port:
                    new_netloc += f":{port}"
                
                # Rebuild the URL
                url_parts = list(parsed_url)
                url_parts[1] = new_netloc
                url = urlparse.urlunparse(url_parts)
        
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