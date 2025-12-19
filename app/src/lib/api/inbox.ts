/**
 * API client for Smart Inbox.
 */

import { apiFetch } from '../api';
import type {
  InboxItem,
  InboxListResponse,
  InboxStats,
  InboxItemCreate,
  InboxItemUpdate,
  InboxItemType,
  DigestConfig,
} from '@/types/inbox';

/**
 * List inbox items
 */
export async function listInboxItems(options?: {
  itemType?: InboxItemType;
  unreadOnly?: boolean;
  limit?: number;
  offset?: number;
}): Promise<InboxListResponse> {
  const params = new URLSearchParams();
  
  if (options?.itemType) {
    params.set('item_type', options.itemType);
  }
  if (options?.unreadOnly) {
    params.set('unread_only', 'true');
  }
  if (options?.limit) {
    params.set('limit', String(options.limit));
  }
  if (options?.offset) {
    params.set('offset', String(options.offset));
  }
  
  const url = params.toString() ? `/api/inbox?${params}` : '/api/inbox';
  const response = await apiFetch(url);
  
  if (!response.ok) {
    throw new Error(`Failed to list inbox items: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get inbox statistics
 */
export async function getInboxStats(): Promise<InboxStats> {
  const response = await apiFetch('/api/inbox/stats');
  
  if (!response.ok) {
    throw new Error(`Failed to get inbox stats: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Get a specific inbox item
 */
export async function getInboxItem(itemId: number): Promise<InboxItem> {
  const response = await apiFetch(`/api/inbox/${itemId}`);
  
  if (!response.ok) {
    throw new Error(`Failed to get inbox item: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Create a new inbox item
 */
export async function createInboxItem(item: InboxItemCreate): Promise<InboxItem> {
  const response = await apiFetch('/api/inbox', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to create inbox item');
  }
  
  return response.json();
}

/**
 * Update an inbox item
 */
export async function updateInboxItem(
  itemId: number,
  update: InboxItemUpdate
): Promise<InboxItem> {
  const response = await apiFetch(`/api/inbox/${itemId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(update),
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to update inbox item');
  }
  
  return response.json();
}

/**
 * Mark an inbox item as read
 */
export async function markAsRead(itemId: number): Promise<InboxItem> {
  const response = await apiFetch(`/api/inbox/${itemId}/read`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    throw new Error(`Failed to mark item as read: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Dismiss an inbox item
 */
export async function dismissItem(itemId: number): Promise<InboxItem> {
  const response = await apiFetch(`/api/inbox/${itemId}/dismiss`, {
    method: 'POST',
  });
  
  if (!response.ok) {
    throw new Error(`Failed to dismiss item: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Mark all inbox items as read
 */
export async function markAllAsRead(): Promise<{ updated: number }> {
  const response = await apiFetch('/api/inbox/read-all', {
    method: 'POST',
  });
  
  if (!response.ok) {
    throw new Error(`Failed to mark all as read: ${response.statusText}`);
  }
  
  return response.json();
}

/**
 * Delete an inbox item
 */
export async function deleteInboxItem(itemId: number): Promise<void> {
  const response = await apiFetch(`/api/inbox/${itemId}`, {
    method: 'DELETE',
  });
  
  if (!response.ok) {
    throw new Error(`Failed to delete inbox item: ${response.statusText}`);
  }
}

/**
 * Generate a digest manually
 */
export async function generateDigest(config?: DigestConfig): Promise<{
  generated: boolean;
  inbox_item_id?: number;
  summary?: string;
  memory_count?: number;
  stale_count?: number;
  reason?: string;
}> {
  const response = await apiFetch('/api/inbox/generate-digest', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: config ? JSON.stringify(config) : undefined,
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to generate digest');
  }
  
  return response.json();
}

/**
 * Analyze connections manually
 */
export async function analyzeConnections(): Promise<{
  analyzed: boolean;
  suggestions_found: number;
  items_created: number;
}> {
  const response = await apiFetch('/api/inbox/analyze-connections', {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to analyze connections');
  }
  
  return response.json();
}

/**
 * Extract action items manually
 */
export async function extractActions(): Promise<{
  analyzed: boolean;
  actions_found: number;
  items_created: number;
}> {
  const response = await apiFetch('/api/inbox/extract-actions', {
    method: 'POST',
  });
  
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(error.detail || 'Failed to extract actions');
  }
  
  return response.json();
}
