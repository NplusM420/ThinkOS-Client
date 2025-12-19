/**
 * TypeScript types for Smart Inbox feature.
 */

export type InboxItemType =
  | 'digest'
  | 'connection'
  | 'stale_alert'
  | 'action_item'
  | 'reminder'
  | 'agent_result'
  | 'suggestion';

export type InboxItemPriority = 0 | 1 | 2 | 3;

export type ActionType =
  | 'view_memory'
  | 'create_memory'
  | 'link_memories'
  | 'run_agent'
  | 'open_url'
  | 'custom';

export interface InboxItem {
  id: number;
  item_type: InboxItemType;
  title: string;
  content?: string;
  metadata?: Record<string, unknown>;
  priority: InboxItemPriority;
  is_read: boolean;
  is_dismissed: boolean;
  is_actionable: boolean;
  action_type?: ActionType;
  action_data?: Record<string, unknown>;
  source_memory_id?: number;
  related_memory_ids?: number[];
  expires_at?: string;
  created_at: string;
  read_at?: string;
}

export interface InboxListResponse {
  items: InboxItem[];
  total: number;
  unread: number;
}

export interface InboxStats {
  total: number;
  unread: number;
  actionable: number;
  by_type: Record<string, number>;
}

export interface InboxItemCreate {
  item_type: InboxItemType;
  title: string;
  content?: string;
  metadata?: Record<string, unknown>;
  priority?: InboxItemPriority;
  is_actionable?: boolean;
  action_type?: ActionType;
  action_data?: Record<string, unknown>;
  source_memory_id?: number;
  related_memory_ids?: number[];
  expires_at?: string;
}

export interface InboxItemUpdate {
  is_read?: boolean;
  is_dismissed?: boolean;
}

export interface DigestConfig {
  frequency: 'daily' | 'weekly';
  include_stale_alerts?: boolean;
  include_connections?: boolean;
  include_action_items?: boolean;
  stale_threshold_days?: number;
  max_items?: number;
}

/**
 * Item type display information
 */
export const INBOX_TYPE_INFO: Record<InboxItemType, { label: string; icon: string; color: string }> = {
  digest: {
    label: 'Digest',
    icon: 'FileText',
    color: 'text-blue-500',
  },
  connection: {
    label: 'Connection',
    icon: 'Link',
    color: 'text-purple-500',
  },
  stale_alert: {
    label: 'Stale Alert',
    icon: 'Clock',
    color: 'text-orange-500',
  },
  action_item: {
    label: 'Action Item',
    icon: 'CheckSquare',
    color: 'text-green-500',
  },
  reminder: {
    label: 'Reminder',
    icon: 'Bell',
    color: 'text-yellow-500',
  },
  agent_result: {
    label: 'Agent Result',
    icon: 'Bot',
    color: 'text-indigo-500',
  },
  suggestion: {
    label: 'Suggestion',
    icon: 'Lightbulb',
    color: 'text-cyan-500',
  },
};

/**
 * Priority display information
 */
export const PRIORITY_INFO: Record<InboxItemPriority, { label: string; color: string }> = {
  0: { label: 'Low', color: 'text-muted-foreground' },
  1: { label: 'Normal', color: 'text-foreground' },
  2: { label: 'High', color: 'text-orange-500' },
  3: { label: 'Urgent', color: 'text-red-500' },
};

/**
 * Get relative time string
 */
export function getRelativeTime(dateString: string): string {
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / 60000);
  const diffHours = Math.floor(diffMs / 3600000);
  const diffDays = Math.floor(diffMs / 86400000);

  if (diffMins < 1) return 'Just now';
  if (diffMins < 60) return `${diffMins}m ago`;
  if (diffHours < 24) return `${diffHours}h ago`;
  if (diffDays < 7) return `${diffDays}d ago`;
  return date.toLocaleDateString();
}
