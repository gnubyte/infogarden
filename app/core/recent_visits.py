"""
Recent visits tracking for user navigation history
"""
from flask import session
from typing import List, Dict, Optional


def add_recent_visit(resource_type: str, resource_id: int, name: str, url: str):
    """
    Add a recent visit to the session.
    
    Args:
        resource_type: Type of resource (document, contact, org, etc.)
        resource_id: ID of the resource
        name: Display name of the resource
        url: URL to the resource
    """
    if 'recent_visits' not in session:
        session['recent_visits'] = []
    
    recent_visits = session['recent_visits']
    
    # Remove any existing entry with the same resource_type and resource_id
    recent_visits = [v for v in recent_visits if not (
        v.get('type') == resource_type and v.get('id') == resource_id
    )]
    
    # Add new visit at the beginning
    recent_visits.insert(0, {
        'type': resource_type,
        'id': resource_id,
        'name': name,
        'url': url
    })
    
    # Keep only the last 10 visits
    recent_visits = recent_visits[:10]
    
    session['recent_visits'] = recent_visits
    session.modified = True


def get_recent_visits() -> List[Dict]:
    """
    Get the list of recent visits from the session.
    
    Returns:
        List of recent visit dictionaries
    """
    return session.get('recent_visits', [])


def remove_recent_visit(resource_type: str, resource_id: int):
    """
    Remove a specific visit from recent visits.
    
    Args:
        resource_type: Type of resource
        resource_id: ID of the resource
    """
    if 'recent_visits' not in session:
        return
    
    recent_visits = session['recent_visits']
    recent_visits = [v for v in recent_visits if not (
        v.get('type') == resource_type and v.get('id') == resource_id
    )]
    
    session['recent_visits'] = recent_visits
    session.modified = True


def clear_recent_visits():
    """
    Clear all recent visits.
    """
    if 'recent_visits' in session:
        session['recent_visits'] = []
        session.modified = True


