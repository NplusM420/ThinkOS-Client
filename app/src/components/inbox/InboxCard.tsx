/**
 * Inbox card component for displaying individual inbox items.
 */

import { useState } from 'react';
import {
  FileText,
  Link,
  Clock,
  CheckSquare,
  Bell,
  Bot,
  Lightbulb,
  Check,
  X,
  ExternalLink,
  ChevronDown,
  ChevronUp,
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { markAsRead, dismissItem } from '@/lib/api/inbox';
import type { InboxItem, InboxItemType, InboxItemPriority } from '@/types/inbox';
import { INBOX_TYPE_INFO, PRIORITY_INFO, getRelativeTime } from '@/types/inbox';

const TYPE_ICONS: Record<InboxItemType, typeof FileText> = {
  digest: FileText,
  connection: Link,
  stale_alert: Clock,
  action_item: CheckSquare,
  reminder: Bell,
  agent_result: Bot,
  suggestion: Lightbulb,
};

interface InboxCardProps {
  item: InboxItem;
  onUpdate: () => void;
  onViewMemory?: (memoryId: number) => void;
}

export function InboxCard({ item, onUpdate, onViewMemory }: InboxCardProps) {
  const [expanded, setExpanded] = useState(false);
  const [loading, setLoading] = useState(false);

  const Icon = TYPE_ICONS[item.item_type];
  const typeInfo = INBOX_TYPE_INFO[item.item_type];
  const priorityInfo = PRIORITY_INFO[item.priority];

  const handleMarkRead = async () => {
    try {
      setLoading(true);
      await markAsRead(item.id);
      onUpdate();
    } catch (error) {
      toast.error('Failed to mark as read');
    } finally {
      setLoading(false);
    }
  };

  const handleDismiss = async () => {
    try {
      setLoading(true);
      await dismissItem(item.id);
      toast.success('Item dismissed');
      onUpdate();
    } catch (error) {
      toast.error('Failed to dismiss item');
    } finally {
      setLoading(false);
    }
  };

  const handleAction = () => {
    if (item.action_type === 'view_memory' && item.source_memory_id && onViewMemory) {
      onViewMemory(item.source_memory_id);
    } else if (item.action_type === 'link_memories' && item.action_data) {
      // Handle link memories action
      const sourceId = item.action_data.source_id as number;
      const targetId = item.action_data.target_id as number;
      toast.info(`Link memories ${sourceId} and ${targetId}`);
    } else if (item.action_type === 'open_url' && item.action_data?.url) {
      window.open(item.action_data.url as string, '_blank');
    }
  };

  return (
    <Card className={`transition-colors ${item.is_read ? 'bg-muted/30' : 'bg-card'}`}>
      <CardContent className="p-4">
        <div className="flex items-start gap-3">
          {/* Icon */}
          <div className={`p-2 rounded-lg bg-muted ${typeInfo.color}`}>
            <Icon className="h-5 w-5" />
          </div>

          {/* Content */}
          <div className="flex-1 min-w-0">
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h3 className={`font-medium truncate ${item.is_read ? 'text-muted-foreground' : ''}`}>
                    {item.title}
                  </h3>
                  {!item.is_read && (
                    <span className="h-2 w-2 rounded-full bg-primary flex-shrink-0" />
                  )}
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Badge variant="outline" className="text-xs">
                    {typeInfo.label}
                  </Badge>
                  {item.priority > 1 && (
                    <Badge variant="outline" className={`text-xs ${priorityInfo.color}`}>
                      {priorityInfo.label}
                    </Badge>
                  )}
                  <span>{getRelativeTime(item.created_at)}</span>
                </div>
              </div>

              {/* Actions */}
              <div className="flex items-center gap-1 flex-shrink-0">
                {!item.is_read && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={handleMarkRead}
                    disabled={loading}
                    title="Mark as read"
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                )}
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={handleDismiss}
                  disabled={loading}
                  title="Dismiss"
                >
                  <X className="h-4 w-4" />
                </Button>
                {item.content && (
                  <Button
                    variant="ghost"
                    size="icon"
                    onClick={() => setExpanded(!expanded)}
                    title={expanded ? 'Collapse' : 'Expand'}
                  >
                    {expanded ? (
                      <ChevronUp className="h-4 w-4" />
                    ) : (
                      <ChevronDown className="h-4 w-4" />
                    )}
                  </Button>
                )}
              </div>
            </div>

            {/* Expanded content */}
            {expanded && item.content && (
              <div className="mt-3 pt-3 border-t">
                <p className="text-sm text-muted-foreground whitespace-pre-wrap">
                  {item.content}
                </p>
              </div>
            )}

            {/* Action button */}
            {item.is_actionable && item.action_type && (
              <div className="mt-3">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={handleAction}
                  className="gap-2"
                >
                  <ExternalLink className="h-4 w-4" />
                  {getActionLabel(item.action_type)}
                </Button>
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

function getActionLabel(actionType: string): string {
  switch (actionType) {
    case 'view_memory':
      return 'View Memory';
    case 'create_memory':
      return 'Create Memory';
    case 'link_memories':
      return 'Link Memories';
    case 'run_agent':
      return 'Run Agent';
    case 'open_url':
      return 'Open Link';
    default:
      return 'Take Action';
  }
}

export default InboxCard;
