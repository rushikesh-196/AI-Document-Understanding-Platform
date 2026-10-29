/* ==========================================================================
   AI Document Intelligence Platform — Upload, Queue & Lightbox JS
   ========================================================================== */

let batchQueue = [];        // [{ file, id, status, objectURL, dataURL }]
let currentProcessingIndex = 0;
let lightboxZoom = 1;

// ─── INIT ─────────────────────────────────────────────────────────────────────
document.addEventListener("DOMContentLoaded", () => {
    const dropzone = document.getElementById("uploadDropzone");
    const fileInput = document.getElementById("fileInput");
    const extractBtn = document.getElementById("extractBtn");

    if (!dropzone) return;

    // Drag events
    ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(ev => {
        dropzone.addEventListener(ev, e => { e.preventDefault(); e.stopPropagation(); });
    });
    ['dragenter', 'dragover'].forEach(ev => dropzone.addEventListener(ev, () => dropzone.classList.add('dragover')));
    ['dragleave', 'drop'].forEach(ev => dropzone.addEventListener(ev, () => dropzone.classList.remove('dragover')));

    dropzone.addEventListener('drop', e => { if (e.dataTransfer.files.length) handleFiles(e.dataTransfer.files); });
    dropzone.addEventListener('click', e => {
        if (e.target.tagName !== 'BUTTON' && e.target.tagName !== 'INPUT') fileInput.click();
    });
    fileInput.addEventListener('change', e => { if (e.target.files.length) handleFiles(e.target.files); });

    if (extractBtn) extractBtn.addEventListener('click', startBatchExtraction);

    // Close lightbox on Escape key
    document.addEventListener('keydown', e => { if (e.key === 'Escape') closeLightbox(); });
});

// ─── FILE HANDLING ─────────────────────────────────────────────────────────────
function handleFiles(files) {
    const promises = [];
    for (let i = 0; i < files.length; i++) {
        const file = files[i];
        const ext = file.name.split('.').pop().toLowerCase();
        const isImage = ['png', 'jpg', 'jpeg', 'webp', 'bmp', 'gif', 'tiff'].includes(ext);

        const item = {
            file,
            id: 'q_' + Date.now() + '_' + i,
            status: 'pending',
            objectURL: URL.createObjectURL(file),
            dataURL: null,
            isImage
        };
        batchQueue.push(item);

        if (isImage) {
            const p = readFileAsDataURL(file).then(dataURL => { item.dataURL = dataURL; });
            promises.push(p);
        }
    }
    // Wait for all DataURLs to be read before rendering
    Promise.all(promises).then(renderBatchQueue);
}

function readFileAsDataURL(file) {
    return new Promise(resolve => {
        const reader = new FileReader();
        reader.onload = e => resolve(e.target.result);
        reader.readAsDataURL(file);
    });
}

// ─── QUEUE RENDERING ───────────────────────────────────────────────────────────
function renderBatchQueue() {
    const container = document.getElementById("batchQueueContainer");
    const list = document.getElementById("batchQueueList");
    const countEl = document.getElementById("batchQueueCount");
    const extractBtn = document.getElementById("extractBtn");

    if (batchQueue.length === 0) {
        container.style.display = "none";
        extractBtn.disabled = true;
        return;
    }

    container.style.display = "block";
    countEl.textContent = batchQueue.length;
    const pendingCount = batchQueue.filter(i => i.status === 'pending').length;
    extractBtn.disabled = pendingCount === 0;

    list.innerHTML = batchQueue.map(item => buildQueueCard(item)).join('');

    // Animate each card in with staggered delay
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        list.querySelectorAll('.queue-card').forEach((card, idx) => {
            card.style.opacity = '0';
            card.style.transform = 'translateY(10px)';
            card.style.transition = `opacity 0.3s ease ${idx * 55}ms, transform 0.3s cubic-bezier(0.22,1,0.36,1) ${idx * 55}ms`;
            requestAnimationFrame(() => {
                card.style.opacity = '1';
                card.style.transform = 'translateY(0)';
            });
        });
    }
}

function buildQueueCard(item) {
    const ext = item.file.name.split('.').pop().toLowerCase();
    const sizeStr = formatFileSize(item.file.size);

    // ── Thumbnail ────────────────────────────────────────────
    let thumbHtml;
    if (item.isImage && item.dataURL) {
        thumbHtml = `
        <div class="queue-thumb" title="View Full Image" onclick="openLightbox('${item.id}')">
            <img src="${item.dataURL}" alt="${escHtml(item.file.name)}" loading="lazy">
            <div class="thumb-view-btn"><i class="fa-solid fa-up-right-and-down-left-from-center"></i></div>
        </div>`;
    } else {
        // Icon fallback for PDF / DOCX / others
        let iconClass = 'fa-file';
        let iconColor = 'var(--text-muted)';
        if (ext === 'pdf') { iconClass = 'fa-file-pdf'; iconColor = 'var(--danger)'; }
        else if (ext === 'docx' || ext === 'doc') { iconClass = 'fa-file-word'; iconColor = 'var(--primary)'; }
        thumbHtml = `
        <div class="queue-thumb">
            <i class="fa-solid ${iconClass} thumb-icon" style="color:${iconColor};"></i>
        </div>`;
    }

    // ── Status badge ─────────────────────────────────────────
    const statusBadges = {
        pending:    `<span class="badge badge-primary" style="text-transform:none;font-size:0.78rem;">Pending</span>`,
        processing: `<span class="badge badge-warning" style="text-transform:none;font-size:0.78rem;"><i class="fa-solid fa-circle-notch fa-spin"></i> Processing</span>`,
        success:    `<span class="badge badge-success" style="text-transform:none;font-size:0.78rem;"><i class="fa-solid fa-circle-check"></i> Done</span>`,
        error:      `<span class="badge badge-danger"  style="text-transform:none;font-size:0.78rem;"><i class="fa-solid fa-xmark"></i> Failed</span>`
    };
    const badge = statusBadges[item.status] || statusBadges.pending;

    // ── View Full button (images only) ───────────────────────
    const viewBtn = item.isImage && item.dataURL
        ? `<button class="btn btn-outline btn-sm" onclick="openLightbox('${item.id}')" title="View Full Image" style="font-size:0.78rem;padding:4px 10px;">
               <i class="fa-solid fa-eye"></i> View
           </button>`
        : '';

    const removeDisabled = item.status === 'processing' ? 'disabled' : '';

    return `
    <div class="queue-card" id="card_${item.id}">
        ${thumbHtml}
        <div class="queue-info">
            <div class="queue-filename" title="${escHtml(item.file.name)}">${escHtml(item.file.name)}</div>
            <div class="queue-meta">
                <small style="color:var(--text-muted);">${sizeStr}</small>
                ${badge}
            </div>
            ${viewBtn ? `<div style="margin-top:4px;">${viewBtn}</div>` : ''}
        </div>
        <div class="queue-actions">
            <button class="btn btn-outline btn-sm" style="padding:5px 9px;font-size:0.82rem;"
                onclick="removeQueueItem('${item.id}')" title="Remove" ${removeDisabled}>
                <i class="fa-solid fa-xmark"></i>
            </button>
        </div>
    </div>`;
}

function removeQueueItem(id) {
    const item = batchQueue.find(i => i.id === id);
    const card = document.getElementById(`card_${id}`);

    if (card && !window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        card.style.transition = 'opacity 0.22s ease, transform 0.22s ease';
        card.style.opacity = '0';
        card.style.transform = 'translateX(16px) scale(0.97)';
        setTimeout(() => {
            if (item && item.objectURL) URL.revokeObjectURL(item.objectURL);
            batchQueue = batchQueue.filter(i => i.id !== id);
            renderBatchQueue();
        }, 230);
    } else {
        if (item && item.objectURL) URL.revokeObjectURL(item.objectURL);
        batchQueue = batchQueue.filter(i => i.id !== id);
        renderBatchQueue();
    }
}

function clearBatchQueue() {
    if (batchQueue.some(i => i.status === 'processing')) { showUploadError("Cannot clear while processing."); return; }
    batchQueue.forEach(i => { if (i.objectURL) URL.revokeObjectURL(i.objectURL); });
    batchQueue = [];
    document.getElementById("fileInput").value = "";
    renderBatchQueue();
}

// ─── LIGHTBOX ──────────────────────────────────────────────────────────────────
function openLightbox(itemId) {
    const item = batchQueue.find(i => i.id === itemId);
    if (!item || !item.dataURL) return;
    lightboxZoom = 1;
    const lb = document.getElementById("imgLightbox");
    const img = document.getElementById("lightboxImg");
    img.src = item.dataURL;
    img.alt = item.file.name;
    img.style.transform = `scale(${lightboxZoom})`;
    lb.classList.add("open");
    document.body.style.overflow = "hidden";
}

function closeLightbox() {
    document.getElementById("imgLightbox").classList.remove("open");
    document.body.style.overflow = "";
}

function closeLightboxOnBackdrop(e) {
    if (e.target === document.getElementById("imgLightbox")) closeLightbox();
}

function lbZoom(factor) {
    lightboxZoom = Math.min(Math.max(lightboxZoom * factor, 0.25), 6);
    document.getElementById("lightboxImg").style.transform = `scale(${lightboxZoom})`;
}

function lbResetZoom() {
    lightboxZoom = 1;
    document.getElementById("lightboxImg").style.transform = `scale(1)`;
}

// ─── HELPERS ───────────────────────────────────────────────────────────────────
function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + " B";
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + " KB";
    return (bytes / 1048576).toFixed(1) + " MB";
}

function escHtml(str) {
    return String(str)
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function showUploadError(message) {
    const errorBox = document.getElementById("uploadErrorMessage");
    if (!errorBox) return;
    if (message) { errorBox.textContent = message; errorBox.style.display = "block"; }
    else { errorBox.textContent = ""; errorBox.style.display = "none"; }
}

// ─── PIPELINE STAGE STEPPER ────────────────────────────────────────────────────
function updatePipelineStage(percent, message) {
    const progressFill    = document.getElementById("progressFill");
    const progressPercent = document.getElementById("progressPercent");
    const progressStatus  = document.getElementById("progressStatus");

    if (progressFill)    progressFill.style.width = `${percent}%`;
    if (progressPercent) progressPercent.textContent = `${percent}%`;
    if (progressStatus)  progressStatus.textContent = message || "Processing your document...";

    const stages = [
        { id: "stage1", min: 1  },
        { id: "stage2", min: 25 },
        { id: "stage3", min: 50 },
        { id: "stage4", min: 70 },
        { id: "stage5", min: 85 },
        { id: "stage6", min: 98 }
    ];

    stages.forEach(st => {
        const el = document.getElementById(st.id);
        if (el) {
            if (percent >= st.min) {
                el.classList.add("active");
                if (percent > st.min + 12) el.classList.add("completed");
            } else {
                el.classList.remove("active", "completed");
            }
        }
    });
}

// ─── BATCH PROCESSING ──────────────────────────────────────────────────────────
function startBatchExtraction() {
    showUploadError("");
    const pendingItems = batchQueue.filter(i => i.status === 'pending');
    if (pendingItems.length === 0) { showUploadError("No pending documents in the queue."); return; }

    const extractBtn = document.getElementById("extractBtn");
    extractBtn.disabled = true;
    extractBtn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing…';
    // Show AI processing dots in button while batch runs
    if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
        extractBtn.innerHTML = `<i class="fa-solid fa-circle-notch fa-spin"></i> Processing <span class="ai-processing-dots" style="display:inline-flex;margin-left:4px;"><span></span><span></span><span></span></span>`;
    }

    currentProcessingIndex = batchQueue.findIndex(i => i.status === 'pending');
    processNextFile();
}

/** After all files in the batch are done, decide where to navigate. */
function onBatchComplete(lastSuccessJobId) {
    // ── ALWAYS go to Results for the last successfully processed doc ──────────
    if (lastSuccessJobId) {
        showToast("Document processed! Loading results…", "success");
        setTimeout(() => { window.location.href = `/results/${lastSuccessJobId}`; }, 900);
    } else {
        // Every file failed – reset the UI so the user can retry
        showBatchError("All documents failed to process. Please check your files and try again.");
        resetExtractBtn();
    }
}

function resetExtractBtn() {
    const btn = document.getElementById("extractBtn");
    if (btn) { btn.disabled = false; btn.innerHTML = '<i class="fa-solid fa-wand-magic-sparkles"></i> Process Batch with AI'; }
}

function showBatchError(msg) {
    showUploadError("");
    // Inject a persistent error + retry card above the extract button
    const existing = document.getElementById("batchErrorCard");
    if (existing) existing.remove();
    const card = document.createElement("div");
    card.id = "batchErrorCard";
    card.style.cssText = "background:var(--danger-bg);border:1px solid var(--danger);border-radius:var(--radius-sm);padding:14px 18px;margin-bottom:16px;display:flex;align-items:center;justify-content:space-between;gap:12px;";
    card.innerHTML = `
        <div style="display:flex;align-items:center;gap:10px;">
            <i class="fa-solid fa-circle-xmark" style="color:var(--danger);font-size:1.2rem;"></i>
            <span style="color:var(--text-main);font-size:0.92rem;">${msg}</span>
        </div>
        <button class="btn btn-outline btn-sm" onclick="retryFailedFiles()">
            <i class="fa-solid fa-rotate-right"></i> Retry Failed
        </button>`;
    const extractBtn = document.getElementById("extractBtn");
    extractBtn.parentNode.insertBefore(card, extractBtn);
}

function retryFailedFiles() {
    const existing = document.getElementById("batchErrorCard");
    if (existing) existing.remove();
    // Reset failed items back to pending
    batchQueue.forEach(i => { if (i.status === 'error') i.status = 'pending'; });
    renderBatchQueue();
    // Restart processing
    currentProcessingIndex = batchQueue.findIndex(i => i.status === 'pending');
    const btn = document.getElementById("extractBtn");
    if (btn) { btn.disabled = true; btn.innerHTML = '<i class="fa-solid fa-circle-notch fa-spin"></i> Processing…'; }
    processNextFile();
}

function processNextFile(lastSuccessJobId = null) {
    // Find the next pending item
    const nextPending = batchQueue.slice(currentProcessingIndex).findIndex(i => i.status === 'pending');
    if (nextPending === -1) {
        // No more pending items – batch is done
        onBatchComplete(lastSuccessJobId);
        return;
    }
    currentProcessingIndex += nextPending;

    const currentItem = batchQueue[currentProcessingIndex];
    if (!currentItem) { onBatchComplete(lastSuccessJobId); return; }

    currentItem.status = 'processing';
    renderBatchQueue();

    const selectedLanguage = document.getElementById("langSelect")?.value || "en";
    const engine = document.getElementById("engineSelect")?.value || "auto";

    const formData = new FormData();
    formData.append("file", currentItem.file);
    formData.append("engine", engine);
    formData.append("language", selectedLanguage);

    const progressContainer = document.getElementById("progressContainer");
    if (progressContainer) {
        progressContainer.style.display = 'block';
        // Animate container into view
        if (!window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
            progressContainer.style.opacity = '0';
            progressContainer.style.transform = 'translateY(8px)';
            progressContainer.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
            requestAnimationFrame(() => {
                progressContainer.style.opacity = '1';
                progressContainer.style.transform = 'translateY(0)';
            });
        }
    }
    updatePipelineStage(10, `Uploading "${currentItem.file.name}"…`);

    fetch('/api/v1/extract', { method: 'POST', body: formData })
        .then(res => { if (!res.ok) throw new Error(`Server error ${res.status}`); return res.json(); })
        .then(data => {
            if (!data.success) throw new Error(data.message || "Upload rejected by server.");
            const jobId = data.job_id;

            const poll = setInterval(() => {
                fetch(`/api/v1/progress/${jobId}`)
                    .then(r => r.json())
                    .then(prog => {
                        const pct = prog.percent || 15;
                        updatePipelineStage(pct, `"${currentItem.file.name}" — ${prog.message || "Running AI extraction…"}`);

                        if (prog.status === 'completed') {
                            clearInterval(poll);
                            updatePipelineStage(100, "Extraction complete! Saving result…");

                            // Save to history in background; then navigate to RESULTS PAGE
                            fetch(`/api/v1/result/${jobId}`)
                                .then(r => r.json())
                                .then(resData => {
                                    const jobObj = resData.raw_json || resData.data || resData;
                                    if (typeof AuthManager !== 'undefined') AuthManager.saveJobToHistory(jobObj);
                                })
                                .catch(() => {})
                                .finally(() => {
                                    currentItem.status = 'success';
                                    renderBatchQueue();
                                    // Animate success card
                                    const successCard = document.getElementById(`card_${currentItem.id}`);
                                    if (successCard) {
                                        successCard.style.animation = 'successPop 0.4s cubic-bezier(0.22, 1, 0.36, 1)';
                                        setTimeout(() => { successCard.style.animation = ''; }, 450);
                                    }
                                    // For single-file mode → redirect to results immediately
                                    // For batch → continue processing rest, then redirect to results of last success
                                    const remaining = batchQueue.filter(i => i.status === 'pending');
                                    if (remaining.length === 0) {
                                        onBatchComplete(jobId);
                                    } else {
                                        currentProcessingIndex++;
                                        setTimeout(() => processNextFile(jobId), 700);
                                    }
                                });

                        } else if (prog.status === 'failed') {
                            clearInterval(poll);
                            currentItem.status = 'error';
                            currentItem.errorMsg = prog.error || prog.message || "Processing failed";
                            renderBatchQueue();
                            // Animate error card
                            const errCard = document.getElementById(`card_${currentItem.id}`);
                            if (errCard) {
                                errCard.style.animation = 'errorShake 0.45s ease';
                                setTimeout(() => { errCard.style.animation = ''; }, 500);
                            }
                            currentProcessingIndex++;
                            // Show error inline; keep going with remaining files
                            showToast(`"${currentItem.file.name}" failed: ${currentItem.errorMsg}`, "error");
                            setTimeout(() => processNextFile(lastSuccessJobId), 700);
                        }
                    })
                    .catch(err => {
                        clearInterval(poll);
                        currentItem.status = 'error';
                        renderBatchQueue();
                        currentProcessingIndex++;
                        showToast(`Poll error for "${currentItem.file.name}": ${err.message}`, "error");
                        setTimeout(() => processNextFile(lastSuccessJobId), 700);
                    });
            }, 400);
        })
        .catch(err => {
            currentItem.status = 'error';
            renderBatchQueue();
            currentProcessingIndex++;
            showToast(`Upload failed: ${err.message}`, "error");
            showBatchError(`"${currentItem.file.name}" could not be uploaded. Check the file and try again.`);
            resetExtractBtn();
        });
}
