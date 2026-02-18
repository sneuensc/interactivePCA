"""
Main Dash application factory for interactivePCA.
"""

import logging
import os
import dash
import dash_bootstrap_components as dbc
from dash import Input, Output

from .data_loader import load_eigenvec, load_annotation, merge_data
from .plots import set_dataframe
from .components import load_aesthetics_file, merge_aesthetics, get_init_aesthetics, register_hover_update_callbacks
from .layouts import create_layout
from .callbacks import register_all_callbacks


def create_app(args):
    """
    Create and configure the Dash application.
    
    Args:
        args: Parsed command-line arguments
    
    Returns:
        Configured Dash app instance
    """
    logging.info("Creating Dash application...")
    
    # Load data
    logging.info("Loading data files...")
    
    # Load eigenvectors (required)
    eigenvec, pcs, eigenvec_id = load_eigenvec(args.eigenvec, args.eigenvecID)
    
    # Load annotation
    annotation = None
    annotation_desc = None
    annotation_cols = {}
    
    if args.annotation:
        annotation, annotation_desc, annotation_cols = load_annotation(args.annotation, args)
    
    # Merge data
    df = merge_data(
        eigenvec,
        annotation,
        eigenvec_id_col='id',
        annotation_id_col=annotation_cols.get('id'),
        time_col=annotation_cols.get('time'),
        invert_time=args.time_invert
    )
    
    # Set global DataFrame in plots module
    set_dataframe(df)
    
    # Get annotation columns
    ANNOTATION_TIME = annotation_cols.get('time')
    ANNOTATION_LAT = annotation_cols.get('latitude')
    ANNOTATION_LONG = annotation_cols.get('longitude')
    
    # Initialize selected IDs
    if args.selectedID:
        if os.path.isfile(args.selectedID):
            with open(args.selectedID, 'r') as f:
                init_selected_ids = [line.rstrip('\n') for line in f]
        else:
            init_selected_ids = args.selectedID.split(";")
        
        # Filter to valid IDs
        valid_ids = set(df['id'].tolist())
        init_selected_ids = [sid for sid in init_selected_ids if sid in valid_ids]
    else:
        init_selected_ids = df['id'].tolist()
    
    logging.info(f"Selected {len(init_selected_ids)} of {len(df)} samples")
    
    # Initialize grouping options
    dropdown_group_list = ['none']
    if annotation_desc is not None:
        # Add columns suitable for grouping
        grouping_cols = annotation_desc.loc[
            annotation_desc['Dropdown'] == 'Yes',
            'Abbreviation'
        ].tolist()
        dropdown_group_list.extend(grouping_cols)

    # Include PCs as grouping options
    for pc in pcs:
        if pc not in dropdown_group_list:
            dropdown_group_list.append(pc)
    
    init_group = args.group if args.group and args.group in dropdown_group_list else dropdown_group_list[0]
    
    # Initialize continuous variable options
    dropdown_list_continuous = []
    init_continuous = ANNOTATION_TIME
    if annotation_desc is not None:
        dropdown_list_continuous = annotation_desc.loc[
            annotation_desc['Type'] == 'continuous',
            'Abbreviation'
        ].tolist()
        if dropdown_list_continuous and ANNOTATION_TIME not in dropdown_list_continuous:
            init_continuous = dropdown_list_continuous[0] if dropdown_list_continuous else None
    
    # Initialize aesthetics from parameters
    init_aesthetics = get_init_aesthetics(args, init_group, df)
    
    # Load aesthetics from file if provided (overrides parameter defaults)
    if args.aesthetics_file:
        file_aesthetics = load_aesthetics_file(args.aesthetics_file)
        if file_aesthetics and init_group in file_aesthetics:
            # Merge file aesthetics with parameter-based defaults
            init_aesthetics = merge_aesthetics(init_aesthetics, file_aesthetics[init_group])
    
    # Create Dash app
    app = dash.Dash(
        __name__,
        external_stylesheets=[dbc.themes.BOOTSTRAP],
        suppress_callback_exceptions=True
    )
    
    # Build layout
    layout_data = create_layout(
        args, df, pcs,
        annotation_desc, ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG,
        init_selected_ids, init_group, init_continuous, init_aesthetics,
        dropdown_group_list, dropdown_list_continuous
    )
    app.layout = layout_data['layout']
    tab_content_map = layout_data['tab_content_map']
    
    # Register tab switching callback using clientside callback for better performance
    app.clientside_callback(
        """
        function(active_tab) {
            // Hide all tab content divs
            const tabs = ['pca_tab', 'annotation_tab', 'help_tab'];
            tabs.forEach(function(tab) {
                const el = document.getElementById(tab + '_content');
                if (el) {
                    el.style.display = (tab === active_tab) ? 'block' : 'none';
                }
            });
            return window.dash_clientside.no_update;
        }
        """,
        Output('tabs-content', 'children'),
        Input('tabs', 'value')
    )
    
    # Register resizer functionality for draggable panes
    app.clientside_callback(
        """
        function() {
            // Initialize resizers on page load
            setTimeout(function() {
                const resizers = document.querySelectorAll('[id$="-resizer"]');
                
                resizers.forEach(function(resizer) {
                    if (resizer.dataset.initialized === 'true') return;
                    resizer.dataset.initialized = 'true';
                    
                    // Determine if this is a vertical or horizontal resizer
                    const isVertical = resizer.id.includes('vertical');
                    
                    resizer.addEventListener('mousedown', function(e) {
                        e.preventDefault();
                        const container = resizer.parentElement;
                        const children = Array.from(container.children);
                        const resizerIndex = children.indexOf(resizer);
                        
                        if (resizerIndex > 0 && resizerIndex < children.length - 1) {
                            const before = children[resizerIndex - 1];
                            const after = children[resizerIndex + 1];
                            
                            if (isVertical) {
                                // Handle vertical resizer (width-based)
                                let startX = e.clientX;
                                let startWidth = before.offsetWidth;
                                const containerWidth = container.offsetWidth;
                                const resizerWidth = 8;
                                
                                function handleMouseMove(moveEvent) {
                                    const deltaX = moveEvent.clientX - startX;
                                    const newWidth = startWidth + deltaX;
                                    const minSize = 10; // pixels minimum on each side
                                    const availableWidth = containerWidth - resizerWidth;
                                    // Constrain so both sides have at least minSize pixels
                                    const beforePx = Math.max(minSize, Math.min(availableWidth - minSize, newWidth));
                                    const beforePercent = (beforePx / availableWidth) * 100;
                                    const afterPercent = 100 - beforePercent;
                                    
                                    before.style.flex = `0 0 ${beforePercent}%`;
                                    after.style.flex = `0 0 ${afterPercent}%`;
                                }
                                
                                function handleMouseUp() {
                                    document.removeEventListener('mousemove', handleMouseMove);
                                    document.removeEventListener('mouseup', handleMouseUp);
                                }
                                
                                document.addEventListener('mousemove', handleMouseMove);
                                document.addEventListener('mouseup', handleMouseUp);
                            } else {
                                // Handle horizontal resizer (height-based)
                                let startY = e.clientY;
                                let startHeight = before.offsetHeight;
                                const containerHeight = container.offsetHeight;
                                const resizerHeight = 8;
                                
                                function handleMouseMove(moveEvent) {
                                    const deltaY = moveEvent.clientY - startY;
                                    const newHeight = startHeight + deltaY;
                                    const minSize = 10; // pixels minimum on each side
                                    const availableHeight = containerHeight - resizerHeight;
                                    // Constrain so both sides have at least minSize pixels
                                    const beforePx = Math.max(minSize, Math.min(availableHeight - minSize, newHeight));
                                    const beforePercent = (beforePx / availableHeight) * 100;
                                    const afterPercent = 100 - beforePercent;
                                    
                                    before.style.flex = `0 0 ${beforePercent}%`;
                                    after.style.flex = `0 0 ${afterPercent}%`;
                                }
                                
                                function handleMouseUp() {
                                    document.removeEventListener('mousemove', handleMouseMove);
                                    document.removeEventListener('mouseup', handleMouseUp);
                                }
                                
                                document.addEventListener('mousemove', handleMouseMove);
                                document.addEventListener('mouseup', handleMouseUp);
                            }
                        }
                    });
                });
            }, 100);
            
            return null;
        }
        """,
        Output('tabs-content', 'data-resizers-init', allow_duplicate=True),
        Input('tabs', 'value'),
        prevent_initial_call='initial_duplicate'
    )
    
    # Register hover update callbacks (factory pattern)
    register_hover_update_callbacks(app, df, annotation_desc)
    
    # Register all application callbacks
    register_all_callbacks(
        app, args, df, pcs, annotation_desc,
        ANNOTATION_TIME, ANNOTATION_LAT, ANNOTATION_LONG
    )
    
    logging.info("Dash application created successfully")
    return app
