def build_document_tree(documents):
    """Build a tree structure from documents using '/' as separator"""
    tree = {}
    
    for doc in documents:
        parts = doc.title.split('/')
        current = tree
        
        # Navigate/create tree structure
        for part in parts[:-1]:
            part = part.strip()
            if part not in current:
                current[part] = {'_children': {}, '_docs': []}
            current = current[part]['_children']
        
        # Add document to the final level
        if '_docs' not in current:
            current['_docs'] = []
        current['_docs'].append(doc)
    
    return tree

