/* ==========================================================================
   AI Document Intelligence Platform — animations.js
   Self-contained animation controller. Non-invasive — only adds CSS classes.
   No modifications to existing functionality, routing, or API calls.
   ========================================================================== */

(function () {
    'use strict';

    const prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    /* ── 1. PAGE LOAD ──────────────────────────────────────────────────────── */
    function initPageLoad() {
        // Body fades in on DOMContentLoaded
        document.body.classList.add('page-loaded');
    }

    /* ── 2. SCROLL-REVEAL (IntersectionObserver) ───────────────────────────── */
    function initScrollReveal() {
        if (prefersReducedMotion) return;

        const revealSelectors = [
            '.reveal', '.reveal-left', '.reveal-right', '.reveal-scale'
        ];

        const targets = document.querySelectorAll(revealSelectors.join(','));
        if (!targets.length) return;

        const observer = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    entry.target.classList.add('visible');
                    observer.unobserve(entry.target); // fire once
                }
            });
        }, {
            threshold: 0.1,
            rootMargin: '0px 0px -40px 0px'
        });

        targets.forEach(el => observer.observe(el));
    }

    /* ── 3. AUTO-MARK REVEAL ELEMENTS ─────────────────────────────────────── */
    function autoRevealSections() {
        if (prefersReducedMotion) return;

        // Sections that should fade in on scroll
        const sectionSelectors = [
            '.features-section .features-grid',
            '.how-it-works-section .steps-grid',
            '.benefits-section .benefits-grid',
            '.document-types-section .document-types-layout',
            '.home-section .section-header',
            '.cta-section .cta-card',
            '.metrics-grid',
            '.action-cards-grid',
            '.upload-card',
            '.results-header-card',
            '.results-tab-card',
            '.settings-section',
            '.history-card',
        ];

        sectionSelectors.forEach(selector => {
            document.querySelectorAll(selector).forEach(el => {
                if (!el.classList.contains('reveal') && !el.classList.contains('reveal-left')) {
                    el.classList.add('reveal');
                }
            });
        });

        // Grid items inside stagger parents
        const staggerParents = document.querySelectorAll(
            '.features-grid, .steps-grid, .benefits-grid, .metrics-grid, .action-cards-grid, .entity-cards-grid'
        );

        staggerParents.forEach(parent => {
            parent.classList.add('stagger-children');
            Array.from(parent.children).forEach(child => {
                if (!child.classList.contains('reveal')) {
                    child.classList.add('reveal');
                }
            });
        });
    }

    /* ── 4. ANIMATED COUNTERS ──────────────────────────────────────────────── */
    function initCounterAnimations() {
        if (prefersReducedMotion) return;

        const counters = document.querySelectorAll('.metric-val[data-target]');
        if (!counters.length) return;

        const counterObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    animateCounter(entry.target);
                    counterObserver.unobserve(entry.target);
                }
            });
        }, { threshold: 0.5 });

        counters.forEach(el => counterObserver.observe(el));
    }

    function animateCounter(el) {
        const target = parseFloat(el.dataset.target) || 0;
        const suffix = el.dataset.suffix || '';
        const prefix = el.dataset.prefix || '';
        const isDecimal = String(target).includes('.');
        const duration = 1200;
        const startTime = performance.now();

        function tick(now) {
            const elapsed = now - startTime;
            const progress = Math.min(elapsed / duration, 1);
            // ease-out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = target * eased;
            el.textContent = prefix + (isDecimal ? current.toFixed(1) : Math.round(current)) + suffix;
            if (progress < 1) requestAnimationFrame(tick);
        }

        requestAnimationFrame(tick);
    }

    /* ── 5. AUTO-ASSIGN data-target TO METRIC VALUES ──────────────────────── */
    function autoAssignCounters() {
        if (prefersReducedMotion) return;

        document.querySelectorAll('.metric-val').forEach(el => {
            if (el.dataset.target) return; // already set in template
            const text = el.textContent.trim();
            // Match patterns like: "42", "1,234", "98.5", "98.5%", "$1,234"
            const match = text.match(/^([^0-9]*)([0-9,]+\.?[0-9]*)([^0-9]*)$/);
            if (match) {
                const prefix = match[1] || '';
                const numStr = (match[2] || '0').replace(/,/g, '');
                const suffix = match[3] || '';
                const num = parseFloat(numStr);
                if (!isNaN(num) && num > 0 && num < 100000) {
                    el.dataset.target = num;
                    if (prefix) el.dataset.prefix = prefix;
                    if (suffix) el.dataset.suffix = suffix;
                    el.textContent = prefix + '0' + suffix;
                }
            }
        });
    }

    /* ── 6. NAVBAR SCROLL SHADOW ───────────────────────────────────────────── */
    function initNavbarScroll() {
        const navbar = document.querySelector('.navbar-header');
        if (!navbar) return;

        let ticking = false;
        window.addEventListener('scroll', () => {
            if (!ticking) {
                requestAnimationFrame(() => {
                    if (window.scrollY > 20) {
                        navbar.classList.add('scrolled');
                    } else {
                        navbar.classList.remove('scrolled');
                    }
                    ticking = false;
                });
                ticking = true;
            }
        }, { passive: true });
    }

    /* ── 7. BUTTON RIPPLE EFFECT ───────────────────────────────────────────── */
    function initRippleButtons() {
        if (prefersReducedMotion) return;

        document.addEventListener('click', (e) => {
            const btn = e.target.closest('.btn');
            if (!btn) return;

            const rect = btn.getBoundingClientRect();
            const size = Math.max(rect.width, rect.height) * 2;
            const x = e.clientX - rect.left - size / 2;
            const y = e.clientY - rect.top - size / 2;

            const ripple = document.createElement('span');
            ripple.className = 'btn-ripple';
            ripple.style.cssText = `
                width: ${size}px;
                height: ${size}px;
                left: ${x}px;
                top: ${y}px;
            `;

            btn.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    }

    /* ── 8. ENHANCED TOAST EXIT ────────────────────────────────────────────── */
    function initToastEnhancement() {
        // Override showToast exit to use CSS class instead of inline styles
        const originalShowToast = window.showToast;
        if (!originalShowToast) return;

        window.showToast = function (message, type = 'success', title = '') {
            const container = document.getElementById('toastContainer') ||
                (() => {
                    const c = document.createElement('div');
                    c.id = 'toastContainer';
                    c.className = 'toast-container';
                    document.body.appendChild(c);
                    return c;
                })();

            const iconMap = {
                success: 'fa-solid fa-circle-check',
                error: 'fa-solid fa-circle-xmark',
                warning: 'fa-solid fa-triangle-exclamation',
                info: 'fa-solid fa-circle-info'
            };
            const titleMap = { success: 'Success', error: 'Error', warning: 'Attention', info: 'Notice' };

            const toast = document.createElement('div');
            toast.className = `toast toast-${type}`;
            toast.innerHTML = `
                <i class="${iconMap[type] || iconMap.info} toast-icon"></i>
                <div class="toast-content">
                    <div class="toast-title">${title || titleMap[type] || 'Notice'}</div>
                    <div class="toast-msg">${message}</div>
                </div>
                <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
            `;

            container.appendChild(toast);

            // Animate out with CSS class
            setTimeout(() => {
                if (toast.parentElement) {
                    toast.classList.add('toast-exit');
                    setTimeout(() => toast.remove(), 300);
                }
            }, 4200);
        };
    }

    /* ── 9. QUEUE CARD ANIMATION (Upload Page) ─────────────────────────────── */
    function initQueueCardAnimations() {
        // Observe the batch queue list and animate new children
        const list = document.getElementById('batchQueueList');
        if (!list) return;

        const mutationObserver = new MutationObserver((mutations) => {
            mutations.forEach(mutation => {
                mutation.addedNodes.forEach((node, idx) => {
                    if (node.nodeType === 1) {
                        if (prefersReducedMotion) return;
                        node.style.animationDelay = `${idx * 60}ms`;
                        node.classList.add('queue-card-anim');
                    }
                });
            });
        });

        mutationObserver.observe(list, { childList: true });
    }

    /* ── 10. EMPTY STATE ANIMATION ─────────────────────────────────────────── */
    function initEmptyStateAnimations() {
        // Add floating icon class if icon exists in empty state
        document.querySelectorAll('.results-empty-state, .empty-state').forEach(el => {
            const icon = el.querySelector('i, .fa, svg');
            if (icon) icon.classList.add('empty-state-icon');
        });
    }

    /* ── 11. SUCCESS/ERROR FEEDBACK ─────────────────────────────────────────── */
    window.animateSuccess = function (el) {
        if (!el || prefersReducedMotion) return;
        el.classList.remove('anim-error');
        el.classList.add('anim-success');
        setTimeout(() => el.classList.remove('anim-success'), 500);
    };

    window.animateError = function (el) {
        if (!el || prefersReducedMotion) return;
        el.classList.remove('anim-success');
        el.classList.add('anim-error');
        setTimeout(() => el.classList.remove('anim-error'), 500);
    };

    /* ── 12. SKELETON HELPERS (Public API) ────────────────────────────────── */
    window.showSkeleton = function (container, rows = 3) {
        if (!container) return;
        container.innerHTML = Array.from({ length: rows }, () => `
            <div class="skeleton-card">
                <div style="display:flex;gap:12px;align-items:center;">
                    <div class="skeleton-circle"></div>
                    <div style="flex:1;">
                        <div class="skeleton-text" style="width:60%;margin-bottom:8px;height:14px;border-radius:4px;"></div>
                        <div class="skeleton-text w-3/4" style="width:80%;height:12px;border-radius:4px;"></div>
                    </div>
                </div>
                <div class="skeleton-text" style="width:100%;height:12px;border-radius:4px;"></div>
                <div class="skeleton-text w-3/4" style="width:75%;height:12px;border-radius:4px;"></div>
            </div>
        `).join('');
    };

    window.hideSkeleton = function (container) {
        if (!container) return;
        container.querySelectorAll('.skeleton-card').forEach(el => {
            el.style.opacity = '0';
            el.style.transition = 'opacity 0.2s ease';
            setTimeout(() => el.remove(), 200);
        });
    };

    /* ── 13. AI SPINNER HELPERS (Public API) ───────────────────────────────── */
    window.showAISpinner = function (container, message = 'Processing…') {
        if (!container) return;
        const existing = container.querySelector('.ai-spinner-overlay');
        if (existing) return;

        const overlay = document.createElement('div');
        overlay.className = 'ai-spinner-overlay';
        overlay.style.cssText = `
            display: flex; align-items: center; justify-content: center;
            flex-direction: column; gap: 14px; padding: 32px;
            text-align: center;
        `;
        overlay.innerHTML = `
            <div class="ai-spinner-ring"></div>
            <div class="ai-processing-dots">
                <span></span><span></span><span></span>
            </div>
            <p style="color:var(--text-muted);font-size:0.9rem;margin:0;">${message}</p>
        `;
        container.appendChild(overlay);
    };

    window.hideAISpinner = function (container) {
        if (!container) return;
        const overlay = container.querySelector('.ai-spinner-overlay');
        if (overlay) {
            overlay.style.opacity = '0';
            overlay.style.transition = 'opacity 0.25s ease';
            setTimeout(() => overlay.remove(), 250);
        }
    };

    /* ── 14. MODAL ANIMATION ───────────────────────────────────────────────── */
    function initModalAnimations() {
        // Listen for modal open/close from existing code
        document.addEventListener('click', (e) => {
            const closeBtn = e.target.closest('[data-modal-close], .modal-close, [data-dismiss="modal"]');
            if (closeBtn) {
                const modal = closeBtn.closest('.modal, [role="dialog"]');
                if (modal) {
                    modal.classList.add('closing');
                    setTimeout(() => modal.classList.remove('closing'), 250);
                }
            }
        });
    }

    /* ── 15. SECTION HEADER REVEAL ─────────────────────────────────────────── */
    function initSectionHeaders() {
        if (prefersReducedMotion) return;

        document.querySelectorAll('.section-header').forEach(el => {
            if (!el.classList.contains('reveal')) {
                el.classList.add('reveal');
            }
        });
    }

    /* ── MAIN INIT ──────────────────────────────────────────────────────────── */
    function initAnimations() {
        initPageLoad();
        initNavbarScroll();
        initRippleButtons();
        initModalAnimations();
        initSectionHeaders();
        autoRevealSections();
        autoAssignCounters();

        // Run after a tick so DOM is fully ready
        requestAnimationFrame(() => {
            initScrollReveal();
            initCounterAnimations();
            initEmptyStateAnimations();
            initQueueCardAnimations();
            initToastEnhancement();
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initAnimations);
    } else {
        initAnimations();
    }

})();
