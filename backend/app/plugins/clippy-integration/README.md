# Clippy Integration Plugin

Integrates ThinkOS with the Clipper platform to create video clips using the Clippy AI agent.

## Features

- **clippy_create_clips** - Send video URLs to Clippy for AI-powered clip generation
- **clippy_check_status** - Check progress of async clip generation jobs
- **clippy_get_clip** - Retrieve details and download URLs for generated clips
- **clippy_configure** - Configure API URL and authentication

## Setup

### 1. Install the Plugin

Copy this folder to your ThinkOS plugins directory or install via the UI.

### 2. Configure Clipper Connection

Use the `clippy_configure` tool or set these ThinkOS settings:

| Setting | Description |
|---------|-------------|
| `clippy_api_url` | Base URL of Clipper API (default: `http://localhost:5000`) |
| `clippy_api_key` | API key from Clipper |
| `clippy_auto_save` | Auto-save clips as memories (`true`/`false`) |

### 3. Get a Clipper API Key

In Clipper, go to Settings → API Keys → Create New Key with these permissions:
- `video_processing` - Required for video upload/analysis
- `clip_generation` - Required for creating clips
- `clippy_agent` - Required for Clippy AI features

## Usage

### Create Clips from a Video

```
User: Create some funny clips from this video: https://youtube.com/watch?v=xyz

Agent: [Uses clippy_create_clips tool]
- video_url: https://youtube.com/watch?v=xyz
- prompt: Find the funniest moments
- target_platform: tiktok
- max_clips: 5
```

### Check Job Status

```
Agent: [Uses clippy_check_status tool]
- job_id: job_abc123
```

### Get Clip Details

```
Agent: [Uses clippy_get_clip tool]
- clip_id: clip_xyz789
```

## Auto-Save to Memories

When `clippy_auto_save` is enabled (default), generated clips are automatically saved as ThinkOS memories with:

- Title: "Clip: {clip_title}"
- Content: Description, timestamps, captions, download URL
- Tags: `clippy`, `video-clip`, `{platform}`
- Type: `clip`

This allows you to search and reference clips later through ThinkOS.

## API Response Format

### Clip Object

```json
{
  "id": "clip_abc123",
  "title": "Funny moment at 2:30",
  "description": "Speaker makes a joke about...",
  "startTime": 150,
  "endTime": 165,
  "duration": 15,
  "downloadUrl": "https://...",
  "thumbnailUrl": "https://...",
  "captions": "Speaker: And then I said...",
  "aspectRatio": "9:16",
  "platformRecommendation": "tiktok",
  "confidence": 0.92
}
```

---

# Clipper-Side Implementation Required

**For your dev agent in Clipper**, here's what needs to be built:

## New Endpoint: POST /api/v1/clippy/generate

This is the main Clippy agent endpoint that ThinkOS will call.

### Request

```typescript
interface ClippyGenerateRequest {
  videoUrl: string;           // YouTube URL, direct video URL, etc.
  prompt: string;             // User's instructions for clip selection
  targetPlatform?: 'tiktok' | 'youtube_shorts' | 'instagram_reels' | 'linkedin' | 'twitter' | 'general';
  maxClips?: number;          // 1-10, default 5
  includeCaptions?: boolean;  // default true
  callbackUrl?: string;       // Optional webhook for async delivery
}
```

### Response (Sync Mode - if processing is fast)

```typescript
interface ClippyGenerateResponse {
  success: true;
  clips: ClipResult[];
  videoId: string;
  processingTime: number;
}

interface ClipResult {
  id: string;
  title: string;
  description: string;
  startTime: number;          // seconds
  endTime: number;            // seconds
  duration: number;           // seconds
  downloadUrl: string;        // Direct download URL
  thumbnailUrl?: string;
  captions?: string;          // SRT or plain text
  aspectRatio: string;        // "9:16", "16:9", "1:1", "4:5"
  platformRecommendation: string;
  confidence: number;         // 0-1 score
  reasoning?: string;         // Why this clip was selected
}
```

### Response (Async Mode - for longer videos)

```typescript
interface ClippyAsyncResponse {
  success: true;
  jobId: string;
  status: 'queued' | 'processing';
  message: string;
  estimatedTime: string;
}
```

## New Endpoint: GET /api/v1/clippy/jobs/:jobId

Check status of async clip generation.

### Response

```typescript
interface ClippyJobStatus {
  jobId: string;
  status: 'queued' | 'processing' | 'completed' | 'failed';
  progress: number;           // 0-100
  videoUrl: string;
  prompt: string;
  clips?: ClipResult[];       // Present when completed
  error?: string;             // Present when failed
  createdAt: string;
  completedAt?: string;
}
```

## Implementation Suggestions

### 1. Use Existing Orchestrator

Leverage `OrchestratorV2` for the AI clip discovery:

```typescript
// In server/routes/clippyRoutes.ts
import { orchestratorV2Service } from '../services/orchestratorV2';

router.post('/clippy/generate', authenticateApiKey, async (req, res) => {
  const { videoUrl, prompt, targetPlatform, maxClips, includeCaptions } = req.body;
  
  // 1. Extract/upload video using URLExtractionService
  const urlExtractionService = new URLExtractionService();
  const video = await urlExtractionService.extractVideo(videoUrl, req.apiKeyInfo.userId);
  
  // 2. Get transcript if needed
  const transcriptionService = new TranscriptionService();
  const transcript = await transcriptionService.transcribeVideo(video.id);
  
  // 3. Use orchestrator to find clips
  const result = await orchestratorV2Service.orchestrate({
    userId: req.apiKeyInfo.userId,
    videoId: video.id,
    userMessage: prompt,
    editorContext: {
      currentVideo: video,
      transcript: transcript,
    },
    conversationHistory: [],
  });
  
  // 4. Process discovered clips
  const clips = await processDiscoveredClips(result.clips, {
    targetPlatform,
    includeCaptions,
    maxClips,
  });
  
  res.json({ success: true, clips });
});
```

### 2. Aspect Ratio Logic

```typescript
function getAspectRatioForPlatform(platform: string): string {
  const ratios: Record<string, string> = {
    tiktok: '9:16',
    youtube_shorts: '9:16',
    instagram_reels: '9:16',
    instagram_feed: '1:1',
    linkedin: '16:9',
    twitter: '16:9',
    youtube: '16:9',
    general: '16:9',
  };
  return ratios[platform] || '16:9';
}
```

### 3. Caption Generation

Use existing `TranscriptionService` to extract captions for the clip timeframe:

```typescript
function extractCaptionsForClip(
  transcript: TranscriptSegment[],
  startTime: number,
  endTime: number
): string {
  return transcript
    .filter(seg => seg.startTime >= startTime && seg.endTime <= endTime)
    .map(seg => seg.text)
    .join(' ');
}
```

### 4. Register Routes

In `server/routes/index.ts`:

```typescript
import { clippyRoutes } from './clippyRoutes';

// In registerRoutes function:
app.use("/api/v1/clippy", clippyRoutes);
```

### 5. Add Permission

In `server/services/apiKeyService.ts`, add `clippy_agent` permission:

```typescript
export interface ApiKeyPermissions {
  video_processing: boolean;
  clip_generation: boolean;
  clippy_agent: boolean;  // NEW
  // ...
}
```

## Webhook Support (Optional)

For long-running jobs, Clipper can POST results to a callback URL:

```typescript
// When job completes
if (job.callbackUrl) {
  await webhookService.sendWebhook(job.callbackUrl, {
    event: 'clippy.job.completed',
    jobId: job.id,
    clips: job.clips,
    timestamp: new Date(),
  });
}
```

---

## Testing

1. Start Clipper: `npm run dev` (port 5000)
2. Start ThinkOS: Backend + App
3. Install this plugin in ThinkOS
4. Configure: `clippy_configure` with Clipper API key
5. Test: Ask ThinkOS agent to create clips from a video URL
