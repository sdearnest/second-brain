# n8n Workflow Examples for Bridge v2

Examples showing how to use new bridge v2 features in n8n.

---

## 1. Voice Message → Whisper Transcription

Handle voice messages and transcribe them with your local Whisper service.

### Workflow Structure

```
Webhook (SimpleX Bridge)
    ↓
Switch (by message type)
    ├─ text → [existing workflow]
    └─ voice → Whisper Transcription
                    ↓
                Classify & File
                    ↓
                Send Confirmation Back
```

### Switch Node Config

```javascript
// Expression in Switch node
{{ $json.type }}

// Cases:
// - "text" → Route to existing text handling
// - "voice" → Route to new voice handling
// - "image" → Route to image handling (future)
// - "file" → Route to file handling (future)
```

### HTTP Request to Whisper

```javascript
// Node: "Transcribe Voice"
// Method: POST
// URL: http://whisper:8000/v1/audio/transcriptions

// Body (Form-Data):
{
  "file": {
    // Read file from filePath
    "filePath": "{{ $json.voice.filePath }}",
    "fileName": "voice.ogg"
  },
  "model": "whisper-1",
  "response_format": "json"
}

// Output: { "text": "transcribed text" }
```

### Set Node - Extract Transcription

```javascript
// After Whisper response
{
  "transcribedText": "{{ $json.text }}",
  "originalType": "voice",
  "duration": "{{ $('Webhook').item.json.voice.duration }}",
  "contactId": "{{ $('Webhook').item.json.contactId }}",
  "displayName": "{{ $('Webhook').item.json.displayName }}"
}
```

### Continue to Classification

Now send `transcribedText` to your existing classification workflow (Ollama → Obsidian).

---

## 2. Send Confirmation Back to SimpleX

After processing a message, send a confirmation back.

### HTTP Request Node

```javascript
// Node: "Send Confirmation"
// Method: POST
// URL: http://simplex-bridge:8080/send

// Body (JSON):
{
  "contactId": "{{ $json.contactId }}",
  "text": "✅ Saved to {{ $json.database }}: {{ $json.name }}"
}
```

### Examples

**After saving to Projects:**
```json
{
  "contactId": 123,
  "text": "✅ Saved to Projects: Second Brain Mobile App"
}
```

**After voice transcription:**
```json
{
  "contactId": 123,
  "text": "🎙️ Voice transcribed: \"{{ $json.transcribedText }}\" → Filed to {{ $json.database }}"
}
```

**On error:**
```json
{
  "contactId": 123,
  "text": "⚠️ Could not classify. Saved to Inbox for manual review."
}
```

---

## 3. Complete Voice → Transcribe → File → Confirm

Full workflow combining all features.

### Workflow Nodes

1. **Webhook Trigger** - Receives from bridge
2. **Switch by Type** - Routes text vs voice
3. **[Voice Branch] HTTP Request** - Transcribe with Whisper
4. **[Voice Branch] Set** - Extract transcription
5. **Function (Classify)** - Call Ollama for classification
6. **HTTP Request (Obsidian)** - Save to appropriate database
7. **HTTP Request (Confirm)** - Send confirmation back to SimpleX

### Complete Example (JSON)

```json
{
  "nodes": [
    {
      "name": "SimpleX Webhook",
      "type": "n8n-nodes-base.webhook",
      "position": [250, 300],
      "parameters": {
        "path": "simplex-capture",
        "responseMode": "lastNode",
        "options": {}
      }
    },
    {
      "name": "Switch by Type",
      "type": "n8n-nodes-base.switch",
      "position": [450, 300],
      "parameters": {
        "dataPropertyName": "type",
        "rules": {
          "rules": [
            {
              "value": "text",
              "output": 0
            },
            {
              "value": "voice",
              "output": 1
            }
          ]
        }
      }
    },
    {
      "name": "Transcribe Voice",
      "type": "n8n-nodes-base.httpRequest",
      "position": [650, 400],
      "parameters": {
        "method": "POST",
        "url": "http://whisper:8000/v1/audio/transcriptions",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "file",
              "value": "={{ $json.voice.filePath }}"
            },
            {
              "name": "model",
              "value": "whisper-1"
            },
            {
              "name": "response_format",
              "value": "json"
            }
          ]
        }
      }
    },
    {
      "name": "Extract Transcription",
      "type": "n8n-nodes-base.set",
      "position": [850, 400],
      "parameters": {
        "values": {
          "string": [
            {
              "name": "text",
              "value": "={{ $json.text }}"
            },
            {
              "name": "originalType",
              "value": "voice"
            },
            {
              "name": "contactId",
              "value": "={{ $('SimpleX Webhook').item.json.contactId }}"
            },
            {
              "name": "displayName",
              "value": "={{ $('SimpleX Webhook').item.json.displayName }}"
            }
          ]
        }
      }
    },
    {
      "name": "Classify with Ollama",
      "type": "n8n-nodes-base.httpRequest",
      "position": [1050, 300],
      "parameters": {
        "method": "POST",
        "url": "http://ollama:11434/api/generate",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "model",
              "value": "gemma3:12b"
            },
            {
              "name": "prompt",
              "value": "Classify this capture into: people, projects, ideas, or admin...\n\nCapture: {{ $json.text }}"
            },
            {
              "name": "stream",
              "value": false
            }
          ]
        }
      }
    },
    {
      "name": "Save to Obsidian",
      "type": "n8n-nodes-base.httpRequest",
      "position": [1250, 300],
      "parameters": {
        "method": "POST",
        "url": "http://obsidian-api:8765/capture",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "original_text",
              "value": "={{ $('Extract Transcription').item.json.text }}"
            },
            {
              "name": "database",
              "value": "={{ $json.database }}"
            },
            {
              "name": "name",
              "value": "={{ $json.name }}"
            }
          ]
        }
      }
    },
    {
      "name": "Send Confirmation",
      "type": "n8n-nodes-base.httpRequest",
      "position": [1450, 300],
      "parameters": {
        "method": "POST",
        "url": "http://simplex-bridge:8080/send",
        "sendBody": true,
        "bodyParameters": {
          "parameters": [
            {
              "name": "contactId",
              "value": "={{ $('Extract Transcription').item.json.contactId }}"
            },
            {
              "name": "text",
              "value": "✅ Saved to {{ $('Save to Obsidian').item.json.database }}: {{ $('Save to Obsidian').item.json.name }}"
            }
          ]
        }
      }
    }
  ],
  "connections": {
    "SimpleX Webhook": {
      "main": [
        [
          {
            "node": "Switch by Type",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Switch by Type": {
      "main": [
        [
          {
            "node": "Classify with Ollama",
            "type": "main",
            "index": 0
          }
        ],
        [
          {
            "node": "Transcribe Voice",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Transcribe Voice": {
      "main": [
        [
          {
            "node": "Extract Transcription",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Extract Transcription": {
      "main": [
        [
          {
            "node": "Classify with Ollama",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Classify with Ollama": {
      "main": [
        [
          {
            "node": "Save to Obsidian",
            "type": "main",
            "index": 0
          }
        ]
      ]
    },
    "Save to Obsidian": {
      "main": [
        [
          {
            "node": "Send Confirmation",
            "type": "main",
            "index": 0
          }
        ]
      ]
    }
  }
}
```

---

## 4. Error Handling with Confirmations

Send different messages based on success/failure.

### Error Node

```javascript
// Node: "On Error"
// Connected to "Save to Obsidian" error output

{
  "contactId": "={{ $('SimpleX Webhook').item.json.contactId }}",
  "text": "⚠️ Error: {{ $json.message }}\n\nOriginal text saved to Inbox for manual review."
}
```

### Success Node

```javascript
// Node: "On Success"
{
  "contactId": "={{ $('SimpleX Webhook').item.json.contactId }}",
  "text": "✅ Saved to {{ $json.database }}: {{ $json.name }}\n\nConfidence: {{ ($json.confidence * 100).toFixed(0) }}%"
}
```

---

## 5. Handle Multiple Message Types

Route different message types to appropriate handlers.

### Switch Node with All Types

```javascript
// Expression: {{ $json.type }}

// Outputs:
// 0: text → existing text workflow
// 1: voice → transcribe + process
// 2: image → OCR + process (future)
// 3: file → extract text + process (future)
// default: log + skip
```

### Image Handling (Future)

```javascript
// When you add image support:

// HTTP Request to OCR service
{
  "method": "POST",
  "url": "http://ocr-service:8080/extract",
  "body": {
    "filePath": "={{ $json.image.filePath }}"
  }
}

// Then process extracted text like normal
```

---

## 6. Rate Limit Notifications

Alert yourself when rate limiting occurs.

### Monitor Rate Limiting

```javascript
// Cron job in n8n (every hour)
// HTTP Request to bridge metrics

// URL: http://simplex-bridge:8080/metrics
// Method: GET

// If node: Check rate_limited count
{
  "expression": "={{ $json.rate_limited > 10 }}"
}

// True → Send alert to you
{
  "contactId": YOUR_CONTACT_ID,
  "text": "⚠️ Bridge rate limited {{ $json.rate_limited }} messages in the past hour."
}
```

---

## 7. Daily Summary

Send yourself a daily summary of captures.

### Cron Workflow

```javascript
// Trigger: Cron (daily at 8 AM)

// 1. Query Obsidian for today's captures
// 2. Count by database
// 3. Send summary to SimpleX

{
  "contactId": YOUR_CONTACT_ID,
  "text": `📊 Daily Summary:
  
  People: {{ $json.people_count }}
  Projects: {{ $json.projects_count }}
  Ideas: {{ $json.ideas_count }}
  Admin: {{ $json.admin_count }}
  
  Total: {{ $json.total }}
  Voice messages: {{ $json.voice_count }}`
}
```

---

## Tips & Best Practices

### 1. Always Check Message Type

```javascript
// Before processing, verify type exists
{{ $json.type || 'text' }}
```

### 2. Preserve Original Context

```javascript
// In Set nodes, keep original data:
{
  "processed_text": "...",
  "original_message": "={{ $json }}",  // Full original payload
  "contactId": "={{ $json.contactId }}"
}
```

### 3. Error Handling

Always add error branches and send feedback:

```
Main Flow
    ↓
  Error?
    ├─ Yes → Send error message to user
    └─ No → Send success message
```

### 4. Test Incrementally

1. Test text messages first (existing workflow)
2. Add voice support
3. Add confirmation messages
4. Add error handling
5. Add monitoring

### 5. Use Meaningful Confirmations

Bad: "✅ Done"

Good: "✅ Saved to Projects: Mobile App Redesign\nNext action: Design wireframes"

---

## Debugging Tips

### Check Bridge Payload

Add a debug node after webhook:

```javascript
// Function node to log payload
console.log("Message type:", $input.item.json.type);
console.log("Full payload:", JSON.stringify($input.item.json, null, 2));
return $input.all();
```

### Test Send Endpoint

Before adding to workflow, test manually:

```bash
curl -X POST http://simplex-bridge:8080/send \
  -H "Content-Type: application/json" \
  -d '{"contactId": 123, "text": "test"}'
```

### Monitor Metrics

Check if messages are being processed:

```bash
curl http://simplex-bridge:8080/metrics | jq
```

---

**You now have complete bidirectional voice-capable workflows!** 🎙️↔️📝
