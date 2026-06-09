var dagcomponentfuncs = (window.dashAgGridComponentFunctions =
    window.dashAgGridComponentFunctions || {});

/**
 * ColorPickerRenderer
 *
 * Renders an <input type="color"> inside an AG Grid cell.
 * Uses local React state so the picker responds smoothly without
 * round-tripping to Python on every frame.  The value is only
 * committed back to AG Grid (and therefore to Dash's rowData) when
 * the picker is closed (onBlur), keeping network traffic minimal.
 */
/**
 * LineColorRenderer
 *
 * Two states:
 *   - null / empty  → greyed-out "—" placeholder (no border); clicking it
 *                     re-enables the border using the fill colour stored in
 *                     the row's `color` field, or falls back to #000000.
 *   - hex string    → colour picker + "×" button that clears back to null.
 *
 * Default is the fill colour, so every group starts with a same-colour border.
 */
dagcomponentfuncs.LineColorRenderer = function (props) {
    var isNull = !props.value || props.value === 'null';
    var _state = React.useState(isNull ? (props.data && props.data.color || '#000000') : props.value);
    var color = _state[0];
    var setColor = _state[1];

    React.useEffect(function () {
        var none = !props.value || props.value === 'null';
        setColor(none ? (props.data && props.data.color || '#000000') : props.value);
    }, [props.value]);

    if (isNull) {
        // Greyed-out: no border. Click to restore fill colour as border.
        return React.createElement(
            'div',
            {
                style: {
                    display: 'flex', alignItems: 'center',
                    justifyContent: 'center', height: '100%', cursor: 'pointer'
                },
                title: 'Click to set line colour (default: fill colour)',
                onClick: function () {
                    var fillColor = (props.data && props.data.color) || '#000000';
                    props.node.setDataValue(props.column.colId, fillColor);
                }
            },
            React.createElement('div', {
                style: {
                    width: '34px', height: '28px',
                    border: '1px dashed #bbb', borderRadius: '3px',
                    backgroundColor: '#f0f0f0',
                    display: 'flex', alignItems: 'center', justifyContent: 'center',
                    fontSize: '13px', color: '#bbb', userSelect: 'none'
                }
            }, '—')
        );
    }

    // Active: colour picker + "×" to clear (no border)
    return React.createElement(
        'div',
        {
            style: {
                display: 'flex', alignItems: 'center',
                justifyContent: 'center', height: '100%', gap: '2px'
            }
        },
        React.createElement('input', {
            type: 'color',
            value: color,
            onChange: function (e) { setColor(e.target.value); },
            onBlur: function (e) {
                props.node.setDataValue(props.column.colId, e.target.value);
            },
            style: {
                width: '34px', height: '28px', padding: '0',
                border: '1px solid #ced4da', cursor: 'pointer', borderRadius: '3px'
            }
        }),
        React.createElement('span', {
            title: 'Remove line colour',
            onClick: function (e) {
                e.stopPropagation();
                props.node.setDataValue(props.column.colId, null);
            },
            style: {
                cursor: 'pointer', color: '#aaa', fontSize: '12px',
                lineHeight: 1, userSelect: 'none', paddingBottom: '1px'
            }
        }, '×')
    );
};

dagcomponentfuncs.ColorPickerRenderer = function (props) {
    var _React$useState = React.useState(props.value || '#cccccc');
    var color = _React$useState[0];
    var setColor = _React$useState[1];

    // Keep local state in sync when AG Grid pushes a new value
    // (e.g. after undo, row refresh, or external rowData update).
    React.useEffect(function () {
        setColor(props.value || '#cccccc');
    }, [props.value]);

    return React.createElement(
        'div',
        {
            style: {
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                height: '100%'
            }
        },
        React.createElement('input', {
            type: 'color',
            value: color,
            onChange: function (e) {
                setColor(e.target.value);
            },
            onBlur: function (e) {
                props.node.setDataValue(props.column.colId, e.target.value);
            },
            style: {
                width: '40px',
                height: '32px',
                padding: '0',
                border: '1px solid #ced4da',
                cursor: 'pointer',
                borderRadius: '3px'
            }
        })
    );
};
