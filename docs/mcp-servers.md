# Model Context Protocol (MCP) Servers

Extend GitHub Copilot's capabilities by connecting it to external tools, data sources, and services through MCP servers.

## What is MCP?

**Model Context Protocol (MCP)** is an open standard that enables AI assistants like GitHub Copilot to securely connect to external systems. MCP servers provide **tools** that Copilot can invoke during Agent mode to accomplish tasks.

## Why Use MCP?

| Without MCP | With MCP |
|-------------|----------|
| Only your codebase | Live database data |
| Public code patterns | GitHub/Jira/Slack APIs |
| General knowledge | Company documentation |
| | Real-time metrics |
| | Custom business logic |

## MCP in VS Code

MCP support is **generally available** in VS Code 1.102+. VS Code provides multiple ways to discover, install, and manage MCP servers.

### How MCP Works with Copilot

```text
┌──────────────────┐
│ Copilot Agent    │
│ (in VS Code)     │
└────────┬─────────┘
         │ MCP Protocol
┌────────▼──────────┐
│   MCP Server      │
│ (Your Integration)│
└────────┬──────────┘
         │
    ┌────┴────┬────────┬────────┐
    │         │        │        │
┌───▼───┐ ┌───▼───┐ ┌──▼──┐ ┌──▼───┐
│GitHub │ │Database│ │Fetch│ │Custom│
│  API  │ │        │ │     │ │ API  │
└───────┘ └────────┘ └─────┘ └──────┘
```

---

## Installing MCP Servers

### Option 1: GitHub MCP Server Registry (Recommended)

VS Code integrates with the GitHub MCP server registry for easy discovery:

1. Enable the gallery in settings:

   ```json
   {
     "chat.mcp.gallery.enabled": true
   }
   ```

2. Open Extensions view (`Ctrl+Shift+X`)

3. Type `@mcp` in the search field

4. Browse and install servers directly

### Option 2: Configuration File (mcp.json)

Create `.vscode/mcp.json` in your workspace:

```json
{
  "servers": {
    "playwright": {
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    },
    "github": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-github"],
      "env": {
        "GITHUB_TOKEN": "${input:github-token}"
      }
    },
    "filesystem": {
      "command": "npx",
      "args": ["-y", "@modelcontextprotocol/server-filesystem", "${workspaceFolder}"]
    }
  },
  "inputs": [
    {
      "id": "github-token",
      "type": "promptString",
      "description": "GitHub Personal Access Token",
      "password": true
    }
  ]
}
```

### Option 3: VS Code CLI

```bash
code --add-mcp '{"name":"playwright","command":"npx","args":["@playwright/mcp@latest"]}'
```

### Option 4: User Configuration

For MCP servers you want across all workspaces, use MCP: Open User Configuration command.

---

## Popular MCP Servers

| Server | Purpose | Installation |
|--------|---------|--------------|
| **Playwright** | Browser automation for testing | `npx @playwright/mcp@latest` |
| **GitHub** | GitHub API access | `npx @modelcontextprotocol/server-github` |
| **Atlassian Rovo** | Jira, Confluence, Compass access | Remote server (see below) |
| **Filesystem** | Enhanced file operations | `npx @modelcontextprotocol/server-filesystem` |
| **PostgreSQL** | Database queries | `npx @modelcontextprotocol/server-postgres` |
| **Fetch** | HTTP requests | `npx @modelcontextprotocol/server-fetch` |
| **Memory** | Persistent memory | `npx @modelcontextprotocol/server-memory` |

---

## Atlassian Rovo MCP Server (Jira & Confluence)

The **Atlassian Rovo MCP Server** is a cloud-based remote MCP server that connects your Atlassian Cloud products (Jira, Confluence, and Compass) to AI assistants like GitHub Copilot.

For more information and how to run it, please refer to [this document](https://github.com/mcp/atlassian/atlassian-mcp-server).

### What You Can Do

- **Jira**: Search issues, create/update work items, bulk create from notes
- **Confluence**: Summarize pages, create documentation, navigate spaces
- **Compass**: Query service dependencies, create components
- **Cross-product**: Link Jira tickets to Confluence pages, find related docs

### Example Workflows

```text
"Find all open bugs in Project Alpha"
"Create a story titled 'Redesign onboarding' in Jira"
"Summarize the Q2 planning page in Confluence"
"What depends on the api-gateway service in Compass?"
"Link these Jira tickets to the Release Plan page"
```

### Setup for VS Code / GitHub Copilot

The Atlassian Rovo MCP Server is a **remote server** that requires the `mcp-remote` proxy:

**Prerequisites**:

- Atlassian Cloud site with Jira and/or Confluence
- Node.js v18+ installed
- Modern browser for OAuth authentication

**Configuration** (`.vscode/mcp.json`):

```json
{
  "servers": {
    "atlassian": {
      "command": "npx",
      "args": ["-y", "mcp-remote", "https://mcp.atlassian.com/v1/sse"]
    }
  }
}
```

### Authentication

1. When you first use the Atlassian MCP tools, a browser window opens
2. Complete the OAuth 2.1 authorization flow
3. Grant permissions for the requested Atlassian products
4. Tokens are session-based and respect your existing Jira/Confluence permissions

### Security Features

- **OAuth 2.1**: Secure authentication with scoped tokens
- **Permission-based**: Only accesses data you have permission to view
- **HTTPS/TLS 1.2+**: All traffic encrypted
- **Audit logging**: Actions logged for compliance

### Beta Limitations

- Rate limits apply (higher for Premium/Enterprise plans)
- Some custom Jira fields may not be recognized
- Workspace switching not available in single session

For full documentation: [Atlassian Rovo MCP Server Guide](https://support.atlassian.com/atlassian-rovo-mcp-server/docs/getting-started-with-the-atlassian-remote-mcp-server/)

---

## Using MCP Tools in Chat

Once configured, enable MCP tools via **Configure Tools** in Agent mode. Copilot automatically selects relevant tools based on your prompt:

```text
"List my open GitHub issues and create a summary"
→ Copilot uses GitHub MCP to fetch issues

"Navigate to the login page and identify all form elements"
→ Copilot uses Playwright MCP to browse

"Query the database for users created this month"
→ Copilot uses PostgreSQL MCP
```

You can also reference tools explicitly with `#`:

```text
Using #fetch, summarize the content from https://example.com/docs
```

For details on tool approvals and security, see the [Copilot Guide](./copilot-guide.md).

---

## MCP Resources and Prompts

### Resources

MCP servers can expose resources (data) that you add as context:

1. In Chat, select **Add Context > MCP Resources**
2. Choose a resource type
3. The resource content is added to your prompt

### Prompts

MCP servers can provide pre-configured prompts:

Type `/mcp.servername.promptname` in chat to invoke.

---

## Creating Your Own MCP Server

### Basic Structure

```typescript
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import {
  CallToolRequestSchema,
  ListToolsRequestSchema,
} from '@modelcontextprotocol/sdk/types.js';

const server = new Server(
  { name: 'my-mcp-server', version: '1.0.0' },
  { capabilities: { tools: {} } }
);

// Define available tools
server.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'get_user',
      description: 'Fetch user information by ID',
      inputSchema: {
        type: 'object',
        properties: {
          userId: { type: 'string', description: 'The user ID' },
        },
        required: ['userId'],
      },
    },
  ],
}));

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'get_user') {
    const userId = request.params.arguments?.userId;
    const user = await fetchUser(userId);
    return {
      content: [{ type: 'text', text: JSON.stringify(user, null, 2) }],
    };
  }
  throw new Error(`Unknown tool: ${request.params.name}`);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}
main();
```

### Configuration for Development

Add to `.vscode/mcp.json`:

```json
{
  "servers": {
    "my-server": {
      "command": "node",
      "args": ["./mcp-server/index.js"],
      "dev": {
        "watch": "./mcp-server/**/*.js",
        "debug": true
      }
    }
  }
}
```

### Debugging

Enable development mode for:

- **watch**: Auto-restart on file changes
- **debug**: Enable VS Code debugger attachment

---

### Complete Server Example

```javascript
server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'get_user',
        description: 'Fetch user information by ID',
        inputSchema: {
          type: 'object',
          properties: {
            userId: {
              type: 'string',
              description: 'The user ID to fetch',
            },
          },
          required: ['userId'],
        },
      },
    ],
  };
});

// Handle tool calls
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  if (request.params.name === 'get_user') {
    const userId = request.params.arguments?.userId;
    
    // Your logic here
    const user = await fetchUserFromDatabase(userId);
    
    return {
      content: [
        {
          type: 'text',
          text: JSON.stringify(user, null, 2),
        },
      ],
    };
  }
  
  throw new Error(`Unknown tool: ${request.params.name}`);
});

// Start server
async function main() {
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('MCP Server running on stdio');
}

main().catch(console.error);
```

### Configuring in VS Code

Add to `.vscode/settings.json`:

```json
{
  "mcp": {
    "servers": {
      "my-server": {
        "command": "node",
        "args": ["path/to/your/mcp-server.js"]
      }
    }
  }
}
```

Or install via VS Code CLI:

```bash
code --add-mcp '{"name":"my-server","command":"node","args":["path/to/your/mcp-server.js"]}'
```

## Example: GitHub MCP Server

```typescript
// github-mcp-server.ts
import { Octokit } from '@octokit/rest';

const octokit = new Octokit({
  auth: process.env.GITHUB_TOKEN
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'get_repository',
        description: 'Get information about a GitHub repository',
        inputSchema: {
          type: 'object',
          properties: {
            owner: { type: 'string', description: 'Repository owner' },
            repo: { type: 'string', description: 'Repository name' },
          },
          required: ['owner', 'repo'],
        },
      },
      {
        name: 'list_pull_requests',
        description: 'List pull requests for a repository',
        inputSchema: {
          type: 'object',
          properties: {
            owner: { type: 'string' },
            repo: { type: 'string' },
            state: { 
              type: 'string', 
              enum: ['open', 'closed', 'all'],
              default: 'open'
            },
          },
          required: ['owner', 'repo'],
        },
      },
      {
        name: 'create_issue',
        description: 'Create a new issue',
        inputSchema: {
          type: 'object',
          properties: {
            owner: { type: 'string' },
            repo: { type: 'string' },
            title: { type: 'string' },
            body: { type: 'string' },
          },
          required: ['owner', 'repo', 'title'],
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case 'get_repository': {
      const { owner, repo } = args;
      const { data } = await octokit.repos.get({ owner, repo });
      return {
        content: [{
          type: 'text',
          text: JSON.stringify({
            name: data.name,
            description: data.description,
            stars: data.stargazers_count,
            language: data.language,
            url: data.html_url,
          }, null, 2),
        }],
      };
    }

    case 'list_pull_requests': {
      const { owner, repo, state = 'open' } = args;
      const { data } = await octokit.pulls.list({ 
        owner, 
        repo, 
        state 
      });
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(data.map(pr => ({
            number: pr.number,
            title: pr.title,
            state: pr.state,
            author: pr.user?.login,
            url: pr.html_url,
          })), null, 2),
        }],
      };
    }

    case 'create_issue': {
      const { owner, repo, title, body } = args;
      const { data } = await octokit.issues.create({
        owner,
        repo,
        title,
        body,
      });
      return {
        content: [{
          type: 'text',
          text: `Created issue #${data.number}: ${data.html_url}`,
        }],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});
```

## Example: Database MCP Server

```typescript
// database-mcp-server.ts
import { Pool } from 'pg';

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
});

server.setRequestHandler(ListToolsRequestSchema, async () => {
  return {
    tools: [
      {
        name: 'query_users',
        description: 'Query user data from database',
        inputSchema: {
          type: 'object',
          properties: {
            limit: { type: 'number', default: 10 },
            offset: { type: 'number', default: 0 },
          },
        },
      },
      {
        name: 'get_user_by_id',
        description: 'Get specific user by ID',
        inputSchema: {
          type: 'object',
          properties: {
            id: { type: 'string' },
          },
          required: ['id'],
        },
      },
      {
        name: 'get_schema',
        description: 'Get database schema information',
        inputSchema: {
          type: 'object',
          properties: {
            table: { type: 'string' },
          },
        },
      },
    ],
  };
});

server.setRequestHandler(CallToolRequestSchema, async (request) => {
  const { name, arguments: args } = request.params;

  switch (name) {
    case 'query_users': {
      const { limit = 10, offset = 0 } = args;
      const result = await pool.query(
        'SELECT id, name, email, created_at FROM users LIMIT $1 OFFSET $2',
        [limit, offset]
      );
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(result.rows, null, 2),
        }],
      };
    }

    case 'get_user_by_id': {
      const { id } = args;
      const result = await pool.query(
        'SELECT id, name, email, created_at FROM users WHERE id = $1',
        [id]
      );
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(result.rows[0] || null, null, 2),
        }],
      };
    }

    case 'get_schema': {
      const { table } = args;
      const result = await pool.query(`
        SELECT column_name, data_type, is_nullable
        FROM information_schema.columns
        WHERE table_name = $1
      `, [table]);
      return {
        content: [{
          type: 'text',
          text: JSON.stringify(result.rows, null, 2),
        }],
      };
    }

    default:
      throw new Error(`Unknown tool: ${name}`);
  }
});
```

## Using MCP with Copilot

Once your MCP server is configured, you can ask Copilot questions that require external data:

### Example Queries

```text
"What are the open pull requests in this repository?"
→ Copilot uses GitHub MCP server

"Show me all users who registered in the last week"
→ Copilot queries database via MCP

"Create a function that fetches the latest issues and formats them for display"
→ Copilot generates code using GitHub MCP context

"What's the database schema for the orders table?"
→ Copilot retrieves schema via Database MCP

"Generate a report combining GitHub activity and database metrics"
→ Copilot uses multiple MCP servers
```

## Best Practices

### 1. **Security**

- Never expose sensitive operations
- Validate all inputs
- Use authentication tokens
- Implement rate limiting
- Sanitize database queries

```typescript
// ✅ Good - Parameterized query
const result = await pool.query(
  'SELECT * FROM users WHERE id = $1',
  [userId]
);

// ❌ Bad - SQL injection risk
const result = await pool.query(
  `SELECT * FROM users WHERE id = '${userId}'`
);
```

### 2. **Error Handling**

```typescript
server.setRequestHandler(CallToolRequestSchema, async (request) => {
  try {
    // Your logic
  } catch (error) {
    return {
      content: [{
        type: 'text',
        text: `Error: ${error.message}`,
      }],
      isError: true,
    };
  }
});
```

### 3. **Performance**

- Implement caching
- Limit result sizes
- Use pagination
- Add timeouts

```typescript
import NodeCache from 'node-cache';
const cache = new NodeCache({ stdTTL: 300 }); // 5 min cache

async function getCachedData(key: string, fetcher: () => Promise<any>) {
  const cached = cache.get(key);
  if (cached) return cached;
  
  const data = await fetcher();
  cache.set(key, data);
  return data;
}
```

### 4. **Documentation**

Provide clear tool descriptions:

```typescript
{
  name: 'create_user',
  description: 'Create a new user in the database. Returns the created user with generated ID.',
  inputSchema: {
    type: 'object',
    properties: {
      name: { 
        type: 'string',
        description: 'User full name (2-100 characters)'
      },
      email: {
        type: 'string',
        description: 'Valid email address, must be unique'
      },
    },
    required: ['name', 'email'],
  },
}
```

## Testing MCP Servers

### 1. **MCP Inspector**

```bash
npx @modelcontextprotocol/inspector node your-mcp-server.js
```

Opens a UI to test your MCP server interactively.

### 2. **Unit Tests**

```typescript
import { describe, it, expect } from 'vitest';

describe('MCP Server', () => {
  it('should list tools', async () => {
    const result = await server.handleRequest({
      method: 'tools/list',
    });
    expect(result.tools).toHaveLength(3);
  });

  it('should execute get_user tool', async () => {
    const result = await server.handleRequest({
      method: 'tools/call',
      params: {
        name: 'get_user',
        arguments: { userId: '123' },
      },
    });
    expect(result.content[0].text).toContain('userId');
  });
});
```

## Common Use Cases

1. **Development Tools**
   - Code search
   - Git operations
   - Build system integration

2. **Data Access**
   - Database queries
   - File system access
   - Cloud storage

3. **External Services**
   - GitHub/GitLab
   - Jira/Linear
   - Slack/Teams
   - Weather/Maps APIs

4. **Business Logic**
   - Custom calculators
   - Validation rules
   - Company-specific workflows

5. **Infrastructure**
   - Cloud provider APIs
   - Monitoring systems
   - Log aggregators

## Troubleshooting

### MCP Server Not Connecting?

1. Check server is running: `node your-server.js`
2. Verify VS Code settings path
3. Check server logs
4. Restart VS Code

### Tools Not Appearing?

1. Verify `ListToolsRequestSchema` handler
2. Check tool schema format
3. Review MCP server logs

### Poor Responses?

1. Improve tool descriptions
2. Add more context in responses
3. Format data clearly
4. Handle errors gracefully

---

## Resources

- [MCP Specification](https://modelcontextprotocol.io/)
- [MCP SDK Documentation](https://github.com/modelcontextprotocol/sdk)
- [Example MCP Servers](https://github.com/modelcontextprotocol/servers)

---

[Back to Main README](../README.md) | [Prompt Engineering](./prompt-engineering.md)
