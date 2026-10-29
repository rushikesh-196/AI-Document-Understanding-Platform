/* ==========================================================================
   AI Document Intelligence Platform — Production Main & Auth JS System
   ========================================================================== */

// --- SERVER-BACKED AUTH & LOCAL DOCUMENT HISTORY ---
const AuthManager = {
    KEYS: {
        HISTORY: "ai_document_history"
    },

    currentUser: window.APP_CURRENT_USER || null,

    getCurrentUser() {
        return this.currentUser;
    },

    isLoggedIn() {
        return !!this.getCurrentUser();
    },

    isAdmin() {
        const user = this.getCurrentUser();
        return !!user && user.role === "admin";
    },

    async registerUser(name, email, password) {
        return this._sendAuthRequest("/auth/register", { name, email, password });
    },

    async loginUser(email, password, portal = "user") {
        return this._sendAuthRequest("/auth/login", { email, password, portal });
    },

    async _sendAuthRequest(url, payload) {
        try {
            const response = await fetch(url, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                credentials: "same-origin",
                body: JSON.stringify(payload)
            });
            const result = await response.json();
            if (response.ok && result.success) {
                this.currentUser = result.user;
            }
            return result;
        } catch (error) {
            return { success: false, message: "Unable to reach the authentication service." };
        }
    },

    async logoutUser() {
        try {
            await fetch("/auth/logout", { method: "POST", credentials: "same-origin" });
        } finally {
            this.currentUser = null;
            window.location.href = "/";
        }
    },

    getUserHistory() {
        const currentUser = this.getCurrentUser();
        if (!currentUser) return [];
        try {
            const allHistory = JSON.parse(localStorage.getItem(this.KEYS.HISTORY)) || [];
            return allHistory.filter(item => item.userId === currentUser.id);
        } catch (e) {
            return [];
        }
    },

    saveJobToHistory(jobData) {
        const currentUser = this.getCurrentUser();
        if (!currentUser) return;

        try {
            const allHistory = JSON.parse(localStorage.getItem(this.KEYS.HISTORY)) || [];
            const newRecord = {
                ...jobData,
                userId: currentUser.id,
                id: jobData.job_id || jobData.id || "job_" + Date.now(),
                filename: jobData.filename || "Document",
                upload_time: jobData.upload_time || jobData.timestamp || new Date().toLocaleString(),
                document_type: jobData.document_type || "Invoice / Document",
                status: "Processed"
            };

            // Remove existing record if duplicate job_id
            const filtered = allHistory.filter(h => h.id !== newRecord.id);
            filtered.unshift(newRecord);

            localStorage.setItem(this.KEYS.HISTORY, JSON.stringify(filtered));
        } catch (e) {
            console.error("Error saving job to history:", e);
        }
    },

    deleteJobFromHistory(jobId) {
        try {
            const allHistory = JSON.parse(localStorage.getItem(this.KEYS.HISTORY)) || [];
            const filtered = allHistory.filter(h => h.id !== jobId);
            localStorage.setItem(this.KEYS.HISTORY, JSON.stringify(filtered));
            return true;
        } catch (e) {
            return false;
        }
    }
};

// --- DOM INITIALIZATION ---

// --- THEME ENGINE ---
function applyTheme(theme) {
    const normalized = theme === "dark" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", normalized);
    document.body.setAttribute("data-theme", normalized);
    localStorage.setItem("ai_doc_theme", normalized);
}

function initTheme() {
    const themeToggle = document.getElementById("themeToggle");
    const mobileThemeToggle = document.getElementById("mobileThemeToggle");
    const savedTheme = localStorage.getItem("ai_doc_theme") || "light";

    applyTheme(savedTheme);

    const toggleFn = (event) => {
        if (event) {
            event.preventDefault();
            event.stopPropagation();
        }
        const currentTheme = document.body.getAttribute("data-theme") || "light";
        applyTheme(currentTheme === "light" ? "dark" : "light");
    };

    if (themeToggle) {
        themeToggle.setAttribute("type", "button");
        themeToggle.addEventListener("click", toggleFn);
    }
    if (mobileThemeToggle) {
        mobileThemeToggle.setAttribute("type", "button");
        mobileThemeToggle.addEventListener("click", toggleFn);
    }
}

// --- AUTH UI SYNC ---
function initAuthUI() {
    const currentUser = AuthManager.getCurrentUser();
    const navAuthContainer = document.getElementById("navAuthContainer");
    const mobileAuthContainer = document.getElementById("mobileAuthContainer");

    if (navAuthContainer) {
        if (currentUser) {
            const initial = currentUser.name.charAt(0).toUpperCase();
            const isAdmin = currentUser.role === "admin";
            const roleBadge = isAdmin ? `<span style="background:rgba(139,92,246,0.2);color:#8B5CF6;padding:2px 8px;border-radius:999px;font-size:0.7rem;font-weight:700;margin-left:6px;"><i class="fa-solid fa-shield-halved"></i> Admin</span>` : "";

            const adminItem = isAdmin ? `
                <a href="/admin/dashboard" class="dropdown-item" style="color:#8B5CF6; font-weight:600;" role="menuitem">
                    <i class="fa-solid fa-gauge-high"></i> Admin Dashboard
                </a>
            ` : "";

            navAuthContainer.innerHTML = `
                <div class="user-menu-wrapper">
                    <button class="user-menu-btn" id="userMenuBtn" aria-expanded="false" aria-haspopup="true">
                        <div class="user-avatar" style="${isAdmin ? 'background:linear-gradient(135deg,#8B5CF6,#4F46E5);color:#fff;' : ''}">${initial}</div>
                        <span class="user-name-text">${currentUser.name}</span>
                        ${roleBadge}
                        <i class="fa-solid fa-chevron-down" style="font-size:0.72rem; color:var(--text-muted); transition:transform 0.2s;"></i>
                    </button>
                    <div class="user-dropdown" id="userDropdown" role="menu">
                        <div class="dropdown-header">
                            <div class="user-avatar" style="width:36px;height:36px;font-size:1rem;margin-bottom:6px;${isAdmin ? 'background:linear-gradient(135deg,#8B5CF6,#4F46E5);color:#fff;' : ''}">${initial}</div>
                            <strong style="color:var(--text-main);">${currentUser.name}</strong><br>
                            <small style="color:var(--text-muted);">${currentUser.email}</small>
                        </div>
                        ${adminItem}
                        <a href="/dashboard" class="dropdown-item" role="menuitem"><i class="fa-solid fa-gauge"></i> User Dashboard</a>
                        <a href="/history" class="dropdown-item" role="menuitem"><i class="fa-solid fa-clock-rotate-left"></i> History</a>
                        <a href="/settings" class="dropdown-item" role="menuitem"><i class="fa-solid fa-gear"></i> Settings</a>
                        <div class="dropdown-divider"></div>
                        <div class="dropdown-item danger-item" onclick="AuthManager.logoutUser()" role="menuitem"><i class="fa-solid fa-right-from-bracket"></i> Sign Out</div>
                    </div>
                </div>
            `;

            const btn = document.getElementById("userMenuBtn");
            const dropdown = document.getElementById("userDropdown");
            if (btn && dropdown) {
                btn.addEventListener("click", (e) => {
                    e.stopPropagation();
                    const open = dropdown.classList.toggle("open");
                    btn.setAttribute("aria-expanded", open);
                    const icon = btn.querySelector(".fa-chevron-down");
                    if (icon) icon.style.transform = open ? "rotate(180deg)" : "";
                });
                document.addEventListener("click", () => {
                    dropdown.classList.remove("open");
                    btn.setAttribute("aria-expanded", false);
                    const icon = btn.querySelector(".fa-chevron-down");
                    if (icon) icon.style.transform = "";
                });
            }
        } else {
            navAuthContainer.innerHTML = `
                <a href="/auth" class="btn btn-primary btn-sm">
                    <i class="fa-solid fa-right-to-bracket"></i> Sign In
                </a>
            `;
        }
    }

    if (mobileAuthContainer) {
        if (currentUser) {
            const isAdmin = currentUser.role === "admin";
            mobileAuthContainer.innerHTML = `
                <div style="background:var(--background-alt);border-radius:var(--radius-md);padding:14px;margin-bottom:12px;">
                    <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                        <div class="user-avatar" style="width:36px;height:36px;font-size:1rem;${isAdmin ? 'background:linear-gradient(135deg,#8B5CF6,#4F46E5);color:#fff;' : ''}">${currentUser.name.charAt(0).toUpperCase()}</div>
                        <div>
                            <strong style="display:block;color:var(--text-main);font-size:0.9rem;">${currentUser.name}</strong>
                            <small style="color:var(--text-muted);">${currentUser.email}</small>
                        </div>
                    </div>
                    ${isAdmin ? '<a href="/admin/dashboard" class="btn btn-primary btn-sm" style="width:100%;margin-bottom:8px;background:linear-gradient(135deg,#8B5CF6,#4F46E5);"><i class="fa-solid fa-gauge-high"></i> Admin Dashboard</a>' : ''}
                    <button onclick="AuthManager.logoutUser()" class="btn btn-danger btn-sm" style="width:100%;">
                        <i class="fa-solid fa-right-from-bracket"></i> Sign Out
                    </button>
                </div>`;
        } else {
            mobileAuthContainer.innerHTML = `
                <a href="/auth" class="btn btn-primary btn-sm" style="width:100%;display:block;text-align:center;">
                    <i class="fa-solid fa-right-to-bracket"></i> Sign In / Create Account
                </a>`;
        }
    }
}

// --- MOBILE DRAWER NAVIGATION ---
function initMobileDrawer() {
    const toggleBtn = document.getElementById("mobileNavToggle");
    const closeBtn = document.getElementById("mobileDrawerClose");
    const drawer = document.getElementById("mobileDrawer");
    const backdrop = document.getElementById("mobileBackdrop");

    if (!toggleBtn || !drawer || !backdrop) return;

    const openDrawer = () => {
        drawer.classList.add("open");
        backdrop.classList.add("open");
    };

    const closeDrawer = () => {
        drawer.classList.remove("open");
        backdrop.classList.remove("open");
    };

    toggleBtn.addEventListener("click", openDrawer);
    if (closeBtn) closeBtn.addEventListener("click", closeDrawer);
    backdrop.addEventListener("click", closeDrawer);
}

// --- PROTECTED ROUTES GUARD ---
function initProtectedRoutes() {
    const userProtectedPaths = ["/dashboard", "/upload", "/results", "/history"];
    const currentPath = window.location.pathname;

    const isUserProtected = userProtectedPaths.some(path => currentPath === path || currentPath.startsWith("/results/"));

    if (isUserProtected && !AuthManager.isLoggedIn()) {
        showToast("Please sign in to continue.", "warning");
        setTimeout(() => {
            window.location.href = "/auth?redirect=" + encodeURIComponent(currentPath);
        }, 400);
    }
}

// --- NAV HIGHLIGHTING ---
function highlightActiveNav() {
    const currentPath = window.location.pathname;
    const navLinks = document.querySelectorAll(".nav-link");

    navLinks.forEach(link => {
        const href = link.getAttribute("href");
        if (href === currentPath || (currentPath.startsWith('/results') && href === '/results')) {
            link.classList.add("active");
        } else {
            link.classList.remove("active");
        }
    });
}

// --- TOAST NOTIFICATION SYSTEM ---
function showToast(message, type = "success", title = "") {
    let container = document.getElementById("toastContainer");
    if (!container) {
        container = document.createElement("div");
        container.id = "toastContainer";
        container.className = "toast-container";
        document.body.appendChild(container);
    }

    const iconMap = {
        success: "fa-solid fa-circle-check",
        error: "fa-solid fa-circle-xmark",
        warning: "fa-solid fa-triangle-exclamation",
        info: "fa-solid fa-circle-info"
    };

    const titleMap = {
        success: "Success",
        error: "Error",
        warning: "Attention",
        info: "Notice"
    };

    const toast = document.createElement("div");
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
        <i class="${iconMap[type] || iconMap.info} toast-icon"></i>
        <div class="toast-content">
            <div class="toast-title">${title || titleMap[type] || "Notice"}</div>
            <div class="toast-msg">${message}</div>
        </div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);

    setTimeout(() => {
        if (toast.parentElement) {
            toast.style.opacity = "0";
            toast.style.transform = "translateX(40px)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }
    }, 4200);
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    initAuthUI();
    initMobileDrawer();
    highlightActiveNav();
    initProtectedRoutes();
});
