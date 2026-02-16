"""
Test the app module with sample data.
"""

import sys
import tempfile
import pandas as pd
from pathlib import Path


def create_sample_eigenvec():
    """Create a sample eigenvec file."""
    data = {
        'FID': ['pop1', 'pop1', 'pop2', 'pop2', 'pop3'],
        'IID': ['sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
        'PC1': [0.01, 0.02, -0.01, -0.02, 0.00],
        'PC2': [-0.02, -0.01, 0.02, 0.01, 0.00],
        'PC3': [0.003, 0.001, -0.002, -0.001, 0.000],
    }
    df = pd.DataFrame(data)
    return df


def create_sample_annotation():
    """Create a sample annotation file."""
    data = {
        'Genetic ID': ['sample1', 'sample2', 'sample3', 'sample4', 'sample5'],
        'Country': ['Germany', 'Germany', 'Sweden', 'Sweden', 'Norway'],
        'Population': ['Pop1', 'Pop1', 'Pop2', 'Pop2', 'Pop3'],
        'Date': [2020, 2021, 2019, 2020, 2022],
    }
    df = pd.DataFrame(data)
    return df


def test_app_creation():
    """Test that the app can be created with sample data."""
    print("Creating temporary test files...")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as tmpdir:
        tmppath = Path(tmpdir)
        
        # Write eigenvec file
        eigenvec_file = tmppath / "test.eigenvec"
        eigenvec_df = create_sample_eigenvec()
        eigenvec_df.to_csv(eigenvec_file, sep=' ', index=False)
        print(f"✅ Created {eigenvec_file}")
        
        # Write annotation file
        anno_file = tmppath / "test.anno"
        anno_df = create_sample_annotation()
        anno_df.to_csv(anno_file, sep='\t', index=False)
        print(f"✅ Created {anno_file}")
        
        # Test loading
        print("\nTesting data loading...")
        from interactive_pca import load_eigenvec, load_annotation
        
        eigenvec, pcs, id_col = load_eigenvec(str(eigenvec_file), 'IID')
        print(f"✅ Loaded eigenvec: {len(eigenvec)} samples, {len(pcs)} PCs")
        
        annotation, desc, cols = load_annotation(str(anno_file))
        print(f"✅ Loaded annotation: {len(annotation)} samples, {len(annotation.columns)} columns")
        
        # Test app creation
        print("\nTesting app creation...")
        from interactive_pca.app import create_app
        from interactive_pca.args import parse_args
        
        args = parse_args([
            '--eigenvec', str(eigenvec_file),
            '--eigenvecID', 'IID',
            '--annotation', str(anno_file),
            '--annotationID', 'Genetic ID',
        ])
        
        app = create_app(args)
        print(f"✅ App created successfully!")
        print(f"   App type: {type(app)}")
        print(f"   Has layout: {app.layout is not None}")
        
        return True


if __name__ == '__main__':
    try:
        test_app_creation()
        print("\n✅ All tests passed!")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
