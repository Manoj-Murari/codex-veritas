/**
 * The Front-End Logic: The Brain of the Interactive Report.
 *
 * This script is responsible for all the dynamic and interactive features
 * of the report page. It communicates with our FastAPI Data API to fetch
 * and display the analysis results.
 *
 * Core responsibilities:
 * 1. On page load, extracts the job_id from the URL.
 * 2. Fetches the main report data (summary and key components) from the API.
 * 3. Dynamically builds and renders the summary and key components tables.
 * 4. Attaches click event listeners to the component table rows.
 * 5. When a row is clicked, it fetches detailed node and relationship data.
 * 6. Populates and displays a modal window (the "Code Inspector") with the
 * detailed information, including the source code snippet.
 * 7. Handles the closing of the modal.
 */

// --- DOM Element References ---
const summaryContainer = document.getElementById('summary-table-container');
const componentsContainer = document.getElementById('components-table-container');
const modal = document.getElementById('inspector-modal');
const modalBody = document.getElementById('modal-body');
const closeButton = document.querySelector('.close-button');

// --- Helper Functions ---

/**
 * Creates and returns a table element from a list of headers and data rows.
 * @param {string[]} headers - An array of header strings for the table.
 * @param {string[][]} rows - A 2D array representing the rows and cells of the table.
 * @param {string} rowIdPrefix - An optional prefix for creating unique IDs on each row.
 * @returns {HTMLTableElement} - The constructed table element.
 */
function createTable(headers, rows, rowIdPrefix = '') {
    const table = document.createElement('table');
    const thead = table.createTHead();
    const tbody = table.createTBody();
    const headerRow = thead.insertRow();

    headers.forEach(headerText => {
        const th = document.createElement('th');
        th.textContent = headerText;
        headerRow.appendChild(th);
    });

    rows.forEach(rowData => {
        const row = tbody.insertRow();
        if (rowIdPrefix && rowData.length > 0) {
            // Use the first cell's content (the node ID) to create a unique DOM id.
            row.dataset.nodeId = rowData[0]; 
        }
        rowData.slice(1).forEach(cellData => { // Skip the ID cell for rendering
            const cell = row.insertCell();
            cell.textContent = cellData;
        });
    });

    return table;
}

/**
 * Fetches data from a given API endpoint and handles errors.
 * @param {string} url - The API endpoint URL to fetch.
 * @returns {Promise<any>} - The JSON data from the response.
 */
async function fetchData(url) {
    try {
        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }
        return await response.json();
    } catch (error) {
        console.error(`Failed to fetch data from ${url}:`, error);
        return null;
    }
}

// --- Main Application Logic ---

/**
 * The main function that runs when the report page is loaded.
 */
async function initializeReport() {
    // 1. Extract the job_id from the window's URL path.
    const pathParts = window.location.pathname.split('/');
    const jobId = pathParts[pathParts.length - 1];

    if (!jobId) {
        summaryContainer.innerHTML = "<p>Error: No job ID found in URL.</p>";
        return;
    }

    // 2. Fetch the main report data.
    const reportData = await fetchData(`/api/report/${jobId}`);
    if (!reportData) {
        summaryContainer.innerHTML = "<p>Error: Could not load report data.</p>";
        return;
    }

    // 3. Render the summary table.
    const summaryHeaders = ['Metric', 'Value'];
    const summaryRows = [
        ['', 'Total Files Analyzed', reportData.summary.total_files],
        ['', 'Identified Components', reportData.summary.total_components],
        ['', 'Identified Relations', reportData.summary.total_relations]
    ];
    summaryContainer.innerHTML = ''; // Clear "Loading..." message
    summaryContainer.appendChild(createTable(summaryHeaders, summaryRows));

    // 4. Render the key components table.
    const componentHeaders = ['Name', 'Type', 'File Path', 'Lines'];
    const componentRows = reportData.key_components.map(node => [
        node.id, // Pass the ID for the data-attribute, but it won't be rendered as a cell
        node.name,
        node.type,
        node.file_path,
        `${node.start_line}-${node.end_line}`
    ]);
    componentsContainer.innerHTML = ''; // Clear "Loading..." message
    const componentsTable = createTable(componentHeaders, componentRows, 'component-row-');
    componentsContainer.appendChild(componentsTable);
    
    // 5. Add click listeners to the component table rows.
    componentsTable.querySelectorAll('tbody tr').forEach(row => {
        row.addEventListener('click', () => {
            const nodeId = row.dataset.nodeId;
            openInspectorModal(jobId, nodeId);
        });
    });
}

/**
 * Fetches detailed data for a node and displays the inspector modal.
 * @param {string} jobId - The current analysis job ID.
 * @param {string} nodeId - The unique ID of the node to inspect.
 */
async function openInspectorModal(jobId, nodeId) {
    modal.style.display = 'block';
    modalBody.innerHTML = '<p>Loading details...</p>';

    // Fetch node details and relations in parallel for speed.
    const [nodeDetails, nodeRelations] = await Promise.all([
        fetchData(`/api/node/${jobId}/${encodeURIComponent(nodeId)}`),
        fetchData(`/api/relations/${jobId}/${encodeURIComponent(nodeId)}`)
    ]);

    if (!nodeDetails || !nodeRelations) {
        modalBody.innerHTML = '<p>Error: Could not load node details.</p>';
        return;
    }
    
    // Build the content for the modal
    const callersTable = createTable(['Caller', 'Type', 'File'], nodeRelations.callers.map(n => [n.id, n.name, n.type, n.file_path]));
    const calleesTable = createTable(['Callee', 'Type', 'File'], nodeRelations.callees.map(n => [n.id, n.name, n.type, n.file_path]));
    
    const modalHTML = `
        <h3>${nodeDetails.name} <span style="color: #888; font-size: 0.8em;">(${nodeDetails.type})</span></h3>
        <p><strong>File:</strong> ${nodeDetails.file_path}</p>
        <h4>Source Code</h4>
        <pre><code>${nodeDetails.source_code || 'Not available.'}</code></pre>
        <div class="relations-grid">
            <div>
                <h4>Callers (${nodeRelations.callers.length})</h4>
                ${nodeRelations.callers.length > 0 ? callersTable.outerHTML : '<p>No callers found in the graph.</p>'}
            </div>
            <div>
                <h4>Callees (${nodeRelations.callees.length})</h4>
                ${nodeRelations.callees.length > 0 ? calleesTable.outerHTML : '<p>No callees found in the graph.</p>'}
            </div>
        </div>
    `;
    
    modalBody.innerHTML = modalHTML;
}

// --- Event Listeners ---

// Close the modal when the 'x' is clicked
closeButton.onclick = function() {
    modal.style.display = "none";
}

// Close the modal when the user clicks outside of the modal content
window.onclick = function(event) {
    if (event.target == modal) {
        modal.style.display = "none";
    }
}

// Kick off the main process when the window loads.
window.onload = initializeReport;
