import axios from 'axios';
import toast from 'react-hot-toast';

const API_BASE = '/api';

const client = axios.create({
  baseURL: API_BASE,
  timeout: 30000,
});

// Request interceptor - attach token
client.interceptors.request.use((config) => {
  const token = localStorage.getItem('tc_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor - handle errors
client.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('tc_token');
      localStorage.removeItem('tc_user');
      window.location.href = '/login';
    } else if (error.response?.status === 403) {
      toast.error('권한이 없습니다.');
    } else if (error.response?.status >= 500) {
      toast.error('서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.');
    }
    return Promise.reject(error);
  }
);

export default client;

// Auth
export const authAPI = {
  login: (email, password) =>
    client.post('/auth/token', { email, password }),
  register: (email, password, org_name) =>
    client.post('/auth/register', { email, password, org_name }),
  me: () => client.get('/auth/me'),
};

// Projects
export const projectsAPI = {
  list: () => client.get('/projects'),
  get: (id) => client.get(`/projects/${id}`),
  create: (data) => client.post('/projects', data),
  delete: (id) => client.delete(`/projects/${id}`),
};

// Plots/Parcels
export const plotsAPI = {
  list: (projectId) => client.get(`/projects/${projectId}/plots`),
  upload: (projectId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return client.post(`/projects/${projectId}/plots/upload`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  validate: (projectId, file) => {
    const fd = new FormData();
    fd.append('file', file);
    return client.post(`/projects/${projectId}/plots/validate`, fd, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
  },
  delete: (plotId) => client.delete(`/plots/${plotId}`),
};

// Analysis
export const analysisAPI = {
  run: (projectId) => client.post(`/projects/${projectId}/analyze`),
  jobStatus: (jobId) => client.get(`/jobs/${jobId}`),
  jobResults: (jobId, riskLevel) =>
    client.get(`/jobs/${jobId}/results`, { params: riskLevel ? { risk_level: riskLevel } : {} }),
  jobSummary: (jobId) => client.get(`/jobs/${jobId}/results/summary`),
  projectJobs: (projectId) => client.get(`/projects/${projectId}/jobs`),
  projectHistory: (projectId) => client.get(`/projects/${projectId}/history`),
};

// Reports
export const reportsAPI = {
  generate: (jobId, format) => client.post(`/jobs/${jobId}/reports`, { format }),
  list: (jobId) => client.get(`/jobs/${jobId}/reports`),
  downloadUrl: (reportId) => `${API_BASE}/reports/${reportId}/download`,
  download: async (reportId, filename) => {
    const resp = await client.get(`/reports/${reportId}/download`, { responseType: 'blob' });
    const url = window.URL.createObjectURL(resp.data);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename || 'report';
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
  },
};

// Organizations
export const orgAPI = {
  me: () => client.get('/organizations/me'),
  subscription: () => client.get('/organizations/me/subscription'),
  members: () => client.get('/organizations/me/members'),
  updateMemberRole: (userId, role) =>
    client.patch(`/organizations/me/members/${userId}/role`, { role }),
};

// Webhooks
export const webhooksAPI = {
  list: () => client.get('/webhooks'),
  create: (data) => client.post('/webhooks', data),
  update: (id, data) => client.patch(`/webhooks/${id}`, data),
  delete: (id) => client.delete(`/webhooks/${id}`),
  test: (id) => client.post(`/webhooks/${id}/test`),
};

// Admin
export const adminAPI = {
  stats: () => client.get('/admin/stats'),
  users: () => client.get('/admin/users'),
  orgs: () => client.get('/admin/organizations'),
};
