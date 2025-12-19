/**
 * API client for plugin management.
 */

import { apiFetch } from '../api';
import type {
  PluginInfo,
  PluginListResponse,
  PluginSettings,
  PluginTool,
  PluginProvider,
  PluginType,
} from '@/types/plugin';

/**
 * List all installed plugins
 */
export async function listPlugins(type?: PluginType): Promise<PluginListResponse> {
  const params = new URLSearchParams();
  if (type) {
    params.set('plugin_type', type);
  }
  
  const url = params.toString() ? `/api/plugins?${params}` : '/api/plugins';
  const response = await apiFetch(url);
  
  if (!response.ok) {
    throw new Error(`Failed to list plugins: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific plugin by ID
 */
export async function getPlugin(pluginId: string): Promise<PluginInfo> {
  const response = await apiFetch(`/api/plugins/${pluginId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get plugin: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Install a plugin from a local path
 */
export async function installPlugin(source: string, enable = true): Promise<PluginInfo> {
  const response = await apiFetch('/api/plugins/install', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ source, enable }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to install plugin');
  }
  
  return response.json();
}

/**
 * Upload and install a plugin from a file
 */
export async function uploadPlugin(file: File, enable = true): Promise<PluginInfo> {
  const formData = new FormData();
  formData.append('file', file);
  formData.append('enable', String(enable));
  
  const response = await apiFetch('/api/plugins/upload', {
    method: 'POST',
    body: formData,
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to upload plugin');
  }
  
  return response.json();
}

/**
 * Uninstall a plugin
 */
export async function uninstallPlugin(pluginId: string): Promise<void> {
  const response = await apiFetch(`/api/plugins/${pluginId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to uninstall plugin');
  }
}

/**
 * Enable a plugin
 */
export async function enablePlugin(pluginId: string): Promise<PluginInfo> {
  const response = await apiFetch(`/api/plugins/${pluginId}/enable`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to enable plugin');
  }
  
  return response.json();
}

/**
 * Disable a plugin
 */
export async function disablePlugin(pluginId: string): Promise<PluginInfo> {
  const response = await apiFetch(`/api/plugins/${pluginId}/disable`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to disable plugin');
  }
  
  return response.json();
}

/**
 * Get plugin settings
 */
export async function getPluginSettings(pluginId: string): Promise<PluginSettings> {
  const response = await apiFetch(`/api/plugins/${pluginId}/settings`);
  
  if (!response.ok) {
    throw new Error(`Failed to get plugin settings: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Update plugin settings
 */
export async function updatePluginSettings(
  pluginId: string,
  settings: Record<string, unknown>
): Promise<PluginSettings> {
  const response = await apiFetch(`/api/plugins/${pluginId}/settings`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ settings }),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to update plugin settings');
  }
  
  return response.json();
}

/**
 * Get tools provided by a plugin
 */
export async function getPluginTools(pluginId: string): Promise<PluginTool[]> {
  const response = await apiFetch(`/api/plugins/${pluginId}/tools`);
  
  if (!response.ok) {
    throw new Error(`Failed to get plugin tools: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.tools;
}

/**
 * Get providers provided by a plugin
 */
export async function getPluginProviders(pluginId: string): Promise<PluginProvider[]> {
  const response = await apiFetch(`/api/plugins/${pluginId}/providers`);
  
  if (!response.ok) {
    throw new Error(`Failed to get plugin providers: ${response.statusText}`);
  }
  
  const data = await response.json();
  return data.providers;
}

/**
 * Reload a plugin
 */
export async function reloadPlugin(pluginId: string): Promise<PluginInfo> {
  const response = await apiFetch(`/api/plugins/${pluginId}/reload`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to reload plugin');
  }
  
  return response.json();
}
