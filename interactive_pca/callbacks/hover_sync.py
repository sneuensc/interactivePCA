"""
Hover synchronization callbacks for cross-plot point highlighting.

Strategy per plot type
----------------------
Scatter / Scattergl (PCA, time):
  - Reposition the __hover_highlight__ ring trace (visual circle).
  - Temporarily replace _fullData[foundTrace].hovertemplate with a minimal
    string, call Plotly.Fx.hover (which reads _fullData), then immediately
    restore.  Fx.hover renders the tooltip synchronously, so the restore
    happens after the DOM is already updated — the tooltip stays minimal.

Scattermap / Scattergeo (map):
  - Reposition the __hover_highlight__ ring trace.
  - Use Plotly.Fx.loneHover on the subplot's _hoverlayer SVG with pixel
    coordinates — mapGL.project([lon, lat]) for GL maps, the d3-geo
    projection for scattergeo. loneHover bypasses nearest-trace search.

Coordinates
-----------
Plotly ships numeric columns base64-packed as {dtype, bdata, _inputArray},
so trace.x[i] / trace.x.length are undefined on them. Always read point
coordinates through coordAt(), never by indexing the array directly.
"""

from dash import Input, Output


def register_hover_sync_callbacks(app, show_map_plot=True, show_time_plot=True):
    inputs = [Input('pca-plot', 'hoverData')]
    input_ids = ['pca-plot']

    if show_map_plot:
        inputs.append(Input('pca-map-plot', 'hoverData'))
        input_ids.append('pca-map-plot')
    if show_time_plot:
        inputs.append(Input('time-histogram', 'hoverData'))
        input_ids.append('time-histogram')

    all_plot_ids_js = '[' + ', '.join(f"'{pid}'" for pid in input_ids) + ']'
    fn_args = ', '.join(f'hoverData{i + 1}' for i in range(len(input_ids)))
    hoverdata_map_js = (
        '{' + ', '.join(f"'{pid}': hoverData{i + 1}" for i, pid in enumerate(input_ids)) + '}'
    )

    js_callback = f"""
    function({fn_args}) {{
        var ctx = dash_clientside.callback_context;
        var triggered = ctx.triggered && ctx.triggered[0];
        var triggeredId = ctx.triggered_id ||
            (triggered ? triggered.prop_id.split('.')[0] : null);
        var NO_UPDATE = window.dash_clientside.no_update;

        // Break feedback loop caused by our own simulated map hover
        if (window._hoverSyncSkip && window._hoverSyncSkip === triggeredId) {{
            window._hoverSyncSkip = null;
            return NO_UPDATE;
        }}

        var allPlotIds = {all_plot_ids_js};
        var hoverDataMap = {hoverdata_map_js};
        var hoverData = hoverDataMap[triggeredId];

        // ── helpers ──────────────────────────────────────────────────────────

        function getPlotlyDiv(plotId) {{
            var el = document.getElementById(plotId);
            if (!el) return null;
            if (el.data) return el;
            var inner = el.querySelector && el.querySelector('.js-plotly-plot');
            return (inner && inner.data) ? inner : null;
        }}

        function findHighlightIdx(plotDiv) {{
            for (var i = 0; i < plotDiv.data.length; i++) {{
                if (plotDiv.data[i].name === '__hover_highlight__') return i;
            }}
            return -1;
        }}

        // Numeric columns arrive base64-packed as {{dtype, bdata, _inputArray}}
        // (Plotly's binary transport), so `arr[i]` and `arr.length` are undefined
        // on them — the decoded values live in _inputArray.
        function coordAt(arr, i) {{
            if (!arr || i == null || i < 0) return null;
            var vals = Array.isArray(arr) ? arr
                     : (arr._inputArray ||
                        (typeof arr.length === 'number' ? arr : null));
            if (!vals || i >= vals.length) return null;
            var v = vals[i];
            if (v === undefined || v === null) return null;
            return (typeof v === 'number' && isNaN(v)) ? null : v;
        }}

        function isGeoPlot(plotDiv) {{
            return plotDiv.data.some(function(d) {{ return d.type === 'scattergeo'; }});
        }}

        function isMapPlot(plotDiv) {{
            return plotDiv.data.some(function(d) {{
                return d.type === 'scattermap' || d.type === 'scattermapbox'
                    || d.type === 'scattergeo';
            }});
        }}

        // Geo subplots project with d3-geo instead of a GL map object.
        function getGeoSubplot(plotDiv, trace) {{
            var key = (trace && trace.geo) || 'geo';
            var geo = plotDiv._fullLayout && plotDiv._fullLayout[key];
            return (geo && geo._subplot && geo._subplot.projection) ? geo : null;
        }}

        // Geo has no _hoverlayer of its own — fall back to the figure's.
        function getHoverContainer(plotDiv, trace) {{
            var fl = plotDiv._fullLayout;
            if (!fl) return null;
            var key = (trace && (trace.subplot || trace.geo))
                      || (isGeoPlot(plotDiv) ? 'geo' : 'map');
            var layer = (fl[key] && fl[key]._hoverlayer) || fl._hoverlayer;
            if (!layer) return null;
            return layer.node ? layer.node() : layer;
        }}

        function getMapGL(plotDiv) {{
            var layout = plotDiv._fullLayout;
            if (!layout) return null;
            var keys = Object.keys(layout);
            for (var i = 0; i < keys.length; i++) {{
                var k = keys[i];
                if (/^(map|mapbox)\d*$/.test(k) && layout[k] && layout[k]._map) {{
                    return layout[k]._map;
                }}
            }}
            return null;
        }}

        function getMapKey(plotDiv, trace) {{
            return (trace && trace.subplot) || 'map';
        }}

        // ── clear ────────────────────────────────────────────────────────────

        function clearHighlight(plotId) {{
            var plotDiv = getPlotlyDiv(plotId);
            if (!plotDiv) return;
            var hlIdx = findHighlightIdx(plotDiv);
            if (hlIdx === -1) return;

            if (isMapPlot(plotDiv)) {{
                Plotly.restyle(plotDiv, {{lat: [[]], lon: [[]]}}, [hlIdx]);
                try {{
                    var mapTrace = plotDiv.data.find(function(d) {{
                        return d.type === 'scattermap' || d.type === 'scattermapbox'
                            || d.type === 'scattergeo';
                    }});
                    var container = getHoverContainer(plotDiv, mapTrace);
                    if (container && Plotly.Fx.loneUnhover) {{
                        Plotly.Fx.loneUnhover(container);
                    }} else if (!isGeoPlot(plotDiv)) {{
                        window._hoverSyncSkip = plotId;
                        Plotly.Fx.hover(plotDiv, {{clientX: -9999, clientY: -9999}},
                                        getMapKey(plotDiv, mapTrace));
                    }}
                }} catch(e) {{}}
            }} else {{
                var clearData = {{x: [[]], y: [[]], hovertemplate: '<extra></extra>'}};
                if (plotDiv.data[hlIdx].z !== undefined) clearData.z = [[]];
                Plotly.restyle(plotDiv, clearData, [hlIdx]);
                try {{ Plotly.Fx.hover(plotDiv, []); }} catch(e) {{}}
            }}
        }}

        // ── update ───────────────────────────────────────────────────────────

        function updateHighlight(plotId, hoveredId) {{
            var plotDiv = getPlotlyDiv(plotId);
            if (!plotDiv) return;

            var hlIdx = findHighlightIdx(plotDiv);
            if (hlIdx === -1) return;

            // find the matching trace + point
            var data = plotDiv.data;
            var foundTrace = -1, foundPoint = -1;
            for (var ti = 0; ti < data.length; ti++) {{
                if (ti === hlIdx) continue;
                var customdata = data[ti].customdata;
                if (!customdata || !customdata.length) continue;
                for (var pi = 0; pi < customdata.length; pi++) {{
                    var cd = customdata[pi];
                    var cdStr = Array.isArray(cd) ? String(cd[0]) : String(cd);
                    if (cdStr === hoveredId) {{ foundTrace = ti; foundPoint = pi; break; }}
                }}
                if (foundTrace !== -1) break;
            }}

            if (foundTrace === -1) {{ clearHighlight(plotId); return; }}

            var trace = data[foundTrace];
            // Synced plots always show minimal info regardless of hover-detailed
            var minTpl = '<b>ID:</b> ' + hoveredId + '<extra></extra>';

            // ── MAP ──────────────────────────────────────────────────────────
            if (isMapPlot(plotDiv)) {{
                var lat = coordAt(trace.lat, foundPoint);
                var lon = coordAt(trace.lon, foundPoint);
                if ((lat == null || lon == null) && plotDiv._fullData &&
                        plotDiv._fullData[foundTrace]) {{
                    var fd = plotDiv._fullData[foundTrace];
                    if (lat == null) lat = coordAt(fd.lat, foundPoint);
                    if (lon == null) lon = coordAt(fd.lon, foundPoint);
                }}
                if (lat == null || lon == null) {{ clearHighlight(plotId); return; }}

                // Visual ring
                Plotly.restyle(plotDiv, {{lat: [[lat]], lon: [[lon]]}}, [hlIdx]);

                // Tooltip via loneHover on the subplot's SVG hover layer.
                try {{
                    var px  = null;
                    var geo = getGeoSubplot(plotDiv, trace);
                    if (geo) {{
                        // d3-geo returns null for points clipped by the projection.
                        var p = geo._subplot.projection([lon, lat]);
                        if (p) px = {{x: p[0], y: p[1]}};
                    }} else {{
                        var mapGL = getMapGL(plotDiv);
                        if (mapGL && mapGL.project) px = mapGL.project([lon, lat]);
                    }}
                    if (px) {{
                        var container = getHoverContainer(plotDiv, trace);
                        if (container && Plotly.Fx.loneHover) {{
                            Plotly.Fx.loneHover({{
                                trace: trace,
                                x: px.x, y: px.y,
                                text: '<b>ID:</b> ' + hoveredId,
                                color: 'white',
                                borderColor: '#aaa',
                                fontFamily: 'sans-serif',
                                fontSize: 13,
                                fontColor: '#333',
                                idealAlign: px.x < plotDiv.clientWidth / 2 ? 'right' : 'left'
                            }}, {{
                                container: container,
                                gd: plotDiv
                            }});
                        }} else if (!geo) {{
                            // fallback: Fx.hover with screen coords (GL maps only)
                            var canvas = getMapGL(plotDiv).getCanvas();
                            var rect   = canvas.getBoundingClientRect();
                            window._hoverSyncSkip = plotId;
                            Plotly.Fx.hover(plotDiv,
                                {{clientX: rect.left + px.x, clientY: rect.top + px.y}},
                                getMapKey(plotDiv, trace));
                        }}
                    }}
                }} catch(e) {{}}

            // ── SCATTER / SCATTERGL ──────────────────────────────────────────
            }} else {{
                var x = coordAt(trace.x, foundPoint);
                var y = coordAt(trace.y, foundPoint);
                var z = coordAt(trace.z, foundPoint);
                if (x == null && plotDiv._fullData && plotDiv._fullData[foundTrace]) {{
                    var fdc = plotDiv._fullData[foundTrace];
                    x = coordAt(fdc.x, foundPoint);
                    if (y == null) y = coordAt(fdc.y, foundPoint);
                    if (z == null) z = coordAt(fdc.z, foundPoint);
                }}

                // Reposition visual ring
                if (x != null) {{
                    var rs = {{x: [[x]], y: [[y != null ? y : 0]]}};
                    if (z != null) rs.z = [[z]];
                    Plotly.restyle(plotDiv, rs, [hlIdx]);
                }}

                // Temporarily override hovertemplate in _fullData so Fx.hover
                // shows the minimal tooltip instead of the (possibly detailed) one.
                // Fx.hover renders synchronously, so restoring after the call is safe.
                var fullTrace = plotDiv._fullData && plotDiv._fullData[foundTrace];
                var origTpl   = fullTrace ? fullTrace.hovertemplate : undefined;
                if (fullTrace) fullTrace.hovertemplate = minTpl;

                try {{
                    Plotly.Fx.hover(plotDiv, [{{curveNumber: foundTrace, pointNumber: foundPoint}}]);
                }} catch(e) {{}}

                if (fullTrace && origTpl !== undefined) fullTrace.hovertemplate = origTpl;
            }}
        }}

        // ── expose helpers globally + attach table hover listeners (once) ──────
        // `getRowId` on pca-annotation-table ensures each AG Grid row DOM element
        // carries row-id="<sample_id>", so plain mouseover can resolve the ID.
        window._hvUpdate = function(id) {{
            if (id) {{
                allPlotIds.forEach(function(pid) {{ updateHighlight(pid, id); }});
            }} else {{
                allPlotIds.forEach(function(pid) {{ clearHighlight(pid); }});
            }}
        }};
        (function() {{
            var tbl = document.getElementById('pca-annotation-table');
            if (!tbl || tbl._hvHooked) return;
            tbl._hvHooked = true;
            tbl.addEventListener('mouseover', function(e) {{
                var row = e.target.closest('.ag-row[row-id]');
                if (!row) return;
                var rowId = row.getAttribute('row-id');
                if (rowId && rowId !== 'undefined') window._hvUpdate(rowId);
            }});
            tbl.addEventListener('mouseleave', function() {{ window._hvUpdate(null); }});
        }})();

        // ── main ─────────────────────────────────────────────────────────────

        if (!hoverData || !hoverData.points || !hoverData.points.length) {{
            allPlotIds.forEach(function(plotId) {{
                if (plotId !== triggeredId) clearHighlight(plotId);
            }});
            return NO_UPDATE;
        }}

        var pt = hoverData.points[0];
        var cd = pt.customdata;
        var hoveredId = Array.isArray(cd) ? String(cd[0]) : String(cd);

        if (!hoveredId || hoveredId === 'undefined' || hoveredId === 'null') {{
            return NO_UPDATE;
        }}

        allPlotIds.forEach(function(plotId) {{
            if (plotId !== triggeredId) updateHighlight(plotId, hoveredId);
        }});

        return NO_UPDATE;
    }}
    """

    app.clientside_callback(
        js_callback,
        Output('hover-sync-dummy', 'data'),
        *inputs,
        prevent_initial_call=True
    )
