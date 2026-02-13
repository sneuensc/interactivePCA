# Map Tab Added Successfully

## Summary

The geographical map visualization has been added to the interactivePCA app.

## Features

### Map Tab
- **Geographic scatter plot** showing the location of each sample
- **Group by variable**: Change colors/sizes by Population, Region, or other categorical variables
- **Continuous color scale**: For numeric variables like time
- **Interactive features**:
  - Hover to see sample ID and coordinates
  - Zoom and pan
  - Click legend items to toggle groups
- **Professional map styling**:
  - Land masses, oceans, country borders
  - Natural Earth projection
  - Color-coded regions

## New Tabs

The app now includes 4 tabs:

1. **PCA** - Principal component analysis plots
   - 2D/3D scatter plots
   - Group by any categorical variable
   - Change PC axes

2. **Annotation** - Data table of metadata
   - Sortable and filterable columns
   - Shows all annotation information

3. **Map** - Geographic distribution *(NEW)*
   - Shows where samples were collected
   - Colors by grouping variable
   - Interactive map with zoom/pan

4. **Help** - Command-line reference
   - Full help text

## Requirements

The Map tab requires latitude and longitude columns in your annotation file:

```bash
interactive-pca \
  --eigenvec data/pca.eigenvec \
  --annotation data/metadata.csv \
  --latitude Latitude \
  --longitude Longitude
```

## Code Changes

### New File: `plots.py` function
```python
create_geographical_map(df, group='none', aesthetics_group=None, lat_col=None, lon_col=None)
```

### Updated: `app.py`
- Added Map tab creation in `create_layout()`
- Map tab includes grouping dropdown and Scattergeo figure
- Only shown if latitude/longitude columns are available

## Testing

Test the map with sample data:
```bash
python run_sample_app.py
```

Open http://localhost:8050 and click the **Map** tab to see the geographic visualization.

## Example Output

The sample data creates samples in different regions:
- **Europe**: 50-65°N, 10-20°E
- **Asia**: 40-50°N, 100-110°E
- **Africa**: -5-15°S, 20-40°E
- **Americas**: 0-20°N, -90-70°W

Each region has different colors (Pop_A, Pop_B, etc.) for easy identification.
