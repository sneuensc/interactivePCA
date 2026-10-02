"""
Snapshot export — clientside callback that builds a self-contained HTML file
directly in the browser from Plotly's live in-memory figure state.

The exported file needs no Dash server to be useful: Plotly.js and AG Grid
are pulled from a CDN (exactly like the live app pulls dash-renderer/React
from its own server — "self-contained" here means one file holding all the
DATA and CUSTOM LOGIC, not that every library is inlined), and everything
else — hover sync, legend-click sync, cross-plot lasso/box-select syncing,
a sortable/filterable table, an optional time-slice slider — is plain
JavaScript operating on the embedded data, ported from the equivalent
clientside logic in hover_sync.py / legend_sync.py, or (for selection
syncing and the time slider) newly written to mirror what their Python
counterparts in selection.py do.

Deliberately NOT reproduced: the live aesthetics editor (recoloring groups)
and the free-form pandas query box — unsafe/impractical to eval arbitrary
pandas syntax in a browser. AG Grid's own per-column sort/filter UI covers
the same underlying need (narrowing down rows) without that risk, and the
exported colors are simply whatever was on screen at export time.
"""

from dash import Input, Output, State

# Pinned to a version compatible with the installed dash-ag-grid's AG Grid
# core, so the exported table's look/behaviour matches the live app's.
_AG_GRID_CDN = 'https://cdn.jsdelivr.net/npm/ag-grid-community@36.2.0/dist/ag-grid-community.min.js'
_PLOTLY_CDN = 'https://cdn.plot.ly/plotly-2.35.2.min.js'


def register_snapshot_callback(app, show_time_plot=True):
    states = [
        State('pca-annotation-table', 'rowData'),
        State('pca-annotation-table', 'columnDefs'),
    ]
    if show_time_plot:
        states.append(State('time-variable', 'value'))

    app.clientside_callback(
        """
        function(n_clicks, rowData, colDefs""" + (', timeVar' if show_time_plot else '') + """) {
            if (!n_clicks) return window.dash_clientside.no_update;
            """ + ('' if show_time_plot else 'var timeVar = null;') + """

            // ── read current pane sizes from the live DOM ────────────────
            function px(id, prop) {
                var el = document.getElementById(id);
                return el ? Math.round(el.getBoundingClientRect()[prop]) : 0;
            }
            var leftW  = px('pca-left-pane',  'width');
            var rightW = px('pca-right-pane', 'width');
            var pcaH   = px('pca-plot',        'height');
            var timeH  = px('time-histogram',  'height');
            var mapH   = px('pca-map-plot',    'height');
            var tblH   = px('pca-annotation-table', 'height');
            // Pane splits are captured as a PERCENTAGE of the two measured
            // panes, not a fixed pixel size for both — a browser window
            // hardly ever matches the exact height/width the snapshot was
            // taken at, and two fixed-pixel panes stacked in a flex column
            // don't grow to fill the difference, leaving blank space (or
            // overflow) below/beside them. Only one side of each split is
            // ever fixed (as a %); the other always grows to absorb
            // whatever's left (flex:1 1 auto), so the pair always fills
            // its container exactly, at any window size.
            function splitPct(a, b, fallback) {
                return (a && b) ? (a / (a + b) * 100).toFixed(2) + '%' : fallback;
            }
            var colCss = '#left-col{flex:0 0 '  + splitPct(leftW, rightW, '50%') + '}' +
                         '#right-col{flex:1 1 auto}';
            var pcaFlex  = 'flex:0 0 ' + splitPct(pcaH, timeH, '60%');
            var timeFlex = 'flex:1 1 auto';
            var mapFlex  = 'flex:0 0 ' + splitPct(mapH, tblH, '60%');

            // ── capture figures ─────────────────────────────────────────
            // customdata (sample id per point) is kept on every trace —
            // it's what lets the exported page match points across plots
            // and the table, exactly like the live app's selection-store.
            var PLOT_IDS = ['pca-plot', 'pca-map-plot', 'time-histogram'];
            var panels = {};
            var figuresJson = {};  // compId -> {data, layout}, for the wiring script below
            var first  = true;

            PLOT_IDS.forEach(function(compId) {
                var wrapper = document.getElementById(compId);
                if (!wrapper) return;
                var el = wrapper.querySelector('.js-plotly-plot') || wrapper;
                if (!el || !el.data) return;

                var data = el.data.filter(function(t) {
                    return t.name !== '__hover_highlight__';
                });
                var layout = Object.assign({}, el.layout || {});
                delete layout.uirevision;
                layout.autosize = true;
                delete layout.width;
                delete layout.height;

                var cfg = {responsive:true, scrollZoom:true, displayModeBar:true};
                var plotlyTag = first
                    ? '<script src="PLOTLY_CDN_PLACEHOLDER"><\\/script>\\n'
                    : '';
                first = false;

                var id = 'p_' + compId.replace(/-/g,'_');
                figuresJson[compId] = {id: id, data: data, layout: layout};
                panels[compId] =
                    plotlyTag +
                    '<div id="' + id + '" style="width:100%;height:100%"><\\/div>\\n' +
                    '<script>Plotly.newPlot(' +
                        JSON.stringify(id) + ',' +
                        JSON.stringify(data) + ',' +
                        JSON.stringify(layout) + ',' +
                        JSON.stringify(cfg) +
                    ')<\\/script>';
            });

            // ── table columns (AG Grid's own columnDefs shape — dash-ag-grid
            // is a thin wrapper, so these pass straight through) ───────────
            function filterCols(cols) {
                return (cols || []).filter(function(c) {
                    return c.field && c.field !== 'Selected' && !c.hide;
                });
            }
            var vcols = filterCols(colDefs);
            var rows  = rowData || [];
            var allIds = rows.map(function(r) { return String(r.id); });

            // id -> time value, for the optional time-slice slider — only
            // possible when the time column is among the ones shown in the
            // table (rowData only carries the user's currently-selected
            // annotation columns, same as the live table).
            var idToTime = null;
            if (timeVar && rows.length && (timeVar in rows[0])) {
                idToTime = {};
                rows.forEach(function(r) {
                    var v = r[timeVar];
                    if (v !== null && v !== undefined && v !== '') {
                        idToTime[String(r.id)] = parseFloat(v);
                    }
                });
            }

            // ── assemble HTML ────────────────────────────────────────────
            var ts = new Date().toISOString().slice(0,19).replace(/:/g,'-');
            var html = [
                '<!DOCTYPE html><html lang="en"><head>',
                '<meta charset="utf-8"/>',
                '<meta name="viewport" content="width=device-width,initial-scale=1"/>',
                '<title>interactivePCA snapshot ' + ts + '<\\/title>',
                '<script src="AG_GRID_CDN_PLACEHOLDER"><\\/script>',
                '<style>',
                '*{box-sizing:border-box;margin:0;padding:0}',
                'html,body{height:100%;font-family:sans-serif;background:#fff;overflow:hidden}',
                'header{height:38px;padding:0 14px;background:#f8f9fa;',
                '  border-bottom:1px solid #dee2e6;display:flex;align-items:center;gap:12px}',
                'header h1{font-size:14px;font-weight:600}',
                'header span{font-size:11px;color:#888}',
                '#sel-counter{font-size:12px;font-weight:600;color:#333;margin-left:auto}',
                '#reset-btn{padding:4px 10px;border:1px solid #ccc;border-radius:4px;',
                '  background:#fff;cursor:pointer;font-size:12px}',
                '#reset-btn:hover{background:#f0f0f0}',
                '#workspace{display:flex;height:calc(100vh - 38px);overflow:hidden}',
                colCss + '#left-col,#right-col{min-width:0;display:flex;flex-direction:column;overflow:hidden}',
                '#pca-wrap{'  + pcaFlex  + ';min-height:0}',
                '#time-wrap{' + timeFlex + ';min-height:0;display:flex;flex-direction:column}',
                '#time-plot-area{flex:1 1 auto;min-height:0}',
                '#map-wrap{'  + mapFlex  + ';min-height:0}',
                '#tbl-wrap{flex:1 1 auto;min-height:0;overflow:hidden}',
                '#ag-table{height:100%;width:100%}',
                '.rv{width:6px;cursor:col-resize;background:#ccc;flex:0 0 6px}',
                '.rh{height:6px;cursor:row-resize;background:#ccc;flex:0 0 6px}',
                '.rv:hover,.rh:hover{background:#888}',
                '#time-slice{flex:0 0 auto;padding:6px 14px;border-top:1px solid #eee;',
                '  display:flex;align-items:center;gap:10px;font-size:12px;color:#333}',
                '#time-slice .rng{position:relative;flex:1 1 auto;height:18px}',
                '#time-slice input[type=range]{position:absolute;left:0;right:0;top:0;',
                '  width:100%;margin:0;pointer-events:none;-webkit-appearance:none;background:transparent}',
                '#time-slice input[type=range]::-webkit-slider-thumb{pointer-events:auto;',
                '  -webkit-appearance:none;width:14px;height:14px;border-radius:50%;',
                '  background:#0066cc;cursor:pointer;margin-top:2px}',
                '#time-slice input[type=range]::-moz-range-thumb{pointer-events:auto;',
                '  width:14px;height:14px;border-radius:50%;background:#0066cc;cursor:pointer;border:none}',
                '#time-slice input[type=range]::-webkit-slider-runnable-track{height:4px;background:#ddd}',
                '<\\/style>',
                '<\\/head><body>',
                '<header><h1>interactivePCA snapshot<\\/h1>',
                '<span>' + ts.replace('T',' ') + '<\\/span>',
                '<span id="sel-counter"><\\/span>',
                '<button id="reset-btn">Reset selection<\\/button>',
                '<\\/header>',
                '<div id="workspace">',
                '  <div id="left-col">',
                '    <div id="pca-wrap">'  + (panels['pca-plot']      || '') + '<\\/div>',
                '    <div class="rh" id="hl"><\\/div>',
                '    <div id="time-wrap">',
                '      <div id="time-plot-area">' + (panels['time-histogram'] || '') + '<\\/div>',
                (idToTime ? '      <div id="time-slice"><\\/div>' : ''),
                '    <\\/div>',
                '  <\\/div>',
                '  <div class="rv" id="vr"><\\/div>',
                '  <div id="right-col">',
                '    <div id="map-wrap">'  + (panels['pca-map-plot']  || '') + '<\\/div>',
                '    <div class="rh" id="hr"><\\/div>',
                '    <div id="tbl-wrap"><div id="ag-table"><\\/div><\\/div>',
                '  <\\/div>',
                '<\\/div>',
                '<script>',
                'window.__SNAPSHOT_DATA__ = ' + JSON.stringify({
                    allIds: allIds,
                    rows: rows,
                    columnDefs: vcols,
                    idToTime: idToTime,
                    plotIds: Object.keys(figuresJson),
                }) + ';',
                '<\\/script>',
                '<script>' + SNAPSHOT_RUNTIME_JS + '<\\/script>',
                '<\\/body><\\/html>'
            ].join('\\n');

            var blob = new Blob([html], {type:'text/html'});
            var url  = URL.createObjectURL(blob);
            var a    = Object.assign(document.createElement('a'),
                           {href:url, download:'interactivePCA_'+ts+'.html'});
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
            setTimeout(function(){URL.revokeObjectURL(url);}, 2000);
            return window.dash_clientside.no_update;
        }
        """.replace('PLOTLY_CDN_PLACEHOLDER', _PLOTLY_CDN)
           .replace('AG_GRID_CDN_PLACEHOLDER', _AG_GRID_CDN)
           .replace('SNAPSHOT_RUNTIME_JS', _runtime_js()),
        Output('download-snapshot', 'data'),
        Input('export-snapshot-btn', 'n_clicks'),
        *states,
        prevent_initial_call=True,
    )


def _runtime_js():
    """The JS that ships INSIDE the exported HTML file (not the callback that
    builds it) — hover sync, legend-click sync, cross-plot selection syncing,
    the table, and the optional time-slice slider. Pure functions of
    window.__SNAPSHOT_DATA__ and whatever Plotly figures got embedded above
    it, so it's identical on every export regardless of what was plotted.

    Returned as a JS STRING LITERAL (quotes included) — the outer callback
    template splices this in as the right-hand side of a `+` concatenation
    (building the exported page's own <script> tag at export time), so this
    needs to evaluate to the runtime source as text, not execute it here.
    json.dumps on the raw source gives exactly that: a properly quoted and
    escaped JS/JSON string literal.
    """
    import json
    return json.dumps(_RUNTIME_JS_SOURCE)


_RUNTIME_JS_SOURCE = r"""
(function() {
    var DATA = window.__SNAPSHOT_DATA__;
    var PLOT_IDS = DATA.plotIds;

    function getDiv(id) {
        var el = document.getElementById(id);
        if (!el) return null;
        if (el.data) return el;
        var inner = el.querySelector && el.querySelector('.js-plotly-plot');
        return (inner && inner.data) ? inner : null;
    }

    // ══════════════════════════════════════════════════════════════════
    // Selection syncing — lasso/box-select on any plot highlights the
    // same points everywhere and dims non-matching table rows. Mirrors
    // selection-store in the live app: null/undefined means "everything
    // selected" (the app-wide sentinel for "no filter").
    // ══════════════════════════════════════════════════════════════════
    var currentSelection = null;

    function idOf(customdataEntry) {
        var v = Array.isArray(customdataEntry) ? customdataEntry[0] : customdataEntry;
        return (v === null || v === undefined) ? null : String(v);
    }

    function applySelection(ids) {
        currentSelection = ids;
        var selSet = ids ? new Set(ids) : null;

        PLOT_IDS.forEach(function(pid) {
            var div = getDiv(pid);
            if (!div) return;
            div.data.forEach(function(trace, idx) {
                var cd = trace.customdata;
                if (!cd || !cd.length) return;
                if (!selSet) {
                    Plotly.restyle(div, {selectedpoints: [null]}, [idx]);
                } else {
                    var mask = [];
                    for (var i = 0; i < cd.length; i++) {
                        if (selSet.has(idOf(cd[i]))) mask.push(i);
                    }
                    Plotly.restyle(div, {selectedpoints: [mask]}, [idx]);
                }
            });
        });

        if (window._gridApi) window._gridApi.redrawRows();
        updateCounter();
    }

    function updateCounter() {
        var el = document.getElementById('sel-counter');
        if (!el) return;
        var total = DATA.allIds.length;
        var n = currentSelection ? currentSelection.length : total;
        el.textContent = 'Selected: ' + n + ' / ' + total;
    }

    function wireSelectionEvents() {
        PLOT_IDS.forEach(function(pid) {
            var div = getDiv(pid);
            if (!div) return;
            div.on('plotly_selected', function(evt) {
                var pts = (evt && evt.points) || [];
                var ids = pts.map(function(pt) { return idOf(pt.customdata); })
                             .filter(function(id) { return id; });
                applySelection(ids);
            });
            div.on('plotly_deselect', function() { applySelection(null); });
        });
    }

    var resetBtn = document.getElementById('reset-btn');
    if (resetBtn) {
        resetBtn.addEventListener('click', function() {
            applySelection(null);
            resetTimeSlice();
        });
    }

    // ══════════════════════════════════════════════════════════════════
    // Hover sync — ported as-is from the live app's hover_sync.py: it was
    // already pure DOM/Plotly logic with no server round-trip.
    // ══════════════════════════════════════════════════════════════════
    function wireHoverSync() {
        if (PLOT_IDS.length < 2) return;

        function findHighlightIdx(plotDiv) {
            for (var i = 0; i < plotDiv.data.length; i++) {
                if (plotDiv.data[i].name === '__hover_highlight__') return i;
            }
            return -1;
        }
        function coordAt(arr, i) {
            if (!arr || i == null || i < 0) return null;
            var vals = Array.isArray(arr) ? arr
                     : (arr._inputArray || (typeof arr.length === 'number' ? arr : null));
            if (!vals || i >= vals.length) return null;
            var v = vals[i];
            if (v === undefined || v === null) return null;
            return (typeof v === 'number' && isNaN(v)) ? null : v;
        }
        function isMapPlot(plotDiv) {
            return plotDiv.data.some(function(d) {
                return d.type === 'scattermap' || d.type === 'scattermapbox' || d.type === 'scattergeo';
            });
        }
        function clearHighlight(plotId) {
            var plotDiv = getDiv(plotId);
            if (!plotDiv) return;
            var hlIdx = findHighlightIdx(plotDiv);
            if (hlIdx === -1) return;
            if (isMapPlot(plotDiv)) {
                Plotly.restyle(plotDiv, {lat: [[]], lon: [[]]}, [hlIdx]);
            } else {
                var clearData = {x: [[]], y: [[]], hovertemplate: '<extra></extra>'};
                if (plotDiv.data[hlIdx].z !== undefined) clearData.z = [[]];
                Plotly.restyle(plotDiv, clearData, [hlIdx]);
            }
            try { Plotly.Fx.hover(plotDiv, []); } catch (e) {}
        }
        function updateHighlight(plotId, hoveredId) {
            var plotDiv = getDiv(plotId);
            if (!plotDiv) return;
            var hlIdx = findHighlightIdx(plotDiv);
            if (hlIdx === -1) return;

            var data = plotDiv.data;
            var foundTrace = -1, foundPoint = -1;
            for (var ti = 0; ti < data.length; ti++) {
                if (ti === hlIdx) continue;
                var customdata = data[ti].customdata;
                if (!customdata || !customdata.length) continue;
                for (var pi = 0; pi < customdata.length; pi++) {
                    if (idOf(customdata[pi]) === hoveredId) { foundTrace = ti; foundPoint = pi; break; }
                }
                if (foundTrace !== -1) break;
            }
            if (foundTrace === -1) { clearHighlight(plotId); return; }

            var trace = data[foundTrace];
            var minTpl = '<b>ID:</b> ' + hoveredId + '<extra></extra>';

            if (isMapPlot(plotDiv)) {
                var lat = coordAt(trace.lat, foundPoint);
                var lon = coordAt(trace.lon, foundPoint);
                if (lat == null || lon == null) { clearHighlight(plotId); return; }
                Plotly.restyle(plotDiv, {lat: [[lat]], lon: [[lon]]}, [hlIdx]);
                try {
                    Plotly.Fx.hover(plotDiv, [{curveNumber: foundTrace, pointNumber: foundPoint}]);
                } catch (e) {}
            } else {
                var x = coordAt(trace.x, foundPoint);
                var y = coordAt(trace.y, foundPoint);
                var z = coordAt(trace.z, foundPoint);
                if (x != null) {
                    var rs = {x: [[x]], y: [[y != null ? y : 0]]};
                    if (z != null) rs.z = [[z]];
                    Plotly.restyle(plotDiv, rs, [hlIdx]);
                }
                var fullTrace = plotDiv._fullData && plotDiv._fullData[foundTrace];
                var origTpl = fullTrace ? fullTrace.hovertemplate : undefined;
                if (fullTrace) fullTrace.hovertemplate = minTpl;
                try {
                    Plotly.Fx.hover(plotDiv, [{curveNumber: foundTrace, pointNumber: foundPoint}]);
                } catch (e) {}
                if (fullTrace && origTpl !== undefined) fullTrace.hovertemplate = origTpl;
            }
        }

        PLOT_IDS.forEach(function(srcId) {
            var srcDiv = getDiv(srcId);
            if (!srcDiv) return;
            srcDiv.on('plotly_hover', function(evt) {
                var pt = evt.points && evt.points[0];
                if (!pt) return;
                var hoveredId = idOf(pt.customdata);
                if (!hoveredId) return;
                PLOT_IDS.forEach(function(pid) { if (pid !== srcId) updateHighlight(pid, hoveredId); });
            });
            srcDiv.on('plotly_unhover', function() {
                PLOT_IDS.forEach(function(pid) { if (pid !== srcId) clearHighlight(pid); });
            });
        });
    }

    // ══════════════════════════════════════════════════════════════════
    // Legend-click sync — ported from legend_sync.py. A click on any
    // plot's legend hides/shows that group's traces (by name) everywhere.
    // ══════════════════════════════════════════════════════════════════
    function wireLegendSync() {
        if (PLOT_IDS.length < 2) return;
        var skip = new Set();

        PLOT_IDS.forEach(function(srcId) {
            var srcDiv = getDiv(srcId);
            if (!srcDiv) return;
            srcDiv.on('plotly_restyle', function(evt) {
                if (skip.has(srcId)) { skip.delete(srcId); return; }
                if (!evt || !evt[0] || !('visible' in evt[0])) return;

                var propDict = evt[0];
                var traceIndices = evt[1] || [];
                var visArray = propDict.visible;

                var visMap = {};
                for (var i = 0; i < traceIndices.length; i++) {
                    var idx = traceIndices[i];
                    var name = srcDiv.data[idx] && srcDiv.data[idx].name;
                    if (name && name !== '__hover_highlight__') {
                        visMap[name] = Array.isArray(visArray) ? visArray[i] : visArray;
                    }
                }
                if (!Object.keys(visMap).length) return;

                PLOT_IDS.forEach(function(pid) {
                    if (pid === srcId) return;
                    var div = getDiv(pid);
                    if (!div) return;
                    var idxList = [], visList = [];
                    for (var j = 0; j < div.data.length; j++) {
                        var tname = div.data[j].name;
                        if (tname in visMap) { idxList.push(j); visList.push(visMap[tname]); }
                    }
                    if (idxList.length) {
                        skip.add(pid);
                        Plotly.restyle(div, {visible: visList}, idxList);
                    }
                });
            });
        });
    }

    // ══════════════════════════════════════════════════════════════════
    // Time-slice slider — a two-thumb range over the time column (when
    // present among the exported table columns), mirroring
    // sync_time_window_to_selection: moving it overrides the selection
    // with exactly the ids whose time value falls inside the window.
    // ══════════════════════════════════════════════════════════════════
    var tsLo, tsHi, tsLabel, tsMin, tsMax;

    function resetTimeSlice() {
        if (!tsLo) return;
        tsLo.value = tsMin;
        tsHi.value = tsMax;
        renderTimeSliceLabel();
    }

    function renderTimeSliceLabel() {
        tsLabel.textContent = Number(tsLo.value).toFixed(1) + ' – ' + Number(tsHi.value).toFixed(1);
    }

    function onTimeSliceInput() {
        var lo = parseFloat(tsLo.value), hi = parseFloat(tsHi.value);
        if (lo > hi) { var t = lo; lo = hi; hi = t; }
        renderTimeSliceLabel();
        var ids = Object.keys(DATA.idToTime).filter(function(id) {
            var v = DATA.idToTime[id];
            return v >= lo && v <= hi;
        });
        applySelection(ids);
    }

    function wireTimeSlice() {
        var wrap = document.getElementById('time-slice');
        if (!wrap || !DATA.idToTime) return;
        var values = Object.keys(DATA.idToTime).map(function(k) { return DATA.idToTime[k]; });
        tsMin = Math.min.apply(null, values);
        tsMax = Math.max.apply(null, values);

        wrap.innerHTML =
            '<span>Time slice:<\/span>' +
            '<div class="rng">' +
            '<input type="range" id="ts-lo" min="' + tsMin + '" max="' + tsMax + '" value="' + tsMin + '" step="any">' +
            '<input type="range" id="ts-hi" min="' + tsMin + '" max="' + tsMax + '" value="' + tsMax + '" step="any">' +
            '<\/div>' +
            '<span id="ts-label"><\/span>';
        tsLo = document.getElementById('ts-lo');
        tsHi = document.getElementById('ts-hi');
        tsLabel = document.getElementById('ts-label');
        renderTimeSliceLabel();
        tsLo.addEventListener('input', onTimeSliceInput);
        tsHi.addEventListener('input', onTimeSliceInput);
    }

    // ══════════════════════════════════════════════════════════════════
    // Table — AG Grid Community, loaded from CDN. Sortable/filterable per
    // column out of the box; rows matching the current selection stay at
    // full opacity, everything else dims. Deliberately read-only (no row
    // checkboxes driving selection back into the plots) to keep one clear
    // direction of truth: the plots (and the time slice) decide the
    // selection, the table just reflects it.
    // ══════════════════════════════════════════════════════════════════
    function wireTable() {
        var container = document.getElementById('ag-table');
        if (!container || !window.agGrid) return;
        agGrid.ModuleRegistry.registerModules([agGrid.AllCommunityModule]);
        var gridOptions = {
            columnDefs: DATA.columnDefs,
            rowData: DATA.rows,
            defaultColDef: {resizable: true, sortable: true, filter: true},
            getRowStyle: function(params) {
                if (!currentSelection) return null;
                var id = params.data && String(params.data.id);
                return currentSelection.indexOf(id) === -1 ? {opacity: 0.35} : null;
            },
        };
        window._gridApi = agGrid.createGrid(container, gridOptions);
    }

    // ══════════════════════════════════════════════════════════════════
    // Pane resizing (unchanged from the previous export) + boot.
    // ══════════════════════════════════════════════════════════════════
    var raf = null;
    function rp() {
        if (raf) return;
        raf = requestAnimationFrame(function() {
            raf = null;
            document.querySelectorAll('.js-plotly-plot').forEach(function(e) {
                if (!e.layout) return;
                var p = e.parentElement;
                if (!p) return;
                var r = p.getBoundingClientRect();
                if (r.width > 0 && r.height > 0) {
                    try { Plotly.relayout(e, {width: r.width, height: r.height}); } catch (x) {}
                }
            });
            if (window._gridApi) window._gridApi.sizeColumnsToFit();
        });
    }
    function iv(r, l, ri) {
        var re = document.getElementById(r);
        if (!re) return;
        re.addEventListener('mousedown', function(e) {
            e.preventDefault();
            var le = document.getElementById(l), re2 = document.getElementById(ri);
            var x0 = e.clientX, lw = le.getBoundingClientRect().width,
                rw = re2.getBoundingClientRect().width, tot = lw + rw;
            function mv(e) {
                var d = e.clientX - x0, w = Math.max(120, Math.min(tot - 120, lw + d));
                le.style.flex = '0 0 ' + w + 'px'; re2.style.flex = '0 0 ' + (tot - w) + 'px'; rp();
            }
            function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); rp(); }
            document.addEventListener('mousemove', mv);
            document.addEventListener('mouseup', up);
        });
    }
    function ih(r, t, b) {
        var re = document.getElementById(r);
        if (!re) return;
        re.addEventListener('mousedown', function(e) {
            e.preventDefault();
            var te = document.getElementById(t), be = document.getElementById(b);
            var y0 = e.clientY, th = te.getBoundingClientRect().height,
                bh = be.getBoundingClientRect().height, tot = th + bh;
            function mv(e) {
                var d = e.clientY - y0, h = Math.max(60, Math.min(tot - 60, th + d));
                te.style.flex = '0 0 ' + h + 'px'; be.style.flex = '0 0 ' + (tot - h) + 'px'; rp();
            }
            function up() { document.removeEventListener('mousemove', mv); document.removeEventListener('mouseup', up); rp(); }
            document.addEventListener('mousemove', mv);
            document.addEventListener('mouseup', up);
        });
    }

    window.addEventListener('load', function() {
        iv('vr', 'left-col', 'right-col');
        ih('hl', 'pca-wrap', 'time-wrap');
        ih('hr', 'map-wrap', 'tbl-wrap');
        wireSelectionEvents();
        wireHoverSync();
        wireLegendSync();
        wireTimeSlice();
        wireTable();
        updateCounter();
        setTimeout(rp, 80);
    });
})();
"""
