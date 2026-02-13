"""
Quick test script to launch the app with sample data.
Run this and open http://localhost:8050 in your browser to see the plots.
"""

import tempfile
import os
from interactive_pca import create_app
from interactive_pca.args import parse_args

def create_sample_data():
    """Create sample test files with more realistic data."""
    tmpdir = tempfile.mkdtemp()
    print(f"Creating sample data in {tmpdir}")
    
    # Create test eigenvec file with 20 samples
    eigenvec_path = os.path.join(tmpdir, 'sample.eigenvec')
    with open(eigenvec_path, 'w') as f:
        f.write("#IID\tPC1\tPC2\tPC3\tPC4\tPC5\n")
        for i in range(20):
            pc1 = -2 + (i % 5) * 1.0 + (i // 5) * 0.1
            pc2 = -1.5 + (i // 4) * 0.8 + (i % 4) * 0.2
            pc3 = -1 + (i % 3) * 0.6
            pc4 = (i % 7) * 0.3 - 1
            pc5 = (i % 6) * 0.25 - 0.75
            f.write(f"sample{i+1:02d}\t{pc1:.4f}\t{pc2:.4f}\t{pc3:.4f}\t{pc4:.4f}\t{pc5:.4f}\n")
    
    # Create test annotation file with geographic coordinates
    anno_path = os.path.join(tmpdir, 'sample.anno')
    with open(anno_path, 'w') as f:
        f.write("id\tPopulation\tRegion\tLatitude\tLongitude\tTime_BP\n")
        populations = ['Pop_A', 'Pop_B', 'Pop_C', 'Pop_D']
        regions = ['Europe', 'Asia', 'Africa', 'Americas']
        
        for i in range(20):
            pop = populations[i % 4]
            region = regions[i % 4]
            # Create realistic geographic coordinates
            if region == 'Europe':
                lat = 50 + (i % 3) * 5
                lon = 10 + (i % 3) * 5
            elif region == 'Asia':
                lat = 40 + (i % 3) * 5
                lon = 100 + (i % 3) * 5
            elif region == 'Africa':
                lat = -5 + (i % 3) * 10
                lon = 20 + (i % 3) * 10
            else:  # Americas
                lat = 0 + (i % 3) * 10
                lon = -80 + (i % 3) * 10
            
            # Add time values (years before present) - spread across different periods
            time_bp = 500 + (i * 200) + ((i % 5) * 100)  # Range from ~500 to ~4500 BP
            
            f.write(f"sample{i+1:02d}\t{pop}\t{region}\t{lat:.2f}\t{lon:.2f}\t{time_bp}\n")
    
    print(f"✅ Created {eigenvec_path}")
    print(f"✅ Created {anno_path}")
    
    return tmpdir, eigenvec_path, anno_path


if __name__ == '__main__':
    tmpdir, eigenvec_path, anno_path = create_sample_data()
    
    print("\nParsing arguments...")
    args = parse_args([
        '--eigenvec', eigenvec_path,
        '--annotation', anno_path,
        '--time', 'Time_BP',
        '--latitude', 'Latitude',
        '--longitude', 'Longitude',
        '--group', 'Population',
    ])
    
    print("Creating app...")
    app = create_app(args)
    
    print("\n" + "="*60)
    print("🚀 Starting interactivePCA app")
    print("="*60)
    print("\n📊 Open your browser and navigate to:")
    print("    http://localhost:8050")
    print("\n✨ Features to check:")
    print("    • PCA Tab: PCA plot (LEFT) + Geographic map (RIGHT)")
    print("    •   - PCA plot: Interactive scatter with colored groups")
    print("    •   - Map: Shows where samples were collected")
    print("    •   - Change grouping variable (Population, Region)")
    print("    •   - Change PC axes (PC1, PC2, PC3, etc.)")
    print("    •   - Hover to see sample IDs")
    print("    • Annotation Tab: Data table of all annotations")
    print("    • Map Tab: Standalone map view (alternative view)")
    print("    • Help Tab: Command-line options reference")
    print("\n⏹️  Press Ctrl+C to stop the server")
    print("="*60 + "\n")
    
    try:
        app.run(debug=True, port=8050)
    except KeyboardInterrupt:
        print("\n\n✅ Server stopped")
        print(f"Temporary files remain at: {tmpdir}")
        print("You can delete them manually if needed.")
