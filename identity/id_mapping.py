# identity/id_mapper.py
from django.core.cache import cache


def get_numeric_id_for_author(uuid_id):
    """
    Maps a UUID to a sequential numeric ID.
    Uses Django's cache to store the mapping.
    """
    # Cache key for the mapping
    mapping_key = "author_uuid_to_numeric_mapping"
    # Get the current mapping from cache
    mapping = cache.get(mapping_key, {})
    # Convert UUID to string for use as dict key
    uuid_str = str(uuid_id)
    
    # If this UUID isn't in our mapping yet, assign it the next available number
    if uuid_str not in mapping:
        # The next ID is 1 + the current number of entries
        next_id = len(mapping) + 1
        mapping[uuid_str] = next_id
        # Save the updated mapping back to cache
        cache.set(mapping_key, mapping)
    
    return mapping[uuid_str]

def get_uuid_for_numeric_id(numeric_id):
    """
    Reverse lookup: converts a sequential numeric ID back to the original UUID.
    Uses the same cache mapping as get_numeric_id_for_author.
    """
    # Cache key for the mapping
    mapping_key = "author_uuid_to_numeric_mapping"
    # Get the current mapping from cache
    mapping = cache.get(mapping_key, {})
    
    # Create reverse mapping (numeric_id -> uuid)
    reverse_mapping = {v: k for k, v in mapping.items()}
    
    # Look up the UUID for this numeric ID
    uuid_str = reverse_mapping.get(numeric_id)
    
    if uuid_str is None:
        return None
    
    return uuid_str