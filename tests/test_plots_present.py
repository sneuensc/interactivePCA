"""Test that plots are actually present in the app layout."""

import tempfile
import os
from pathlib import Path
from interactive_pca import create_app
from interactive_pca.args import parse_args

def create_test_data():
    """Create temporary test files."""
    tmpdir = tempfile.mkdtemp()
    
    # Create test eigenvec file
    eigenvec_path = os.path.join(tmpdir, 'test.eigenvec')
    with open(eigenvec_path, 'w') as f:
        f.write("#IID\tPC1\tPC2\tPC3\n")
        f.write("sample1\t0.1\t0.2\t0.3\n")
        f.write("sample2\t0.4\t0.5\t0.6\n")
        f.write("sample3\t0.7\t0.8\t0.9\n")
        f.write("sample4\t-0.1\t-0.2\t-0.3\n")
        f.write("sample5\t-0.4\t-0.5\t-0.6\n")
    
    # Create test annotation file
    anno_path = os.path.join(tmpdir, 'test.anno')
    with open(anno_path, 'w') as f:
        f.write("id\tgroup\ttime\tlat\n")
        f.write("sample1\tA\t100\t45.5\n")
        f.write("sample2\tA\t200\t46.0\n")
        f.write("sample3\tB\t300\t47.0\n")
        f.write("sample4\tB\t400\t48.0\n")
        f.write("sample5\tC\t500\t49.0\n")
    
    return tmpdir, eigenvec_path, anno_path


def check_component_recursive(component, component_type):
    """Recursively check if a component type exists in the layout."""
    if component is None:
        return False
    
    # Check type
    type_name = type(component).__name__
    if type_name == component_type:
        return True
    
    # Check children
    if hasattr(component, 'children'):
        children = component.children
        if children is None:
            return False
        
        # Handle list of children
        if isinstance(children, list):
            for child in children:
                if check_component_recursive(child, component_type):
                    return True
        # Handle single child
        else:
            if check_component_recursive(children, component_type):
                return True
    
    return False


def test_plots_in_layout():
    """Test that plots (dcc.Graph components) are present in the layout."""
    print("Creating test data...")
    tmpdir, eigenvec_path, anno_path = create_test_data()
    
    try:
        # Parse arguments
        args = parse_args([
            '--eigenvec', eigenvec_path,
            '--annotation', anno_path,
            '--time', 'time',
            '--latitude', 'lat',
        ])
        
        print("Creating app...")
        app = create_app(args)
        
        # Check that app has layout
        assert app.layout is not None, "App layout is None!"
        print("✅ App has layout")
        
        # Check for dcc.Graph components
        has_graph = check_component_recursive(app.layout, 'Graph')
        
        if has_graph:
            print("✅ Found dcc.Graph component in layout - plots are present!")
        else:
            print("❌ No dcc.Graph components found - plots are missing!")
            return False
        
        # Count number of Graph components
        def count_graphs(component):
            """Count Graph components recursively."""
            if component is None:
                return 0
            
            count = 0
            if type(component).__name__ == 'Graph':
                count = 1
            
            if hasattr(component, 'children'):
                children = component.children
                if children is not None:
                    if isinstance(children, list):
                        for child in children:
                            count += count_graphs(child)
                    else:
                        count += count_graphs(children)
            
            return count
        
        num_graphs = count_graphs(app.layout)
        print(f"✅ Found {num_graphs} Graph component(s) in the layout")
        
        # Check for specific Graph IDs
        def find_graph_ids(component, ids=None):
            """Find all Graph component IDs."""
            if ids is None:
                ids = []
            
            if component is None:
                return ids
            
            if type(component).__name__ == 'Graph':
                if hasattr(component, 'id') and component.id:
                    ids.append(component.id)
            
            if hasattr(component, 'children'):
                children = component.children
                if children is not None:
                    if isinstance(children, list):
                        for child in children:
                            find_graph_ids(child, ids)
                    else:
                        find_graph_ids(children, ids)
            
            return ids
        
        graph_ids = find_graph_ids(app.layout)
        if graph_ids:
            print(f"✅ Graph IDs found: {', '.join(graph_ids)}")
        else:
            print("⚠️  No Graph components have IDs")
        
        print("\n✅ All checks passed! Plots are present in the app.")
        return True
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir)


if __name__ == '__main__':
    success = test_plots_in_layout()
    exit(0 if success else 1)
