/**
 * Inbox page for Smart Inbox feature.
 */

import { SmartInbox } from "@/components/inbox";

export default function InboxPage() {
  const handleViewMemory = (memoryId: number) => {
    // Navigate to memory or open memory viewer
    console.log("View memory:", memoryId);
    // TODO: Integrate with memory navigation
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <SmartInbox onViewMemory={handleViewMemory} />
    </div>
  );
}
