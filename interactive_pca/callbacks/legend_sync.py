"""
Legend-visibility synchronisation across all active plots.

When the user clicks a legend item to hide/show a categorical group in
any plot, the same group is hidden/shown in every other active plot.

Implementation mirrors hover_sync: a single clientside callback listens to
`restyleData` from every plot.  The callback calls Plotly.restyle() directly
on the other divs (no Python round-trip).  A Set-based skip flag prevents the
programmatic restyle from re-entering the callback.
"""

from dash import Input, Output


def register_legend_sync_callbacks(app, show_map_plot=True, show_time_plot=True):
    plot_ids = ['pca-plot']
    if show_map_plot:
        plot_ids.append('pca-map-plot')
    if show_time_plot:
        plot_ids.append('time-histogram')

    if len(plot_ids) < 2:
        return

    all_ids_js  = '[' + ', '.join(f"'{p}'" for p in plot_ids) + ']'
    fn_args     = ', '.join(f'rd{i}' for i in range(len(plot_ids)))

    js = f"""
    function({fn_args}) {{
        var NO_UPDATE = window.dash_clientside.no_update;
        var ctx = dash_clientside.callback_context;
        var triggered = ctx.triggered && ctx.triggered[0];
        if (!triggered) return NO_UPDATE;

        var triggeredId = ctx.triggered_id ||
            (triggered ? triggered.prop_id.split('.')[0] : null);

        // Skip if this restyle was triggered by us (prevents infinite loop)
        if (!window._legendSyncSkip) window._legendSyncSkip = new Set();
        if (window._legendSyncSkip.has(triggeredId)) {{
            window._legendSyncSkip.delete(triggeredId);
            return NO_UPDATE;
        }}

        // Locate the restyleData that fired
        var allIds = {all_ids_js};
        var args   = [{fn_args}];
        var restyleData = null;
        for (var k = 0; k < allIds.length; k++) {{
            if (allIds[k] === triggeredId) {{ restyleData = args[k]; break; }}
        }}

        if (!restyleData || !restyleData[0] || !('visible' in restyleData[0])) {{
            return NO_UPDATE;
        }}

        var propDict      = restyleData[0];
        var traceIndices  = restyleData[1];
        var visArray      = propDict['visible'];

        // Helper: resolve the Plotly div for a component id
        function getDiv(id) {{
            var el = document.getElementById(id);
            if (!el) return null;
            if (el.data) return el;
            var inner = el.querySelector && el.querySelector('.js-plotly-plot');
            return (inner && inner.data) ? inner : null;
        }}

        var srcDiv = getDiv(triggeredId);
        if (!srcDiv) return NO_UPDATE;

        // Build name → visible map from the source figure's trace names
        var visMap = {{}};
        for (var i = 0; i < traceIndices.length; i++) {{
            var idx  = traceIndices[i];
            var name = srcDiv.data[idx] && srcDiv.data[idx].name;
            if (name && name !== '__hover_highlight__') {{
                visMap[name] = Array.isArray(visArray) ? visArray[i] : visArray;
            }}
        }}

        if (!Object.keys(visMap).length) return NO_UPDATE;

        // Apply to every other plot
        allIds.forEach(function(plotId) {{
            if (plotId === triggeredId) return;
            var div = getDiv(plotId);
            if (!div) return;

            var idxList = [], visList = [];
            for (var j = 0; j < div.data.length; j++) {{
                var tname = div.data[j].name;
                if (tname in visMap) {{
                    idxList.push(j);
                    visList.push(visMap[tname]);
                }}
            }}

            if (idxList.length) {{
                window._legendSyncSkip.add(plotId);
                Plotly.restyle(div, {{visible: visList}}, idxList);
            }}
        }});

        return NO_UPDATE;
    }}
    """

    inputs = [Input(pid, 'restyleData') for pid in plot_ids]

    app.clientside_callback(
        js,
        Output('hover-sync-dummy', 'data', allow_duplicate=True),
        *inputs,
        prevent_initial_call=True
    )
