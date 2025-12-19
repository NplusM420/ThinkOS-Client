/**
 * TypeScript types for the plugin system.
 */

export type PluginType = 'tool' | 'provider' | 'ui' | 'integration';

export type PluginStatus = 'installed' | 'enabled' | 'disabled' | 'error' | 'updating';

export type PluginPermission =
  | 'read_memories'
  | 'write_memories'
  | 'read_settings'
  | 'write_settings'
  | 'execute_tools'
  | 'network_access'
  | 'file_system'
  | 'agent_execution';

export interface PluginAuthor {
  name: string;
  email?: string;
  url?: string;
}

export interface PluginInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  type: PluginType;
  author: PluginAuthor;
  status: PluginStatus;
  permissions: PluginPermission[];
  installed_at: string;
  is_loaded: boolean;
  error_message?: string;
}

export interface PluginListResponse {
  plugins: PluginInfo[];
  total: number;
}

export interface PluginSettings {
  plugin_id: string;
  settings: Record<string, unknown>;
}

export interface PluginTool {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  plugin_id: string;
}

export interface PluginProvider {
  name: string;
  display_name: string;
  description: string;
  supports_chat: boolean;
  supports_embeddings: boolean;
  supports_streaming: boolean;
  plugin_id: string;
  config_schema: Record<string, unknown>;
}

export interface PluginInstallRequest {
  source: string;
  enable?: boolean;
}

export interface PluginSettingsUpdateRequest {
  settings: Record<string, unknown>;
}

/**
 * Permission display information
 */
export const PERMISSION_INFO: Record<PluginPermission, { label: string; description: string; risk: 'low' | 'medium' | 'high' }> = {
  read_memories: {
    label: 'Read Memories',
    description: 'Access and search your saved memories',
    risk: 'low',
  },
  write_memories: {
    label: 'Write Memories',
    description: 'Create and modify memories',
    risk: 'medium',
  },
  read_settings: {
    label: 'Read Settings',
    description: 'Access application settings',
    risk: 'low',
  },
  write_settings: {
    label: 'Write Settings',
    description: 'Modify application settings',
    risk: 'medium',
  },
  execute_tools: {
    label: 'Execute Tools',
    description: 'Run registered tools and actions',
    risk: 'medium',
  },
  network_access: {
    label: 'Network Access',
    description: 'Make HTTP requests to external services',
    risk: 'high',
  },
  file_system: {
    label: 'File System',
    description: 'Read and write files on your computer',
    risk: 'high',
  },
  agent_execution: {
    label: 'Agent Execution',
    description: 'Run AI agents on your behalf',
    risk: 'high',
  },
};

/**
 * Plugin type display information
 */
export const PLUGIN_TYPE_INFO: Record<PluginType, { label: string; description: string; icon: string }> = {
  tool: {
    label: 'Tool',
    description: 'Adds new tools for agents to use',
    icon: 'Wrench',
  },
  provider: {
    label: 'Provider',
    description: 'Adds new AI model providers',
    icon: 'Cloud',
  },
  ui: {
    label: 'UI Extension',
    description: 'Adds new views and components',
    icon: 'Layout',
  },
  integration: {
    label: 'Integration',
    description: 'Connects external services',
    icon: 'Link',
  },
};

/**
 * Get risk level color
 */
export function getRiskColor(risk: 'low' | 'medium' | 'high'): string {
  switch (risk) {
    case 'low':
      return 'text-green-500';
    case 'medium':
      return 'text-yellow-500';
    case 'high':
      return 'text-red-500';
  }
}

/**
 * Get status badge variant
 */
export function getStatusVariant(status: PluginStatus): 'default' | 'secondary' | 'destructive' | 'outline' {
  switch (status) {
    case 'enabled':
      return 'default';
    case 'disabled':
      return 'secondary';
    case 'error':
      return 'destructive';
    default:
      return 'outline';
  }
}
