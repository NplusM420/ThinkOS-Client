/**
 * Inbox page for Smart Inbox feature.
 */

import { useNavigate } from "react-router-dom";
import { SmartInbox } from "@/components/inbox";

export default function InboxPage() {
  const navigate = useNavigate();
  
  const handleViewMemory = (memoryId: number) => {
    // Navigate to memories page with the memory ID as a query param to open detail panel
    navigate(`/memories?view=${memoryId}`);
  };

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <SmartInbox onViewMemory={handleViewMemory} />
    </div>
  );
}
