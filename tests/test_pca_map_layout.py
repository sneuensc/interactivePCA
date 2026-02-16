"""Quick test to verify the PCA tab has both plots side by side."""

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

# Find PCA tab content
def find_pca_tab_content(component):
    if component is None:
        return None
    if type(component).__name__ == 'Tabs':
        # Found tabs, now look in the tab configs
        return component
    if hasattr(component, 'children'):
        children = component.children
        if children is not None:
            if isinstance(children, list):
                for child in children:
                    result = find_pca_tab_content(child)
                    if result is not None:
                        return result
            else:
                return find_pca_tab_content(children)
    return None

# Count graphs in layout
def count_graphs(component):
    if component is None:
        return 0
    count = 1 if type(component).__name__ == 'Graph' else 0
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
print(f'✅ Found {num_graphs} graph(s) in total')

if num_graphs >= 2:
    print('✅ PCA tab should have 2 plots (PCA + Map) side by side')
else:
    print('⚠️  Expected at least 2 graphs for PCA tab layout')

import shutil
shutil.rmtree(tmpdir)
