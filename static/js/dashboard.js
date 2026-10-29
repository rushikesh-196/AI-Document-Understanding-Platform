/* Results / Dashboard Page JavaScript */

let currentDocZoom = 1.0;
let parsedJobData = null;

function getJobData() {
    if (parsedJobData) return parsedJobData;
    const jsonEl = document.getElementById('rawJobJson');
    if (jsonEl && jsonEl.textContent && jsonEl.textContent.trim()) {
        try {
            parsedJobData = JSON.parse(jsonEl.textContent);
        } catch (e) {
            console.error('Failed to parse job json:', e);
        }
    }
    return parsedJobData;
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function normalizeText(value) {
    if (value == null) return '';
    if (typeof value === 'string') return value.trim();
    if (typeof value === 'number' || typeof value === 'boolean') return String(value);
    if (Array.isArray(value)) return value.map(normalizeText).filter(Boolean).join('\n');
    if (typeof value === 'object') {
        if (value.text) return String(value.text).trim();
        if (value.value) return String(value.value).trim();
        if (value.row) return String(value.row).trim();
        return '';
    }
    return String(value).trim();
}

function hasContent(value) {
    if (value == null) return false;
    if (Array.isArray(value)) return value.length > 0;
    if (typeof value === 'object') return Object.keys(value).length > 0;
    return normalizeText(value).length > 0;
}

/**
 * Collect entities from all possible job fields (unified + legacy).
 */
function collectEntities(job) {
    const entities = [];
    const seen = new Set();

    function add(label, text) {
        const clean = normalizeText(text);
        if (!clean || clean.length < 2) return;
        const key = `${(label || 'ENTITY').toUpperCase()}::${clean.toLowerCase()}`;
        if (seen.has(key)) return;
        seen.add(key);
        entities.push({ label: (label || 'ENTITY').toUpperCase(), text: clean, value: clean });
    }

    // Primary unified entities array
    (job.entities || []).forEach((ent) => {
        if (typeof ent === 'object') {
            add(ent.label || ent.type || 'ENTITY', ent.text || ent.value);
        }
    });

    // Legacy spaCy entities
    (job.spacy_entities || []).forEach((ent) => {
        if (typeof ent === 'object') {
            const labelMap = {
                PERSON: 'PERSON', ORG: 'ORGANIZATION', GPE: 'LOCATION',
                LOC: 'LOCATION', DATE: 'DATE', MONEY: 'AMOUNT', PRODUCT: 'PRODUCT',
            };
            const lbl = labelMap[ent.label] || ent.label || 'ENTITY';
            add(lbl, ent.text || ent.value);
        }
    });

    // Legacy compact JSON key_entities
    (job.key_entities || []).forEach((ent) => {
        if (typeof ent === 'object') add(ent.label || 'ENTITY', ent.text || ent.value);
    });

    // Structured data fields as entities
    const fieldLabels = {
        email: 'EMAIL', phone: 'PHONE', date: 'DATE', due_date: 'DATE',
        total_amount: 'AMOUNT', subtotal: 'AMOUNT', tax: 'AMOUNT',
        invoice_number: 'INVOICE NUMBER', receipt_number: 'RECEIPT NUMBER',
        order_number: 'ORDER NUMBER', gst_number: 'GST NUMBER', pan_number: 'PAN NUMBER',
        aadhaar_number: 'ID NUMBER', id_number: 'ID NUMBER',
        name: 'PERSON', customer_name: 'PERSON', patient_name: 'PERSON',
        company: 'ORGANIZATION', vendor_name: 'ORGANIZATION',
        address: 'LOCATION', city: 'LOCATION', skills: 'SKILLS',
        job_title: 'JOB TITLE', degree: 'EDUCATION', payment_method: 'PAYMENT METHOD',
    };
    const sd = job.structured_data || {};
    Object.entries(sd).forEach(([key, val]) => {
        if (hasContent(val)) add(fieldLabels[key] || key.replace(/_/g, ' ').toUpperCase(), val);
    });

    // Extracted fields list
    (job.extracted_fields || []).forEach((field) => {
        if (typeof field === 'object' && field.value) {
            const key = field.field_key || '';
            add(fieldLabels[key] || (field.field_name || key).toUpperCase(), field.value);
        }
    });

    return entities;
}

function collectTables(job) {
    const tables = job.tables || [];
    if (!tables.length) return [];

    return tables.filter((table) => {
        if (typeof table === 'string') return table.trim().length > 0;
        if (table && typeof table === 'object') {
            if (table.row) return normalizeText(table.row).length > 0;
            if (Array.isArray(table.rows) && table.rows.length > 0) return true;
        }
        return false;
    });
}

function switchResultTab(tabKey, btnEl) {
    document.querySelectorAll('.result-tab-btn').forEach((btn) => {
        btn.classList.remove('active');
        btn.setAttribute('aria-selected', 'false');
    });
    document.querySelectorAll('.results-tab-card .tab-pane').forEach((pane) => {
        pane.classList.remove('active');
    });

    if (btnEl) {
        btnEl.classList.add('active');
        btnEl.setAttribute('aria-selected', 'true');
    }

    const target = document.getElementById(`tabContent_${tabKey}`);
    if (target) target.classList.add('active');

    if (tabKey === 'formattedViewTab') renderFormattedView();
    if (tabKey === 'structuredLayoutTab') renderStructuredLayout();
}

function toggleJsonExpand(expand) {
    const panel = document.getElementById('jsonViewerPanel');
    const expBtn = document.getElementById('expandJsonBtn');
    const colBtn = document.getElementById('collapseJsonBtn');
    if (!panel) return;
    if (expand) {
        panel.classList.add('expanded');
        if (expBtn) expBtn.style.display = 'none';
        if (colBtn) colBtn.style.display = 'inline-flex';
    } else {
        panel.classList.remove('expanded');
        if (expBtn) expBtn.style.display = 'inline-flex';
        if (colBtn) colBtn.style.display = 'none';
    }
}

function copyJsonOutput() {
    const codeEl = document.getElementById('jsonCodeBlock');
    if (!codeEl) return;
    navigator.clipboard.writeText(codeEl.textContent).then(() => {
        showToast('JSON copied to clipboard!', 'success');
    }).catch(() => showToast('Failed to copy JSON.', 'error'));
}

function copyRawExtractedText() {
    const textBlock = document.getElementById('rawExtractedTextBlock');
    if (!textBlock) return;
    navigator.clipboard.writeText(textBlock.textContent).then(() => {
        showToast('Raw text copied to clipboard!', 'success');
    }).catch(() => showToast('Failed to copy raw text.', 'error'));
}

function copySummaryText() {
    const narrative = document.getElementById('summaryNarrativePanel');
    const findings = document.getElementById('summaryFindingsPanel');
    let text = '';
    if (narrative && narrative.innerText.trim()) {
        text += '=== SUMMARY ===\n' + narrative.innerText.trim() + '\n\n';
    }
    if (findings && findings.innerText.trim()) {
        text += '=== KEY FINDINGS ===\n' + findings.innerText.trim();
    }
    if (!text.trim()) {
        const job = getJobData() || {};
        text = job.summary || job.ai_summary || '';
    }
    if (!text.trim()) {
        showToast('No summary content to copy.', 'error');
        return;
    }
    navigator.clipboard.writeText(text.trim()).then(() => {
        showToast('Summary copied to clipboard!', 'success');
    }).catch(() => showToast('Failed to copy summary.', 'error'));
}

function copyTablesData() {
    const job = getJobData() || {};
    const tables = collectTables(job);
    if (!tables || !tables.length) {
        showToast('No table data to copy.', 'error');
        return;
    }
    let tsv = '';
    tables.forEach((t) => {
        if (typeof t === 'string') {
            tsv += t + '\n\n';
            return;
        }
        if (t.headers && Array.isArray(t.headers)) {
            tsv += t.headers.join('\t') + '\n';
        }
        if (t.rows && Array.isArray(t.rows)) {
            t.rows.forEach(r => {
                if (Array.isArray(r)) {
                    tsv += r.join('\t') + '\n';
                } else if (typeof r === 'object' && t.headers) {
                    tsv += t.headers.map(h => r[h] || r[h.toLowerCase()] || '').join('\t') + '\n';
                } else {
                    tsv += String(r) + '\n';
                }
            });
        }
        tsv += '\n';
    });
    navigator.clipboard.writeText(tsv.trim()).then(() => {
        showToast('Tables copied (TSV format)!', 'success');
    }).catch(() => showToast('Failed to copy tables.', 'error'));
}

function getCurrentJobId() {
    if (window.currentJobId) return String(window.currentJobId).trim();
    const rawEl = document.getElementById('rawJobJson');
    if (!rawEl || !rawEl.textContent || !rawEl.textContent.trim()) return '';
    try {
        const payload = JSON.parse(rawEl.textContent);
        if (payload && payload.job_id) return String(payload.job_id).trim();
    } catch (error) {
        console.error('Failed to parse job payload for export.', error);
    }
    return '';
}

function getExportFileName(fmt, jobId) {
    const ext = fmt === 'excel' ? 'xlsx' : fmt;
    return `${jobId}.${ext}`;
}

function getExportLabel(fmt) {
    const labels = {
        txt: 'TXT',
        pdf: 'PDF',
        docx: 'DOCX',
        json: 'JSON',
        csv: 'CSV',
        excel: 'XLSX',
    };
    return labels[fmt] || String(fmt || '').toUpperCase();
}

function setDownloadButtonState(button, isLoading) {
    if (!button) return;
    const originalLabel = button.dataset.originalLabel || button.innerHTML;
    if (isLoading) {
        button.dataset.originalLabel = originalLabel;
        button.disabled = true;
        button.setAttribute('aria-busy', 'true');
        button.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Downloading...';
        return;
    }

    button.disabled = false;
    button.removeAttribute('aria-busy');
    button.innerHTML = originalLabel;
}

async function triggerDirectDownload(fmt, button) {
    const jobId = getCurrentJobId();
    if (!jobId) {
        showToast('Job ID unavailable for export.', 'error');
        return;
    }

    const normalizedFmt = String(fmt || '').toLowerCase();
    const exportUrl = `/api/v1/export/${normalizedFmt}/${jobId}`;
    const buttonRef = button || document.querySelector(`[data-export-format="${normalizedFmt}"]`);

    if (buttonRef && buttonRef.dataset.exportInProgress === 'true') {
        return;
    }

    if (buttonRef) {
        buttonRef.dataset.exportInProgress = 'true';
        setDownloadButtonState(buttonRef, true);
    }

    try {
        const response = await fetch(exportUrl, {
            method: 'GET',
            credentials: 'same-origin',
            headers: { Accept: '*/*' },
            cache: 'no-store',
        });

        if (!response.ok) {
            let message = 'Download failed. Please try again.';
            try {
                const data = await response.json();
                if (data && data.message) message = data.message;
            } catch (error) {
                console.warn('Export response was not JSON.', error);
            }
            throw new Error(message);
        }

        const blob = await response.blob();
        if (blob.size === 0) {
            throw new Error('Download failed. Please try again.');
        }

        const url = URL.createObjectURL(blob);
        const anchor = document.createElement('a');
        anchor.href = url;
        anchor.rel = 'noopener';
        anchor.download = getExportFileName(normalizedFmt, jobId);
        document.body.appendChild(anchor);
        anchor.click();
        setTimeout(() => {
            URL.revokeObjectURL(url);
            if (anchor.parentNode) anchor.parentNode.removeChild(anchor);
        }, 1000);

        showToast(`${getExportLabel(normalizedFmt)} downloaded successfully`, 'success');
    } catch (error) {
        console.error(`Export failed for ${normalizedFmt}:`, error);
        showToast('Download failed. Please try again.', 'error');
    } finally {
        if (buttonRef) {
            buttonRef.dataset.exportInProgress = 'false';
            setDownloadButtonState(buttonRef, false);
        }
    }
}

function zoomDocImg(factor) {
    const img = document.getElementById('docPreviewImage');
    if (!img) return;
    currentDocZoom = Math.max(0.4, Math.min(3.0, currentDocZoom * factor));
    img.style.transform = `scale(${currentDocZoom})`;
}

function resetDocImg() {
    const img = document.getElementById('docPreviewImage');
    if (!img) return;
    currentDocZoom = 1.0;
    img.style.transform = 'scale(1)';
}

function renderEntities(job) {
    const container = document.getElementById('entitiesContainer');
    if (!container) return;

    const entities = collectEntities(job);
    if (!entities.length) {
        container.innerHTML = '<div class="results-empty-state"><i class="fa-solid fa-circle-info"></i> No named entities detected in this document.</div>';
        return;
    }

    container.innerHTML = `<div class="entity-cards-grid">${entities.map((ent) => {
        const label = escapeHtml(ent.label || 'ENTITY');
        const value = escapeHtml(ent.text || ent.value || '');
        return `<div class="entity-card"><span class="entity-label-badge">${label}</span><span class="entity-value-text">${value}</span></div>`;
    }).join('')}</div>`;
}

function renderTables(job) {
    const container = document.getElementById('tablesContainer');
    if (!container) return;

    const tables = collectTables(job);
    if (!tables.length) {
        container.innerHTML = '<div class="results-empty-state"><i class="fa-solid fa-circle-info"></i> No tabular data detected.</div>';
        return;
    }

    const html = tables.map((table) => {
        if (typeof table === 'string') {
            return `<div class="detected-table-wrapper"><table class="detected-table"><tbody><tr><td>${escapeHtml(table)}</td></tr></tbody></table></div>`;
        }
        if (table && table.row) {
            const rowStr = String(table.row);
            const moneyMatch = rowStr.match(/^(.+?)\s+([$€£₹]?\s?[\d,.]+)$/);
            const cells = rowStr.includes('|')
                ? rowStr.split('|').map((c) => c.trim())
                : moneyMatch
                    ? [moneyMatch[1].trim(), moneyMatch[2].trim()]
                    : [rowStr];
            return `<div class="detected-table-wrapper"><table class="detected-table"><tbody><tr>${cells.map((c) => `<td>${escapeHtml(c)}</td>`).join('')}</tr></tbody></table></div>`;
        }
        const headers = Array.isArray(table.headers) ? table.headers : [];
        const rows = Array.isArray(table.rows) ? table.rows : [];
        const headerHtml = headers.length
            ? `<thead><tr>${headers.map((h) => `<th>${escapeHtml(h)}</th>`).join('')}</tr></thead>` : '';
        const bodyHtml = rows.map((row) => {
            const cells = Array.isArray(row) ? row : [row];
            return `<tr>${cells.map((c) => `<td>${escapeHtml(c ?? '')}</td>`).join('')}</tr>`;
        }).join('');
        return `<div class="detected-table-wrapper"><table class="detected-table">${headerHtml}<tbody>${bodyHtml}</tbody></table></div>`;
    }).filter(Boolean).join('');

    container.innerHTML = html || '<div class="results-empty-state"><i class="fa-solid fa-circle-info"></i> No tabular data detected.</div>';
}

function buildFormattedViewText(job) {
    const candidates = [
        job && job.display_formatted_text,
        job && job.formatted_text,
        job && job.summary,
        job && job.raw_text,
    ];

    for (const candidate of candidates) {
        const text = normalizeText(candidate);
        if (text && !text.includes('[object Object]') && !text.includes('object Object')) {
            return text;
        }
    }
    return 'No formatted content available.';
}

function looksLikeTableRow(value) {
    const row = String(value || '').trim();
    if (!row) return false;
    if (/\|/.test(row)) return true;
    if (/\t/.test(row)) return true;
    const columns = row.split(/\s{2,}/).filter(Boolean);
    return columns.length >= 2 && /\d/.test(row);
}

function renderTableFromJob(table) {
    if (!table) return '';

    if (Array.isArray(table.rows) && table.rows.length) {
        const headers = Array.isArray(table.headers) ? table.headers : [];
        const rows = table.rows.slice(0, 12);
        const headerHtml = headers.length
            ? `<thead><tr>${headers.map((h) => `<th>${escapeHtml(h || '')}</th>`).join('')}</tr></thead>`
            : '';
        const bodyHtml = rows.map((row) => {
            const cells = Array.isArray(row) ? row : [row];
            return `<tr>${cells.map((cell) => `<td>${escapeHtml(String(cell ?? ''))}</td>`).join('')}</tr>`;
        }).join('');

        return `
            <div class="formatted-table-wrap">
                <table class="formatted-document-table">
                    ${headerHtml}
                    <tbody>${bodyHtml}</tbody>
                </table>
            </div>
        `;
    }

    if (typeof table === 'string') {
        const rowText = table.trim();
        if (!rowText) return '';
        const cells = rowText.includes('|') ? rowText.split('|').map((cell) => cell.trim()).filter(Boolean) : [rowText];
        return `
            <div class="formatted-table-wrap">
                <table class="formatted-document-table">
                    <tbody>
                        <tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    if (table && typeof table === 'object' && table.row) {
        const rowText = String(table.row);
        const cells = rowText.includes('|') ? rowText.split('|').map((cell) => cell.trim()).filter(Boolean) : [rowText];
        return `
            <div class="formatted-table-wrap">
                <table class="formatted-document-table">
                    <tbody>
                        <tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr>
                    </tbody>
                </table>
            </div>
        `;
    }

    return '';
}

function isNoiseDocumentLine(line) {
    const value = String(line || '').trim();
    if (!value) return true;
    if (value.includes('[object Object]') || value.includes('object Object')) return true;
    if (value.includes('debug') || value.includes('traceback') || value.includes('python object')) return true;
    if (/^(\{|\[).*(\}|\])$/.test(value) || /^(api|response|message|status|error|debug)\s*:/i.test(value)) return true;
    if (/^https?:\/\//i.test(value) && value.length > 120) return true;
    return false;
}

function renderDocumentLikeText(containerId, sourceText, fallbackText, job = {}) {
    const container = document.getElementById(containerId);
    if (!container) return;

    const cleanText = String(sourceText || '')
        .replace(/\r/g, '')
        .replace(/\[object Object\]/gi, '')
        .replace(/\s*\n\s*\n\s*/g, '\n\n')
        .trim();

    const tableBlocks = Array.isArray(job.tables) ? job.tables.map(renderTableFromJob).filter(Boolean).join('') : '';
    const blocks = cleanText
        ? cleanText.split(/\n{2,}/).map((block) => block.trim()).filter(Boolean)
        : [];

    const titleText = (job.filename ? job.filename.replace(/\.[^.]+$/, '') : '') || (job.document_type ? String(job.document_type) : 'Document');
    const metaRows = [];
    if (job.document_type) metaRows.push({ label: 'Document Type', value: job.document_type });
    if (job.summary) metaRows.push({ label: 'Summary', value: job.summary });

    const renderedSections = blocks.map((block) => {
        const lines = block.split(/\n+/)
            .map((line) => line.replace(/\s+/g, ' ').trim())
            .filter((line) => Boolean(line) && !isNoiseDocumentLine(line));

        if (!lines.length) return '';

        const textOnly = lines.join(' ');
        if (looksLikeTableRow(textOnly) || lines.some((line) => looksLikeTableRow(line))) {
            return `<div class="formatted-content-block">${lines.map((line) => {
                const cells = line.includes('|') ? line.split('|').map((cell) => cell.trim()).filter(Boolean) : line.split(/\t|\s{2,}/).filter(Boolean);
                return cells.length > 1
                    ? `<div class="formatted-table-wrap"><table class="formatted-document-table"><tbody><tr>${cells.map((cell) => `<td>${escapeHtml(cell)}</td>`).join('')}</tr></tbody></table></div>`
                    : `<p class="formatted-paragraph">${escapeHtml(line)}</p>`;
            }).join('')}</div>`;
        }

        const sectionHeading = lines.find((line) => {
            const normalized = line.replace(/[:\-]/g, '').trim();
            return normalized.length >= 4 && normalized.length <= 60 && normalized === normalized.toUpperCase() && !/\d{1,2}\s+[A-Z]/.test(normalized);
        });

        if (sectionHeading) {
            const headingHtml = `<h3 class="formatted-section-heading">${escapeHtml(sectionHeading)}</h3>`;
            const remainingLines = lines.filter((line) => line !== sectionHeading);
            const bodyHtml = remainingLines.map((line) => {
                const kvMatch = line.match(/^([^:]{1,80}):\s*(.+)$/);
                if (kvMatch) {
                    return `<div class="formatted-kv"><span class="formatted-key">${escapeHtml(kvMatch[1].trim())}</span><span class="formatted-separator">:</span><span class="formatted-value">${escapeHtml(kvMatch[2].trim())}</span></div>`;
                }
                return `<p class="formatted-paragraph">${escapeHtml(line)}</p>`;
            }).join('');
            return `<div class="formatted-content-block">${headingHtml}${bodyHtml}</div>`;
        }

        const bodyHtml = lines.map((line) => {
            const kvMatch = line.match(/^([^:]{1,80}):\s*(.+)$/);
            if (kvMatch) {
                return `<div class="formatted-kv"><span class="formatted-key">${escapeHtml(kvMatch[1].trim())}</span><span class="formatted-separator">:</span><span class="formatted-value">${escapeHtml(kvMatch[2].trim())}</span></div>`;
            }
            return `<p class="formatted-paragraph">${escapeHtml(line)}</p>`;
        }).join('');

        return `<div class="formatted-content-block">${bodyHtml}</div>`;
    }).join('');

    const html = `
        <article class="formatted-document-shell">
            <header class="formatted-document-header">
                <div class="formatted-document-kicker">Document</div>
                <h1 class="formatted-document-title">${escapeHtml(titleText)}</h1>
                ${metaRows.length ? `<div class="formatted-document-meta">${metaRows.map((row) => `<div class="formatted-meta-row"><span class="formatted-meta-label">${escapeHtml(row.label)}</span><span class="formatted-meta-value">${escapeHtml(String(row.value).replace(/\s+/g, ' ').trim())}</span></div>`).join('')}</div>` : ''}
            </header>
            ${tableBlocks ? `<div class="formatted-table-group">${tableBlocks}</div>` : ''}
            ${renderedSections ? `<div class="formatted-document-body">${renderedSections}</div>` : `<p class="formatted-empty-state">${escapeHtml(fallbackText)}</p>`}
        </article>
    `;

    container.innerHTML = html;
}

function renderFormattedView() {
    const job = getJobData() || {};

    // If server-side Jinja already rendered HTML into the sheet, leave it as-is
    const sheet = document.getElementById('formattedDocumentSheet');
    if (sheet && sheet.innerHTML && sheet.innerHTML.trim() !== '') {
        return;
    }

    // Fallback 1: use formatted_html from the job JSON payload
    const htmlContent = normalizeText(job.formatted_html || job.display_formatted_html);
    if (htmlContent && sheet) {
        sheet.innerHTML = htmlContent;
        return;
    }

    // Fallback 2: text-based rendering (legacy)
    const text = buildFormattedViewText(job);
    renderDocumentLikeText('formattedTextContainer', text, 'No formatted content available.', job);
}

function switchFormattedViewMode(mode) {
    const visualPanel = document.getElementById('formattedVisualViewport');
    const textPanel   = document.getElementById('formattedTextPanel');
    const visualBtn   = document.getElementById('btnFormattedVisual');
    const textBtn     = document.getElementById('btnFormattedText');
    if (mode === 'visual') {
        if (visualPanel) visualPanel.style.display = '';
        if (textPanel)   textPanel.style.display   = 'none';
        if (visualBtn)   visualBtn.classList.add('active');
        if (textBtn)     textBtn.classList.remove('active');
    } else {
        if (visualPanel) visualPanel.style.display = 'none';
        if (textPanel)   textPanel.style.display   = '';
        if (visualBtn)   visualBtn.classList.remove('active');
        if (textBtn)     textBtn.classList.add('active');
    }
}

function printFormattedDocument() {
    const sheet = document.getElementById('formattedDocumentSheet');
    if (!sheet) return;
    const w = window.open('', '_blank');
    w.document.write(
        '<html><head><title>Document</title>' +
        '<style>body{background:#fff;margin:0;padding:32px;font-family:sans-serif;}' +
        'table{width:100%;border-collapse:collapse;}' +
        'th,td{border:1px solid #e2e8f0;padding:8px 12px;text-align:left;}' +
        'th{background:#f8fafc;font-weight:600;}' +
        '</style></head><body>' +
        sheet.innerHTML +
        '</body></html>'
    );
    w.document.close();
    w.print();
}

function copyFormattedDocumentText() {
    const block = document.getElementById('formattedPreBlock');
    if (!block) return;
    navigator.clipboard.writeText(block.textContent)
        .then(() => showToast('Document text copied!', 'success'))
        .catch(() => showToast('Failed to copy.', 'error'));
}

function renderStructuredLayout() {
    const container = document.getElementById('structuredLayoutContainer');
    if (!container) return;
    const job = getJobData() || {};
    const text = normalizeText(job.structured_layout);
    const safeText = text && !text.includes('[object Object]') ? text : 'Structured layout analysis is not available for this document.';
    renderDocumentLikeText('structuredLayoutContainer', safeText, 'Structured layout analysis is not available for this document.', job);
}

function renderRawText(job) {
    const block = document.getElementById('rawExtractedTextBlock');
    if (!block) return;
    const text = normalizeText(job.raw_text);
    if (text && !text.includes('[object Object]')) block.textContent = text;
}

/**
 * Highlight a value string inside the raw text panel to help users locate
 * extracted fields in the original document text.
 */
function highlightField(value) {
    if (!value) return;
    const textBlock = document.getElementById('rawExtractedTextBlock');
    if (!textBlock) return;

    // Switch to the Raw Text tab so the highlight is visible
    const rawTabBtn = document.querySelector('[data-tab="rawExtractedText"]');
    if (rawTabBtn && !rawTabBtn.classList.contains('active')) {
        switchResultTab('rawExtractedText', rawTabBtn);
    }

    const rawText = textBlock.textContent;
    const idx = rawText.toLowerCase().indexOf(String(value).toLowerCase());
    if (idx === -1) {
        showToast(`"${value}" not found in extracted text.`, 'error');
        return;
    }

    // Rebuild content with highlighted span
    const before = escapeHtml(rawText.slice(0, idx));
    const match  = escapeHtml(rawText.slice(idx, idx + value.length));
    const after  = escapeHtml(rawText.slice(idx + value.length));
    textBlock.innerHTML = `${before}<mark style="background: rgba(37,99,235,0.3); color: var(--text-main); border-radius: 3px; padding: 0 2px;">${match}</mark>${after}`;

    // Scroll the highlighted text into view
    const markEl = textBlock.querySelector('mark');
    if (markEl) markEl.scrollIntoView({ behavior: 'smooth', block: 'center' });

    showToast(`Highlighted "${value}" in extracted text`, 'success');
}

function initResultsPage() {
    const job = getJobData();
    if (!job) return;
    renderRawText(job);
    renderFormattedView();
    renderStructuredLayout();
    renderEntities(job);
    renderTables(job);
    renderInteractiveJsonTree();
}

document.addEventListener('DOMContentLoaded', initResultsPage);

/* ==========================================================================
   INTERACTIVE JSON TREE RENDERER
   ========================================================================== */

function renderInteractiveJsonTree(data, containerId) {
    const container = document.getElementById(containerId || 'interactiveJsonTree');
    if (!container) return;

    if (!data || typeof data !== 'object') {
        const jsonBlock = document.getElementById('jsonCodeBlock');
        if (jsonBlock && jsonBlock.textContent) {
            try { data = JSON.parse(jsonBlock.textContent); }
            catch (e) { container.innerHTML = '<pre>' + escapeHtml(jsonBlock.textContent) + '</pre>'; return; }
        }
    }

    container.innerHTML = createJsonNodeHtml(data, 'root', true);
}

function createJsonNodeHtml(val, key, isRoot) {
    if (val === null) {
        return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> <span class="json-null">null</span></div>`;
    }
    const type = typeof val;
    if (type === 'string') {
        return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> <span class="json-string">"${escapeHtml(val)}"</span></div>`;
    }
    if (type === 'number') {
        return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> <span class="json-number">${val}</span></div>`;
    }
    if (type === 'boolean') {
        return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> <span class="json-boolean">${val}</span></div>`;
    }

    if (Array.isArray(val)) {
        const count = val.length;
        if (count === 0) {
            return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> []</div>`;
        }
        let childrenHtml = val.map((item, i) => createJsonNodeHtml(item, i, false)).join('');
        return `
            <div class="json-node ${isRoot ? 'json-node-root' : ''}">
                <div class="json-toggle" onclick="toggleJsonNode(this)">
                    <i class="fa-solid fa-chevron-down json-toggle-icon"></i>
                    <span class="json-key">${escapeHtml(key)}</span>
                    <span class="json-count">[ ${count} items ]</span>
                </div>
                <div class="json-children">${childrenHtml}</div>
            </div>`;
    }

    if (type === 'object') {
        const keys = Object.keys(val);
        if (keys.length === 0) {
            return `<div class="json-node ${isRoot ? 'json-node-root' : ''}"><span class="json-key">${escapeHtml(key)}:</span> {}</div>`;
        }
        let childrenHtml = keys.map(k => createJsonNodeHtml(val[k], k, false)).join('');
        return `
            <div class="json-node ${isRoot ? 'json-node-root' : ''}">
                <div class="json-toggle" onclick="toggleJsonNode(this)">
                    <i class="fa-solid fa-chevron-down json-toggle-icon"></i>
                    <span class="json-key">${escapeHtml(key)}</span>
                    <span class="json-count">{ ${keys.length} keys }</span>
                </div>
                <div class="json-children">${childrenHtml}</div>
            </div>`;
    }
    return '';
}

function toggleJsonNode(el) {
    const parent = el.closest('.json-node');
    if (parent) parent.classList.toggle('collapsed');
}

function toggleJsonTreeExpand(expand) {
    const container = document.getElementById('interactiveJsonTree');
    if (!container) return;
    const nodes = container.querySelectorAll('.json-node');
    nodes.forEach(node => {
        if (expand) node.classList.remove('collapsed');
        else node.classList.add('collapsed');
    });
}

/* ==========================================================================
   FORMATTED VIEW ZOOM & FIT
   ========================================================================== */

let formattedZoomLevel = 1.0;

function zoomFormattedSheet(factor) {
    const sheet = document.getElementById('formattedDocumentSheet');
    const label = document.getElementById('formattedZoomLevel');
    if (!sheet) return;
    if (factor === 1.0) formattedZoomLevel = 1.0;
    else formattedZoomLevel = Math.max(0.4, Math.min(2.5, formattedZoomLevel * factor));
    sheet.style.transform = `scale(${formattedZoomLevel})`;
    if (label) label.textContent = `${Math.round(formattedZoomLevel * 100)}%`;
}

function fitFormattedSheet(mode) {
    const sheet = document.getElementById('formattedDocumentSheet');
    const viewport = document.getElementById('formattedVisualViewport');
    const label = document.getElementById('formattedZoomLevel');
    if (!sheet || !viewport) return;

    if (mode === 'width') {
        const vpWidth = viewport.clientWidth - 48;
        const sheetWidth = 820;
        formattedZoomLevel = Math.min(1.5, Math.max(0.5, vpWidth / sheetWidth));
    } else if (mode === 'page') {
        formattedZoomLevel = 0.85;
    }
    sheet.style.transform = `scale(${formattedZoomLevel})`;
    if (label) label.textContent = `${Math.round(formattedZoomLevel * 100)}%`;
}

/* ==========================================================================
   DOCUMENT PREVIEW ZOOM & FIT
   ========================================================================== */

let docPreviewZoom = 1.0;

function zoomDocImg(scale) {
    const img = document.getElementById('docPreviewImage');
    if (!img) return;
    docPreviewZoom = Math.max(0.5, Math.min(3.0, docPreviewZoom * scale));
    img.style.transform = `scale(${docPreviewZoom})`;
}

function resetDocImg() {
    const img = document.getElementById('docPreviewImage');
    if (!img) return;
    docPreviewZoom = 1.0;
    img.style.transform = 'scale(1.0)';
}

function fitDocPreview(mode) {
    const img = document.getElementById('docPreviewImage');
    const container = document.getElementById('docPreviewContainer');
    if (!img || !container) return;
    if (mode === 'width') {
        docPreviewZoom = (container.clientWidth - 40) / (img.naturalWidth || 800);
    } else {
        docPreviewZoom = 1.0;
    }
    img.style.transform = `scale(${Math.max(0.4, Math.min(2.0, docPreviewZoom))})`;
}

/* ==========================================================================
   UNIFIED FULL VIEW MODAL CONTROLLER
   ========================================================================== */

function openFullViewModal(type) {
    const modal = document.getElementById('fullViewModal');
    const title = document.getElementById('fullViewModalTitle');
    const icon = document.getElementById('fullViewModalIcon');
    const body = document.getElementById('fullViewModalBody');
    const actions = document.getElementById('fullViewModalCustomActions');

    if (!modal || !body) return;

    actions.innerHTML = '';
    const job = getJobData() || {};

    if (type === 'json') {
        if (title) title.textContent = 'Structured JSON';
        if (icon) icon.className = 'fa-solid fa-code';
        
        let jsonStr = '';
        const jsonBlock = document.getElementById('jsonCodeBlock');
        if (jsonBlock) jsonStr = jsonBlock.textContent;

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="toggleJsonTreeExpand(true)"><i class="fa-solid fa-folder-open"></i> Expand All</button>
            <button class="btn btn-outline btn-sm" onclick="toggleJsonTreeExpand(false)"><i class="fa-solid fa-folder"></i> Collapse All</button>
            <button class="btn btn-outline btn-sm" onclick="copyJsonOutput()"><i class="fa-solid fa-copy"></i> Copy</button>
            <button class="btn btn-primary btn-sm" data-export-format="json" onclick="triggerDirectDownload('json', this)"><i class="fa-solid fa-download"></i> Download</button>
        `;

        body.innerHTML = `
            <div style="background: var(--code-bg, #0f172a); padding: 20px; border-radius: 8px; border: 1px solid var(--card-border); min-height: 100%;">
                <div id="modalJsonTree" class="json-tree-container"></div>
            </div>
        `;
        try {
            const dataObj = JSON.parse(jsonStr);
            renderInteractiveJsonTree(dataObj, 'modalJsonTree');
        } catch(e) {
            document.getElementById('modalJsonTree').innerHTML = `<pre style="white-space: pre-wrap; color: var(--text-main);">${escapeHtml(jsonStr)}</pre>`;
        }
    }
    else if (type === 'rawText') {
        if (title) title.textContent = 'Raw Extractor (Text)';
        if (icon) icon.className = 'fa-solid fa-align-left';
        
        const rawTextBlock = document.getElementById('rawExtractedTextBlock');
        const rawText = rawTextBlock ? rawTextBlock.textContent : (job.raw_text || '');

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="copyRawExtractedText()"><i class="fa-solid fa-copy"></i> Copy</button>
            <button class="btn btn-primary btn-sm" data-export-format="txt" onclick="triggerDirectDownload('txt', this)"><i class="fa-solid fa-download"></i> Download</button>
        `;

        body.innerHTML = `
            <div class="code-panel" style="min-height: 100%;">
                <div class="code-body" style="padding: 24px;">
                    <pre style="white-space: pre-wrap; font-family: var(--font-code); font-size: 0.95rem; line-height: 1.6; color: var(--code-text, #e2e8f0); margin: 0;">${escapeHtml(rawText)}</pre>
                </div>
            </div>
        `;
    }
    else if (type === 'formattedView') {
        if (title) title.textContent = 'Formatted View';
        if (icon) icon.className = 'fa-solid fa-newspaper';

        const sheet = document.getElementById('formattedDocumentSheet');
        const sheetHtml = sheet ? sheet.innerHTML : (job.formatted_html || job.display_formatted_html || '');

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="printFormattedDocument()"><i class="fa-solid fa-print"></i> Print</button>
            <button class="btn btn-primary btn-sm" data-export-format="pdf" onclick="triggerDirectDownload('pdf', this)"><i class="fa-solid fa-file-pdf"></i> Export PDF</button>
        `;

        body.innerHTML = `
            <div style="background: var(--background-alt, #f1f5f9); padding: 40px 20px; border-radius: 8px; text-align: center; overflow: auto; min-height: 100%;">
                <div class="formatted-document-sheet" style="margin: 0 auto; box-shadow: 0 10px 25px rgba(0,0,0,0.15);">
                    ${sheetHtml}
                </div>
            </div>
        `;
    }
    else if (type === 'preview') {
        if (title) title.textContent = 'Document Preview';
        if (icon) icon.className = 'fa-solid fa-image';

        const previewContainer = document.getElementById('docPreviewContainer');
        const containerInner = previewContainer ? previewContainer.innerHTML : '';

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="zoomDocImg(0.8)"><i class="fa-solid fa-magnifying-glass-minus"></i> Zoom -</button>
            <button class="btn btn-outline btn-sm" onclick="zoomDocImg(1.2)"><i class="fa-solid fa-magnifying-glass-plus"></i> Zoom +</button>
            <button class="btn btn-outline btn-sm" onclick="fitDocPreview('width')"><i class="fa-solid fa-arrows-left-right"></i> Fit Width</button>
            <button class="btn btn-outline btn-sm" onclick="resetDocImg()"><i class="fa-solid fa-rotate-left"></i> Reset</button>
        `;

        body.innerHTML = `
            <div style="background: #1e1e1e; padding: 24px; border-radius: 8px; text-align: center; height: 100%; display: flex; align-items: center; justify-content: center; overflow: auto;">
                <div style="max-width: 100%; max-height: 100%;">
                    ${containerInner}
                </div>
            </div>
        `;
    }
    else if (type === 'summary') {
        if (title) title.textContent = 'AI Summary & Findings';
        if (icon) icon.className = 'fa-solid fa-sparkles';

        const narrative = document.getElementById('summaryNarrativePanel');
        const findings = document.getElementById('summaryFindingsPanel');

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="copySummaryText()"><i class="fa-solid fa-copy"></i> Copy Summary</button>
            <button class="btn btn-primary btn-sm" data-export-format="json" onclick="triggerDirectDownload('json', this)"><i class="fa-solid fa-download"></i> Download JSON</button>
        `;

        body.innerHTML = `
            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 24px;" class="results-responsive-grid">
                <div class="saas-card" style="padding: 24px;">
                    <h4 style="margin-bottom: 14px; color: var(--text-main);"><i class="fa-solid fa-wand-magic-sparkles" style="color: var(--primary);"></i> Factual Narrative Summary</h4>
                    <div style="line-height: 1.7; color: var(--text-main);">${narrative ? narrative.innerHTML : ''}</div>
                </div>
                <div class="saas-card" style="padding: 24px;">
                    <h4 style="margin-bottom: 14px; color: var(--text-main);"><i class="fa-solid fa-list-check" style="color: var(--success);"></i> Key Findings & Details</h4>
                    <div>${findings ? findings.innerHTML : ''}</div>
                </div>
            </div>
        `;
    }
    else if (type === 'tables') {
        if (title) title.textContent = 'Extracted Tables';
        if (icon) icon.className = 'fa-solid fa-table';

        const tablesCont = document.getElementById('tablesContainer');

        actions.innerHTML = `
            <button class="btn btn-outline btn-sm" onclick="copyTablesData()"><i class="fa-solid fa-copy"></i> Copy Tables</button>
            <button class="btn btn-primary btn-sm" data-export-format="csv" onclick="triggerDirectDownload('csv', this)"><i class="fa-solid fa-file-csv"></i> Export CSV</button>
        `;

        body.innerHTML = `
            <div style="padding: 12px;">
                ${tablesCont ? tablesCont.innerHTML : '<p>No tables detected.</p>'}
            </div>
        `;
    }

    modal.style.display = 'flex';
    document.body.style.overflow = 'hidden';
}

function closeFullViewModal() {
    const modal = document.getElementById('fullViewModal');
    if (modal) {
        modal.style.display = 'none';
        document.body.style.overflow = '';
    }
}

function handleFullViewBackdropClick(e) {
    if (e.target.id === 'fullViewModal') {
        closeFullViewModal();
    }
}

document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeFullViewModal();
    }
});
