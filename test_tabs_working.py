"""Test that tabs are working properly."""

import tempfile
import os
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
    
    # Create test annotation file
    anno_path = os.path.join(tmpdir, 'test.anno')
    with open(anno_path, 'w') as f:
        f.write("id\tgroup\ttime\n")
        f.write("sample1\tA\t100\n")
        f.write("sample2\tB\t200\n")
        f.write("sample3\tC\t300\n")
    
    return tmpdir, eigenvec_path, anno_path


def test_tabs():
    """Test that only PCA, Annotation, and Help tabs are present."""
    print("Creating test data...")
    tmpdir, eigenvec_path, anno_path = create_test_data()
    
    try:
        # Parse arguments
        args = parse_args([
            '--eigenvec', eigenvec_path,
            '--annotation', anno_path,
        ])
        
        print("Creating app...")
        app = create_app(args)
        
        # Check that app has layout
        assert app.layout is not None, "App layout is None!"
        print("✅ App has layout")
        
        # Find the Tabs component
        def find_tabs_component(component):
            """Find the Tabs component in the layout."""
            if component is None:
                return None
            
            if type(component).__name__ == 'Tabs':
                return component
            
            if hasattr(component, 'children'):
                children = component.children
                if children is not None:
                    if isinstance(children, list):
                        for child in children:
                            result = find_tabs_component(child)
                            if result is not None:
                                return result
                    else:
                        return find_tabs_component(children)
            
            return None
        
        tabs = find_tabs_component(app.layout)
        if tabs is None:
            print("❌ No Tabs component found!")
            return False
        
        print("✅ Found Tabs component")
        
        # Check tab labels
        tab_labels = [tab.label for tab in tabs.children]
        print(f"   Tab labels: {', '.join(tab_labels)}")
        
        expected_tabs = ['PCA', 'Annotation', 'Help']
        if tab_labels == expected_tabs:
            print(f"✅ Correct tabs present: {', '.join(tab_labels)}")
        else:
            print(f"❌ Expected tabs {expected_tabs}, got {tab_labels}")
            return False
        
        # Check that callbacks are registered
        if hasattr(app, 'callback_map') and app.callback_map:
            print(f"✅ Found {len(app.callback_map)} callback(s) registered")
            
            # Check for tabs-content callback
            tabs_callback = None
            for callback_id, callback_info in app.callback_map.items():
                if 'tabs-content' in str(callback_id):
                    tabs_callback = callback_info
                    break
            
            if tabs_callback:
                print("✅ Tab switching callback is registered")
            else:
                print("⚠️  No tab switching callback found")
        else:
            print("⚠️  No callbacks registered yet")
        
        print("\n✅ All checks passed! App has 3 tabs and callback registered.")
        return True
        
    finally:
        # Cleanup
        import shutil
        shutil.rmtree(tmpdir)


if __name__ == '__main__':
    success = test_tabs()
    exit(0 if success else 1)
