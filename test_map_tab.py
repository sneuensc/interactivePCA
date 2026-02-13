"""Test that map plot is added to the app."""

import tempfile
import os
from interactive_pca import create_app
from interactive_pca.args import parse_args

tmpdir = tempfile.mkdtemp()
eigenvec_path = os.path.join(tmpdir, 'sample.eigenvec')
with open(eigenvec_path, 'w') as f:
    f.write('#IID\tPC1\tPC2\tPC3\n')
    for i in range(5):
        f.write(f'sample{i+1}\t{i*0.1:.4f}\t{i*0.2:.4f}\t{i*0.3:.4f}\n')

anno_path = os.path.join(tmpdir, 'sample.anno')
with open(anno_path, 'w') as f:
    f.write('id\tgroup\tLatitude\tLongitude\n')
    for i in range(5):
        f.write(f'sample{i+1}\tA\t{50+i*5:.2f}\t{10+i*5:.2f}\n')

args = parse_args(['--eigenvec', eigenvec_path, '--annotation', anno_path, '--latitude', 'Latitude', '--longitude', 'Longitude'])
app = create_app(args)

# Check for map plot
def find_component(component, name):
    if component is None:
        return False
    if type(component).__name__ == name:
        return True
    if hasattr(component, 'children'):
        children = component.children
        if children is None:
            return False
        if isinstance(children, list):
            for child in children:
                if find_component(child, name):
                    return True
        else:
            return find_component(children, name)
    return False

has_map = find_component(app.layout, 'Graph')
if has_map:
    print('✅ Map plot found in app!')
else:
    print('⚠️  No graphs found')

# Check for Tabs
def find_tabs(component):
    if component is None:
        return None
    if type(component).__name__ == 'Tabs':
        return component
    if hasattr(component, 'children'):
        children = component.children
        if children is None:
            return None
        if isinstance(children, list):
            for child in children:
                result = find_tabs(child)
                if result is not None:
                    return result
        else:
            return find_tabs(children)
    return None

tabs = find_tabs(app.layout)
if tabs:
    tab_labels = [tab.label for tab in tabs.children]
    print(f'✅ Tabs found: {", ".join(tab_labels)}')
    if 'Map' in tab_labels:
        print('✅ Map tab is present!')
    else:
        print('⚠️  Map tab not found')

import shutil
shutil.rmtree(tmpdir)
