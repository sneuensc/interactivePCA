// Resizable split pane functionality
(function() {
    let activeResizer = null;
    let activeContainer = null;
    let activeDirection = null;
    
    function attachResizerListeners(resizerId, containerId, direction) {
        const resizer = document.getElementById(resizerId);
        const container = document.getElementById(containerId);
        
        if (!resizer || !container) {
            console.log('Cannot attach resizer:', resizerId, 'resizer exists:', !!resizer, 'container exists:', !!container);
            return false;
        }
        
        console.log('Attaching resizer:', resizerId);
        
        resizer.onmousedown = function(e) {
            e.preventDefault();
            activeResizer = resizerId;
            activeContainer = containerId;
            activeDirection = direction;
            document.body.style.cursor = direction === 'vertical' ? 'col-resize' : 'row-resize';
            document.body.style.userSelect = 'none';
        };
        
        // Hover effect
        resizer.onmouseenter = function() {
            if (!activeResizer) {
                this.style.backgroundColor = '#999';
            }
        };
        
        resizer.onmouseleave = function() {
            if (!activeResizer) {
                this.style.backgroundColor = '#bbb';
            }
        };
        
        return true;
    }
    
    function handleMouseMove(e) {
        if (!activeResizer || !activeContainer || !activeDirection) return;
        
        const container = document.getElementById(activeContainer);
        if (!container) return;
        
        const containerRect = container.getBoundingClientRect();
        
        if (activeDirection === 'vertical') {
            // Vertical resize (left-right)
            const leftPane = container.querySelector('[data-pane="left"]');
            const rightPane = container.querySelector('[data-pane="right"]');
            
            if (!leftPane || !rightPane) return;
            
            const newLeftWidth = e.clientX - containerRect.left;
            const containerWidth = containerRect.width;
            const dividerWidth = 8;
            
            const leftPercent = Math.max(5, Math.min(95, (newLeftWidth / containerWidth) * 100));
            const rightPercent = 100 - leftPercent - (dividerWidth / containerWidth) * 100;
            
            leftPane.style.flex = `0 0 ${leftPercent}%`;
            rightPane.style.flex = `0 0 ${rightPercent}%`;
        } else {
            // Horizontal resize (top-bottom)
            const topPane = container.querySelector('[data-pane="top"]');
            const bottomPane = container.querySelector('[data-pane="bottom"]');
            
            if (!topPane || !bottomPane) {
                console.log('Horizontal resize: panes not found in', activeContainer);
                return;
            }
            
            const newTopHeight = e.clientY - containerRect.top;
            const containerHeight = containerRect.height;
            const dividerHeight = 8;
            
            const topPercent = Math.max(10, Math.min(90, (newTopHeight / containerHeight) * 100));
            const bottomPercent = 100 - topPercent - (dividerHeight / containerHeight) * 100;
            
            topPane.style.flex = `0 0 ${topPercent}%`;
            bottomPane.style.flex = `0 0 ${bottomPercent}%`;
        }
    }
    
    function handleMouseUp() {
        if (activeResizer) {
            activeResizer = null;
            activeContainer = null;
            activeDirection = null;
            document.body.style.cursor = '';
            document.body.style.userSelect = '';
        }
    }

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    
    function initializeAllResizers() {
        console.log('=== Initializing resizers ===');
        const success1 = attachResizerListeners('pca-vertical-resizer', 'pca-plots-container', 'vertical');
        const success2 = attachResizerListeners('pca-left-horizontal-resizer', 'pca-left-container', 'horizontal');
        const success3 = attachResizerListeners('pca-right-horizontal-resizer', 'pca-right-container', 'horizontal');
        console.log('Resize initialization complete:', { vertical: success1, leftHorizontal: success2, rightHorizontal: success3 });
    }
    
    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', function() {
            setTimeout(initializeAllResizers, 100);
        });
    } else {
        setTimeout(initializeAllResizers, 100);
    }
    
    // Re-initialize when tabs change
    const observer = new MutationObserver(function(mutations) {
        // Check if PCA tab content was added
        for (const mutation of mutations) {
            if (mutation.addedNodes.length > 0) {
                setTimeout(initializeAllResizers, 200);
                break;
            }
        }
    });
    
    // Start observing once DOM is ready
    function startObserving() {
        const tabsContent = document.getElementById('tabs-content');
        if (tabsContent) {
            observer.observe(tabsContent, { childList: true, subtree: true });
        } else {
            setTimeout(startObserving, 100);
        }
    }
    
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', startObserving);
    } else {
        startObserving();
    }
})();
