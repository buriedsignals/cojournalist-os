/**
 * Per-agent setup recipes for the Agents modal. Keep this file the single
 * source of truth for how to connect an AI assistant to coJournalist —
 * the UI is a dumb renderer over it.
 *
 * Each agent has one or two connection paths:
 *   - 'cli'  — the agent shells out to the `cojo` binary. No MCP server to
 *              run; the agent inspects commands as plain shell. Preferred
 *              for shell-capable agents (Claude Code, Codex CLI, Cursor,
 *              Windsurf, Gemini CLI, Goose, Hermes).
 *   - 'mcp'  — the agent connects to the remote MCP server at MCP_URL.
 *              The only option for chat UIs without shell access
 *              (Claude Desktop / claude.ai, ChatGPT).
 *
 * `defaultPath` per agent picks the one we lead with; the modal exposes
 * a toggle when both are available.
 */

import type { AgentSlug } from './agent-icons';

export type InstallPath = 'cli' | 'mcp';

export type RecipeMode = 'cli-command' | 'cli-install' | 'config-file' | 'ui-steps' | 'generic';

export interface RecipeWarning {
	title: string;
	body: string;
}

export interface Recipe {
	/** Short headline that renders under the path selector. */
	tagline: string;

	/** Optional tier / compatibility callout (ChatGPT Plus limitation, stdio bridge, etc.). */
	warning?: RecipeWarning;

	mode: RecipeMode;

	/** Single shell command for `cli-command` mode. Templated with {{MCP_URL}}. */
	command?: string;

	/** Install one-liner for `cli-install` mode (curl + chmod). */
	installCommand?: string;
	/** Config commands shown as a second copy-able block for `cli-install` mode. */
	configCommands?: string[];

	/** File path for `config-file` mode (e.g. ~/.cursor/mcp.json). */
	configPath?: string;
	/** JSON / TOML / YAML / URL snippet for `config-file`, `ui-steps`, `generic` modes. Templated with {{MCP_URL}}. */
	configSnippet?: string;
	/** Language hint for syntax highlighting (json, toml, yaml). */
	configLang?: 'json' | 'toml' | 'yaml';

	/** Numbered steps for `ui-steps` mode (also appended to `cli-command` mode). */
	uiSteps?: string[];

	/** Docs link shown next to the setup block. */
	docsUrl?: string;
	docsLabel?: string;

	/** Optional: verify prompt (overrides the default "List my coJournalist scouts"). */
	verifyPrompt?: string;
}

export const MCP_URL = 'https://www.cojournalist.ai/mcp';
export const CLI_RELEASES_URL = 'https://github.com/buriedsignals/cojournalist-os/releases/latest/download';
export const CLI_README_URL = 'https://github.com/buriedsignals/cojournalist-os/blob/main/cli/README.md';
export const SKILL_URL = 'https://www.cojournalist.ai/skill.md';

function fill(tpl: string): string {
	return tpl.replace(/\{\{MCP_URL\}\}/g, MCP_URL);
}

// ----- Shared CLI recipe ----------------------------------------------------
// All shell-capable agents use the same install + config steps. The only
// per-agent variation is where skill.md is persisted (see SKILL_PROMPTS).

const CLI_INSTALL_DEFAULT = `curl -fsSL ${CLI_RELEASES_URL}/cojo-darwin-arm64 | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo`;

const CLI_CONFIG_COMMANDS = [
	'cojo config set api_url=https://www.cojournalist.ai/api',
	'cojo config set auth_token=<paste cj_... key from the API panel>',
	'cojo --version && cojo scouts list'
];

const sharedCliRecipe: Recipe = {
	tagline: 'Install the cojo CLI — your agent shells out to it. No MCP server to manage, commands stay visible in the transcript.',
	mode: 'cli-install',
	installCommand: CLI_INSTALL_DEFAULT,
	configCommands: CLI_CONFIG_COMMANDS,
	docsUrl: CLI_README_URL,
	docsLabel: 'CLI install + other platforms',
	verifyPrompt: 'Run `cojo scouts list` and tell me what I’m monitoring.'
};

// ----- Per-agent MCP recipes (the original table) ---------------------------

const mcpRecipes: Record<AgentSlug, Recipe> = {
	'claude-code': {
		tagline: 'One command in your terminal. OAuth opens on first use.',
		mode: 'cli-command',
		command: 'claude mcp add --transport http cojournalist {{MCP_URL}}',
		docsUrl: 'https://code.claude.com/docs/en/mcp',
		docsLabel: 'Claude Code MCP docs'
	},

	'claude-desktop': {
		tagline: 'Add a custom connector in Claude — no terminal needed.',
		mode: 'ui-steps',
		uiSteps: [
			'Open Claude Desktop or claude.ai.',
			'Go to Customize → Connectors.',
			'Click "+" then "Add custom connector".',
			'Paste the URL below as the Remote MCP Server URL.',
			'Click Add, then sign in with your coJournalist account when prompted.'
		],
		configSnippet: MCP_URL,
		docsUrl: 'https://support.claude.com/en/articles/11175166-get-started-with-custom-connectors-using-remote-mcp',
		docsLabel: 'Claude custom connector docs'
	},

	chatgpt: {
		tagline: 'Add a custom connector in ChatGPT Settings.',
		warning: {
			title: 'ChatGPT plan matters',
			body:
				'Full tool-calling connectors require a Business, Enterprise, or Edu workspace. Plus and Pro users can connect coJournalist to Deep Research in read-only mode only. If you only have Plus/Pro, you can still read your data — but ChatGPT won’t be able to create or run scouts on your behalf.'
		},
		mode: 'ui-steps',
		uiSteps: [
			'In ChatGPT, open Settings → Connectors (or the avatar menu → Connectors).',
			'Click "Create" to add a new connector.',
			'Paste the URL below as the MCP Server URL.',
			'Save, then sign in with your coJournalist account when prompted.',
			'In a new chat, enable the connector from the "+" menu before asking questions.'
		],
		configSnippet: MCP_URL,
		docsUrl: 'https://help.openai.com/en/articles/11487775-connectors-in-chatgpt',
		docsLabel: 'ChatGPT connectors docs'
	},

	codex: {
		tagline: 'Codex CLI only speaks stdio — bridge via mcp-remote.',
		warning: {
			title: 'Stdio bridge required',
			body:
				'Codex CLI does not yet support remote HTTP MCP servers natively. The config below uses the official mcp-remote bridge (run via npx) so no manual install is needed. The CLI path avoids this entirely — consider using it instead.'
		},
		mode: 'config-file',
		configPath: '~/.codex/config.toml',
		configLang: 'toml',
		configSnippet: `[mcp_servers.cojournalist]
command = "npx"
args = ["-y", "mcp-remote", "{{MCP_URL}}"]`,
		docsUrl: 'https://github.com/openai/codex/blob/main/docs/config.md',
		docsLabel: 'Codex config docs'
	},

	cursor: {
		tagline: 'Add an entry to Cursor’s MCP config. OAuth on first use.',
		mode: 'config-file',
		configPath: '~/.cursor/mcp.json',
		configLang: 'json',
		configSnippet: `{
  "mcpServers": {
    "cojournalist": {
      "url": "{{MCP_URL}}"
    }
  }
}`,
		docsUrl: 'https://cursor.com/docs/mcp',
		docsLabel: 'Cursor MCP docs'
	},

	windsurf: {
		tagline: 'Add via Windsurf’s MCP panel, or edit the config file.',
		mode: 'config-file',
		configPath: '~/.codeium/windsurf/mcp_config.json',
		configLang: 'json',
		configSnippet: `{
  "mcpServers": {
    "cojournalist": {
      "serverUrl": "{{MCP_URL}}"
    }
  }
}`,
		docsUrl: 'https://docs.windsurf.com/windsurf/cascade/mcp',
		docsLabel: 'Windsurf MCP docs'
	},

	'gemini-cli': {
		tagline: 'Add a block to Gemini CLI’s settings file.',
		mode: 'config-file',
		configPath: '~/.gemini/settings.json',
		configLang: 'json',
		configSnippet: `{
  "mcpServers": {
    "cojournalist": {
      "httpUrl": "{{MCP_URL}}"
    }
  }
}`,
		docsUrl: 'https://geminicli.com/docs/tools/mcp-server/',
		docsLabel: 'Gemini CLI MCP docs'
	},

	goose: {
		tagline: 'Configure via the Goose CLI prompt flow.',
		mode: 'cli-command',
		command: 'goose configure',
		uiSteps: [
			'Run `goose configure` in your terminal.',
			'Choose "Add Extension" → "Streamable HTTP".',
			'Name the extension `cojournalist`.',
			'Paste the URL below when prompted.',
			'Authorize in the browser window that opens.'
		],
		configSnippet: MCP_URL,
		docsUrl: 'https://block.github.io/goose/docs/mcp/',
		docsLabel: 'Goose MCP docs'
	},

	openclaw: {
		tagline: 'OpenClaw’s MCP client is in active beta.',
		warning: {
			title: 'Beta support',
			body:
				'Native MCP client support for OpenClaw is tracked upstream (openclaw/openclaw#29053). Until that lands in the stable release, follow the upstream install guide below and paste the URL into the MCP extensions panel.'
		},
		mode: 'generic',
		configSnippet: MCP_URL,
		docsUrl: 'https://github.com/openclaw/openclaw/issues/29053',
		docsLabel: 'OpenClaw MCP tracking issue'
	},

	hermes: {
		tagline: 'Add a server block to Hermes’ YAML config.',
		mode: 'config-file',
		configPath: '~/.hermes/config.yaml',
		configLang: 'yaml',
		configSnippet: `mcp_servers:
  cojournalist:
    url: {{MCP_URL}}
    transport: streamable_http`,
		docsUrl: 'https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp',
		docsLabel: 'Hermes Agent MCP docs'
	},

	other: {
		tagline: 'Any MCP-speaking client. Paste this URL and authorize.',
		mode: 'generic',
		configSnippet: MCP_URL,
		docsUrl: 'https://modelcontextprotocol.io',
		docsLabel: 'Model Context Protocol docs'
	}
};

// ----- Which path is primary per agent --------------------------------------
// Rule of thumb: if the agent has shell access, default to CLI. Chat UIs
// without shell (Claude Desktop, ChatGPT) are MCP-only. "Other" offers both.

const CLI_CAPABLE: AgentSlug[] = [
	'claude-code',
	'codex',
	'cursor',
	'windsurf',
	'gemini-cli',
	'goose',
	'hermes'
];

const MCP_ONLY: AgentSlug[] = ['claude-desktop', 'chatgpt', 'openclaw'];

export interface AgentRecipes {
	/** Which paths are available for this agent, in display order. */
	paths: InstallPath[];
	/** The path we recommend (preselected in the UI). */
	default: InstallPath;
	/** Recipe per available path, values filled in. */
	recipes: Partial<Record<InstallPath, Recipe>>;
}

/** Resolve recipes + default path for an agent. */
export function getAgentRecipes(slug: AgentSlug): AgentRecipes {
	const hasCli = CLI_CAPABLE.includes(slug);
	const hasMcp = !MCP_ONLY.includes(slug) ? true : true; // every agent has some MCP recipe
	// "Other" gets both CLI + MCP so generic users can pick.
	const includeCli = hasCli || slug === 'other';

	const paths: InstallPath[] = [];
	const recipes: Partial<Record<InstallPath, Recipe>> = {};

	if (includeCli) {
		paths.push('cli');
		recipes.cli = fillRecipe(sharedCliRecipe);
	}
	paths.push('mcp');
	recipes.mcp = fillRecipe(mcpRecipes[slug]);

	const defaultPath: InstallPath = includeCli && !MCP_ONLY.includes(slug) ? 'cli' : 'mcp';
	return { paths, default: defaultPath, recipes };
}

function fillRecipe(r: Recipe): Recipe {
	return {
		...r,
		command: r.command ? fill(r.command) : undefined,
		configSnippet: r.configSnippet ? fill(r.configSnippet) : undefined
	};
}

/**
 * Legacy single-recipe accessor. Returns the recipe for the agent’s default
 * path. Kept for any consumer that hasn’t yet switched to getAgentRecipes.
 */
export function getRecipe(slug: AgentSlug): Recipe {
	const { default: defaultPath, recipes } = getAgentRecipes(slug);
	return recipes[defaultPath] ?? mcpRecipes[slug];
}

/**
 * Per-agent skill-save location. Tells the agent where skill.md should be
 * persisted so it auto-loads in future sessions. The skill file itself
 * (SKILL_URL) is agnostic — same content for every agent.
 */
const SKILL_LOCATIONS: Record<AgentSlug, string> = {
	'claude-code': '.claude/skills/cojournalist.md',
	'claude-desktop': "this Project's instructions (or your memory)",
	chatgpt: "this Project's instructions (or your memory)",
	codex: 'AGENTS.md (or ~/.codex/AGENTS.md for global reuse)',
	cursor: '.cursor/rules/cojournalist.mdc',
	windsurf: '.windsurf/rules/cojournalist.md',
	'gemini-cli': 'GEMINI.md (or ~/.gemini/GEMINI.md for global reuse)',
	goose: '.goosehints (or ~/.config/goose/.goosehints for global reuse)',
	openclaw: 'somewhere your agent loads on startup (project rules, system prompt, or memory)',
	hermes: '~/.hermes/skills/cojournalist.md',
	other: 'somewhere your agent loads on startup (project rules, system prompt, or memory)'
};

const CLI_INSTALL_LINE = `curl -fsSL ${CLI_RELEASES_URL}/cojo-darwin-arm64 | sudo tee /usr/local/bin/cojo > /dev/null && sudo chmod +x /usr/local/bin/cojo`;

/**
 * Build a complete 1-click setup prompt that walks the agent (and user)
 * through connecting to coJournalist end-to-end. The agent:
 *
 *   1. Fetches skill.md so it understands the product
 *   2. Installs the cojo CLI (or configures MCP)
 *   3. Prompts the user for the JWT and calls the right config command
 *   4. Verifies the connection
 *   5. Reports back what it can do and where it saved skill.md
 *
 * Paste this into any agent's first message and it self-configures.
 */
export function getSetupPrompt(slug: AgentSlug, path: InstallPath = 'cli'): string {
	const location = SKILL_LOCATIONS[slug] ?? SKILL_LOCATIONS.other;

	if (path === 'mcp') {
		return [
			`Set me up with coJournalist. Do this in order, narrating each step:`,
			``,
			`1. Fetch ${SKILL_URL} and save it to ${location} so it auto-loads in future sessions. This is the product skill — it tells you how to drive coJournalist.`,
			`2. Configure the remote MCP server at ${MCP_URL}. If a config file edit is needed, show me the exact file path and diff before saving.`,
			`3. The MCP server uses OAuth — when the connector prompts me to sign in, I'll approve it in the browser. Do not ask me for a JWT or API key; the OAuth flow handles auth.`,
			`4. Verify the connection by listing my scouts. If the tool isn't available yet, tell me to reload the chat.`,
			`5. Summarise what coJournalist lets you do for me and suggest one concrete thing you'd use it for based on my current work.`
		].join('\n');
	}

	return [
		`Set me up with coJournalist via the cojo CLI. Do this in order, narrating each step:`,
		``,
		`1. Fetch ${SKILL_URL} and save it to ${location} so it auto-loads in future sessions. This is the product skill — it tells you how to drive coJournalist.`,
		`2. Install the cojo CLI by running: ${CLI_INSTALL_LINE}`,
		`   (On Intel Mac / Linux, swap the asset suffix to -darwin-x86_64, -linux-x86_64, or -linux-arm64.)`,
		`3. Tell me to generate an API key at https://www.cojournalist.ai → Agents → API → Create key (it's shown once). Do NOT ask me to paste the key into this chat — credentials in a transcript leak into logs and screenshots. Instead, have me run these two commands in my own terminal so the key never enters the conversation:`,
		`     cojo config set api_url=https://www.cojournalist.ai/api`,
		`     cojo config set auth_token=cj_...   # I replace cj_... with the real key locally`,
		`4. After I confirm I've done that, verify by running: cojo --version && cojo scouts list — if it returns my scouts, we're connected. The CLI reads the key from ~/.cojournalist/config.json, so you never see it.`,
		`5. From now on, use the cojo CLI to create scouts, list findings, and verify units on my behalf. Don't ask me to open the web UI when you can do it via the CLI.`,
		`6. Summarise what coJournalist lets you do for me and suggest one concrete thing you'd use it for based on my current work.`
	].join('\n');
}

/** Backwards-compatible alias. */
export function getSkillPrompt(slug: AgentSlug, path: InstallPath = 'cli'): string {
	return getSetupPrompt(slug, path);
}

/** @deprecated Use getSetupPrompt(agent, path) — kept for backwards compatibility. */
export const SKILL_PROMPT = getSetupPrompt('other', 'cli');
