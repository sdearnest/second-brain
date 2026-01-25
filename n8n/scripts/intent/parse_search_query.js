/**
 * Parse_Query - Search Query Parser
 * 
 * Workflow: Call_Obsidian_Search_Agent (sub-workflow)
 * Node: Parse_Query
 * 
 * Purpose: Parses the AI response from Extract_Search_Query into structured fields.
 *          Handles multiple response formats from Ollama (simplified and full).
 * 
 * Input: AI model response with JSON content
 * Output: query, database, date_filter, intent, original_message
 * 
 * Last updated: 2026-01-25
 */

const input = $input.first().json;

// Handle multiple possible response structures from Ollama
// With "Simplify Output" ON: { content: "..." }
// With "Simplify Output" OFF: { output: [{ content: [{ text: "..." }] }] }
let content = '';

if (typeof input.content === 'string') {
  // Simplified output - content is directly the string
  content = input.content;
} else if (input.output?.[0]?.content?.[0]?.text) {
  // Full output structure
  content = input.output[0].content[0].text;
} else if (input.text) {
  // Alternative text field
  content = input.text;
} else {
  content = '{}';
}

let parsed;
try {
  // Strip markdown code fences if present
  const jsonStr = content
    .replace(/```json\n?/g, '')
    .replace(/```\n?/g, '')
    .trim();
  
  parsed = JSON.parse(jsonStr);
} catch (e) {
  // Fallback: use original message as query
  parsed = {
    query: $('When Called By Another Workflow').first().json.message,
    database: 'all',
    date_filter: null,
    intent: 'find'
  };
}

return {
  json: {
    query: parsed.query || '',
    database: parsed.database || 'all',
    date_filter: parsed.date_filter || null,
    intent: parsed.intent || 'find',
    original_message: $('When Called By Another Workflow').first().json.message
  }
};
