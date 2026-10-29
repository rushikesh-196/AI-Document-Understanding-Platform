/* ==========================================================================
   AI Document Intelligence Platform — History Management JS
   ========================================================================== */

document.addEventListener("DOMContentLoaded", () => {
    loadCompleteHistory();

    const searchInput = document.getElementById("historySearchInput");
    const typeFilter = document.getElementById("historyTypeFilter");

    if (searchInput) searchInput.addEventListener("input", filterHistory);
    if (typeFilter) typeFilter.addEventListener("change", filterHistory);
});

function loadCompleteHistory() {
    const tableBody = document.getElementById("userHistoryTableBody");
    if (!tableBody) return;

    // Get user-specific local storage history
    const localHistory = AuthManager.getUserHistory() || [];

    // Fetch backend API history to merge
    fetch('/api/v1/jobs')
        .then(res => res.json())
        .then(data => {
            const apiRecords = data.jobs || data.history || [];
            
            // Merge local and API records, avoiding duplicates
            const combinedMap = new Map();

            localHistory.forEach(item => {
                const id = item.job_id || item.id;
                if (id) combinedMap.set(id, item);
            });

            apiRecords.forEach(item => {
                const id = item.job_id || item.id;
                if (id && !combinedMap.has(id)) {
                    combinedMap.set(id, {
                        id: id,
                        job_id: id,
                        filename: item.filename || "Document",
                        upload_time: item.upload_time || item.timestamp || "N/A",
                        document_type: item.document_type || "Invoice",
                        status: "Processed"
                    });
                }
            });

            const mergedList = Array.from(combinedMap.values());
            renderHistoryRows(mergedList);
        })
        .catch(() => {
            renderHistoryRows(localHistory);
        });
}

function renderHistoryRows(records) {
    const tableBody = document.getElementById("userHistoryTableBody");
    if (!tableBody) return;

    if (!records || records.length === 0) {
        tableBody.innerHTML = `
            <tr>
                <td colspan="6" style="text-align: center; padding: 48px 24px; color: var(--text-muted);">
                    <i class="fa-solid fa-folder-open" style="font-size: 2.5rem; margin-bottom: 12px; opacity: 0.5;"></i>
                    <p style="font-weight: 600;">No documents found in your history.</p>
                    <a href="/upload" class="btn btn-primary btn-sm" style="margin-top: 12px;">
                        <i class="fa-solid fa-cloud-arrow-up"></i> Upload Your First Document
                    </a>
                </td>
            </tr>
        `;
        return;
    }

    tableBody.innerHTML = records.map(item => {
        const jobId = item.job_id || item.id || "JOB-UNKNOWN";
        const filename = item.filename || "Document";
        const uploadDate = item.upload_time || item.timestamp || "N/A";
        const docType = item.document_type || "General Document";

        return `
            <tr id="jobRow_${jobId}">
                <td>
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <i class="fa-solid fa-file-contract" style="color: var(--primary); font-size: 1.1rem;"></i>
                        <strong style="color: var(--text-main);">${filename}</strong>
                    </div>
                </td>
                <td><span class="badge badge-primary">${docType}</span></td>
                <td>${uploadDate}</td>
                <td><span class="badge badge-success"><i class="fa-solid fa-circle-check"></i> Processed</span></td>
                <td><code style="font-family: var(--font-code); font-size: 0.8rem; background: var(--background-alt); padding: 2px 6px; border-radius: 4px;">${jobId}</code></td>
                <td style="text-align: right;">
                    <div style="display: inline-flex; gap: 6px;">
                        <a href="/results/${jobId}" class="btn btn-outline btn-sm" title="View Result Page">
                            <i class="fa-solid fa-eye"></i> View Result
                        </a>
                        <button type="button" class="btn btn-danger btn-sm" onclick="deleteRecord('${jobId}')" title="Delete Record">
                            <i class="fa-solid fa-trash"></i>
                        </button>
                    </div>
                </td>
            </tr>
        `;
    }).join("");
}

function filterHistory() {
    const query = (document.getElementById("historySearchInput")?.value || "").toLowerCase().trim();
    const selectedType = document.getElementById("historyTypeFilter")?.value || "ALL";
    const rows = document.querySelectorAll("#userHistoryTableBody tr");

    rows.forEach(row => {
        if (!row.children || row.children.length < 5) return;
        const text = row.innerText.toLowerCase();
        const docType = row.children[1]?.innerText.toUpperCase() || "";

        const matchesQuery = !query || text.includes(query);
        const matchesType = selectedType === "ALL" || docType.includes(selectedType);

        if (matchesQuery && matchesType) {
            row.style.display = "";
        } else {
            row.style.display = "none";
        }
    });
}

function deleteRecord(jobId) {
    if (!confirm(`Are you sure you want to delete history for ${jobId}?`)) return;

    // Delete from backend API
    fetch(`/api/v1/job/${jobId}`, { method: 'DELETE' })
        .catch(() => {});

    // Delete from local storage
    AuthManager.deleteJobFromHistory(jobId);
    showToast("Record removed from history.", "info");

    const row = document.getElementById(`jobRow_${jobId}`);
    if (row) row.remove();

    const remaining = document.querySelectorAll("#userHistoryTableBody tr");
    if (remaining.length === 0) loadCompleteHistory();
}
