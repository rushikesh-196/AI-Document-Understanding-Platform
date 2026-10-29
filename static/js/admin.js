/* ==========================================================================
   AI Document Intelligence Platform — Admin Operations JS
   ========================================================================== */

const AdminManager = {
    async fetchStats() {
        try {
            const res = await fetch('/api/admin/stats');
            return await res.json();
        } catch (e) {
            console.error('Error fetching admin stats:', e);
            return { success: false };
        }
    },

    async fetchUsers(query = '') {
        try {
            const url = query ? `/api/admin/users?q=${encodeURIComponent(query)}` : '/api/admin/users';
            const res = await fetch(url);
            return await res.json();
        } catch (e) {
            console.error('Error fetching admin users:', e);
            return { success: false, users: [] };
        }
    },

    async fetchDocuments(page = 1, type = '', status = '', query = '') {
        try {
            const params = new URLSearchParams({ page, type, status, q: query });
            const res = await fetch(`/api/admin/documents?${params.toString()}`);
            return await res.json();
        } catch (e) {
            console.error('Error fetching admin documents:', e);
            return { success: false, documents: [] };
        }
    },

    async deleteUser(userId) {
        try {
            const res = await fetch(`/api/admin/users/${userId}`, { method: 'DELETE' });
            return await res.json();
        } catch (e) {
            return { success: false, message: 'Network error deleting user.' };
        }
    },

    async toggleUserStatus(userId, status) {
        try {
            const res = await fetch(`/api/admin/users/${userId}/status`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ status })
            });
            return await res.json();
        } catch (e) {
            return { success: false, message: 'Network error updating user status.' };
        }
    },

    async deleteDocument(jobId) {
        try {
            const res = await fetch(`/api/admin/documents/${jobId}`, { method: 'DELETE' });
            return await res.json();
        } catch (e) {
            return { success: false, message: 'Network error deleting document.' };
        }
    }
};
