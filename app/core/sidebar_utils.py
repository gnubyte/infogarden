def build_document_tree(documents, org_id):
    """Build a tree structure from folders and documents"""
    from app.modules.docs.models import DocumentFolder
    
    # Get all folders for this org
    folders = DocumentFolder.query.filter_by(org_id=org_id).order_by(DocumentFolder.name).all()
    
    # Build folder map
    folder_map = {f.id: f for f in folders}
    
    # Build tree structure
    tree = {}
    
    # Helper function to get or create folder node
    def get_folder_node(folder_id):
        if folder_id is None:
            return tree
        folder = folder_map.get(folder_id)
        if not folder:
            return tree
        
        # Build path to this folder
        path_parts = []
        current = folder
        while current:
            path_parts.insert(0, current.id)
            current = current.parent
        
        # Navigate/create tree structure
        node = tree
        for part_id in path_parts:
            folder = folder_map[part_id]
            if folder.id not in node:
                node[folder.id] = {
                    '_type': 'folder',
                    '_folder': folder,
                    '_children': {},
                    '_docs': []
                }
            node = node[folder.id]['_children']
        return node
    
    # Add folders to tree
    for folder in folders:
        parent_node = get_folder_node(folder.parent_id)
        if folder.id not in parent_node:
            parent_node[folder.id] = {
                '_type': 'folder',
                '_folder': folder,
                '_children': {},
                '_docs': []
            }
    
    # Add documents to tree
    for doc in documents:
        target_node = get_folder_node(doc.folder_id)
        if '_docs' not in target_node:
            target_node['_docs'] = []
        target_node['_docs'].append(doc)
    
    return tree



